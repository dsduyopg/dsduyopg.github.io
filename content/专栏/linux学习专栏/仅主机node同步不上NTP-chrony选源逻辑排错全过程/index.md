---
comments: true
giscusMapping: "og:title"
utterancesIssueTerm: "og:title"
title: "仅主机 node 能 ping 通 jumper，却同步不上 NTP？删掉一行公网 pool 就好了——chrony 选源逻辑排错全过程"
date: 2026-08-26
lastmod: 2026-08-26
draft: false
ShowToc: false
description: "node 仅主机能 ping 通 jumper，chrony 却死活同步不上 NTP，同一台宿主机的 WSL 却好好的。排查到最后发现是 chrony.conf 里一行公网 pool 的事：删掉立刻恢复。本文完整还原分层排错过程，并把 chrony「不切换源」的选源逻辑一次讲透。"
tags: ["Linux", "VMware", "chrony", "NTP", "网络排错", "仅主机"]

---

{{< toc >}}

> **前言**
>
> 跟着黑马课程做到「时间同步」这一节，我的环境是上一篇文章里的那套拓扑：一台 jumper 双网卡/三网卡当网关，node1_copy、node2_copy 是仅主机模式的节点。
>
> 现象非常诡异：**node1_copy 能 ping 通 jumper，但 chrony 就是同步不上 NTP**；而同一台宿主机里的 WSL（AlmaLinux）里跑 chrony 却好好的，公网源都能用。
>
> 我一度怀疑是 MobaXterm 的问题、是 jumper 的 NTP 服务没起、是防火墙在拦、是 SELinux 在作怪……几乎把网络栈从客户端到服务端查了个遍。结果最后发现，**问题就在 node1_copy 自己的 `/etc/chrony.conf` 里一行公网 pool**——删掉它，`chronyc sources` 立刻变成 `^*`。
>
> 如果你也遇到过「能 ping 通却同步不上时间」的怪事，希望这篇排错记录能帮你省下这几个小时。更重要的是，这篇文章会把 chrony 为什么「明明有可达的第二个源，却不去用它」的选源逻辑彻底讲清楚——这才是这次排错最有价值的部分。

**快速结论**

| 问题 | 答案 |
| --- | --- |
| 为什么同步不上 NTP | `chrony.conf` 里混配了公网源 `pool 2.centos.pool.ntp.org iburst`，仅主机节点没有公网出口，该源永远不可达 |
| 为什么 ping 通但 NTP 不通 | ping jumper 是「本机到 jumper 自己」，不用出公网；NTP 去公网 pool 要借道 jumper 的 NAT 转发，这条链路上 UDP 123 没通 |
| 为什么 WSL 却可以 | WSL2 走宿主机自己的 NAT 出公网，和虚拟机所在的 VMnet 是两条完全独立的路径 |
| 为什么删掉公网 pool 就好了 | 配置里只剩一个可达的内网源，没有第二个源可比较，chrony 必然选中它 |
| 怎么修 | 删掉公网 pool，只留 `pool 192.168.149.10 iburst`（内网源） |

## 1. 实验环境与拓扑

沿用上一篇 iptables 排错文章里的那套 VMware 拓扑，再加上一台 WSL 做对照：

```text
┌────────────────────────────────────────────┐
│ VMware 宿主机（Windows）                    │
│  ┌──────────┐        ┌──────────┐          │
│  │ WSL2     │        │ (宿主机 NAT 出口)   │
│  │ AlmaLinux│        └────┬─────┘          │
│  └────┬─────┘             │ 独立 NAT 路径   │
│       │                   ▼                │
│       │           ┌──────────────────┐     │
│       │           │jumper（3 网卡）  │     │
│       │           │ens33 192.168.149.10 ← NAT 口（连 VMnet8）
│       │           │ens36 10.1.1.128   ← 仅主机口（连 VMnet2）
│       │           │ens37 172.16.0.128 ← 仅主机口（连 VMnet3）
│       │           └───┬────────┬─────┘     │
│       │               │        │           │
│       │            VMnet2     VMnet3       │
│       │            （仅主机） （仅主机）    │
│       ▼               ▼        ▼           │
│  WSL 走宿主 NAT   ┌────────┐ ┌────────┐    │
│  可直接出公网     │node1_  │ │node2_  │    │
│                   │copy    │ │copy    │    │
│                   │10.1.1.1│ │172.16.x│    │
│                   └────────┘ └────────┘    │
└────────────────────────────────────────────┘
```

| 机器 | 网络模式 | 网段 | 角色 |
| --- | --- | --- | --- |
| jumper | VMnet8（NAT）+ VMnet2/VMnet3（仅主机） | 192.168.149.10 / 10.1.1.128 / 172.16.0.128 | 网关 + NTP 服务器 |
| node1_copy | VMnet2（仅主机） | 10.1.1.1 | 目标节点 A |
| node2_copy | VMnet3（仅主机） | 172.16.0.x | 目标节点 B |
| WSL2 AlmaLinux | 宿主机 NAT（Hyper-V 虚拟交换机） | 独立 | 对照组 |

> 网段按你自己的虚拟网络编辑器实际配置为准。本实验里 chrony 源配的是 `192.168.149.10`（jumper 的 NAT 口），node1_copy 通过 jumper 内部转发可以直达它。

## 2. 现象：ping 通，NTP 不通

先复现一下问题：

```bash
# node1_copy 上：ping jumper，通
[root@node1 ~]# ping -c 2 192.168.149.10
PING 192.168.149.10 (192.168.149.10) 56(84) bytes of data.
64 bytes from 192.168.149.10: icmp_seq=1 ttl=64 time=0.5 ms   ← 通

# node1_copy 上：看时间同步状态，公网源一直不可达
[root@node1 ~]# chronyc sources
MS Name/IP address         Stratum Poll Reach LastRx Last sample
^? 2.centos.pool.ntp.org        3    6    17    3  +535ns[+37us] +/- 133ms
^? 2.centos.pool.ntp.org        3    6     0    -  ...
...
```

`^?` 表示该源**不可达**，没有任何源被选为 `^*`（当前同步源），时间自然就同步不上。

而 WSL 里同样的 chrony 配置（公网 pool + 本地源混配），却能正常 `^*` 同步。这就是最让人困惑的地方：**同一个公网 pool，WSL 能用，虚拟机不能用；同一个 jumper，能 ping 通，NTP 却不通。**

## 3. 排查过程：一层一层剥开

排错切忌瞎猜，我把整个链路拆成「客户端 → 服务端 → 中间路径 → 源头配置」四层，一层层排除。

### 3.1 第一层：是不是 MobaXterm / 客户端的问题？

第一个怀疑对象是 MobaXterm——因为现象是在 MobaXterm 里连 node1_copy 观察到的。

排除：MobaXterm 只是一个终端模拟器，它只负责「显示字符」，不参与 NTP 同步。换个终端（直接进 VMware 控制台）现象一模一样，说明与客户端无关，直接排除。

> 教训：客户端工具只是「眼睛」，不是「手」。现象出现在哪个工具里，不等于问题出在哪个工具里。

### 3.2 第二层：jumper 的 NTP 服务到底通不通？

这是关键一步：**先确认服务端是不是好的，再往下查**。我在宿主机上用 `w32tm` 直接对 jumper 的三个 IP 发 NTP 探测：

```bash
# 宿主机上，对 jumper 的三个网卡口分别测 UDP 123
w32tm /stripchart /computer:192.168.149.10 /samples:3 /dataonly
w32tm /stripchart /computer:10.1.1.128    /samples:3 /dataonly
w32tm /stripchart /computer:172.16.0.128  /samples:3 /dataonly
```

三个 IP 全部回包。再用 WSL 直接向 `192.168.149.10:123` 发一个手工构造的 NTP 请求包（48 字节），也收到了 48 字节的响应：

```text
NTP from WSL to 192.168.149.10: OK (48 bytes)
```

**结论：jumper 的 chronyd 在正常监听，UDP 123 对这几个来源都是通的。服务端没问题。**

### 3.3 第三层：模拟「仅主机网段的源 IP」去访问，是不是防火墙 / allow 在拦？

宿主机测通了，但宿主机不是「仅主机网段」的机器。万一 jumper 的 chrony `allow` 列表或 firewalld 只放行了某些来源呢？node 那边是 `10.1.1.x` 网段，我直接在宿主机上临时加一条路由，绑定 `10.1.1.3` 这个仅主机网段的源地址，向 jumper 的 NAT 口发 NTP：

```bash
route add 192.168.149.10 mask 255.255.255.255 10.1.1.128   # 临时路由，测完即删
# 绑定源地址 10.1.1.3 发 UDP 123 到 192.168.149.10
```

结果也是通的（拿到 NTP 响应）。

**结论：不是防火墙拦来源，也不是 chrony 的 allow 列表问题。服务端对「仅主机网段」的请求也放行。**

### 3.4 收窄：问题只剩 node1_copy 自己

服务端正常、中间路径正常，那问题一定在 node1_copy 这台机器自己的配置上。直接看它的 chrony 配置：

```bash
[root@node1 ~]# grep -vE '^\s*(#|$)' /etc/chrony.conf
pool 2.centos.pool.ntp.org iburst      ← 公网源
pool 192.168.149.10 iburst             ← 内网源（jumper）
```

**问题浮出水面：配置里混配了公网源 + 内网源，而 node1_copy 是仅主机模式，出不了公网。**

### 3.5 验证：删掉公网 pool 那一行

把 `pool 2.centos.pool.ntp.org iburst` 删掉，重启 chronyd：

```bash
[root@node1 ~]# systemctl restart chronyd
[root@node1 ~]# chronyc sources
MS Name/IP address         Stratum Poll Reach LastRx Last sample
^* 192.168.149.10               3     6    17    3  +535ns[+37us] +/- 133ms
```

`^*` 出现了——**同步立刻成功**。

到这里，问题解决。但如果你以为这就结束了，那就亏了。真正值钱的问题是下面这个：

## 4. 为什么删掉一行就好了？（核心原理）

删掉之前，配置里明明还有 `pool 192.168.149.10 iburst` 这个**可达**的源。按照直觉，「第一个源不可达，不是应该自动切到第二个源吗」？

为什么 chrony 不切？这里有两个原因，一层比一层深。

### 4.1 原因一：仅主机节点没有公网出口，公网源永远不可达

node1_copy 是**仅主机模式**（VMnet2），这个网络的特性就是：**默认没有 DHCP、没有 NAT、没有公网出口**。它想访问公网，唯一的办法是借道 jumper 的转发（就是上一篇 iptables 排错文章里配的那套 NAT/MASQUERADE）。

而实测这条转发链路上，**UDP 123 并没有被放通**——所以 `2.centos.pool.ntp.org` 这个公网源对 node1_copy 来说，是永远不可达的。这不是暂时的网络抖动，而是拓扑上就没有这条路。

注意区分：**「ping 通 jumper」和「NTP 访问公网」是两码事。**

```text
node1_copy → ping jumper 192.168.149.10
  = 本机到「jumper 自己」，jumper 内部转发即可，不需要出公网 → 通

node1_copy → NTP 到 2.centos.pool.ntp.org
  = 本机 → jumper → NAT 转发 → 公网 → 回来，UDP 123 没放通 → 不通
```

### 4.2 原因二：chrony 不是「故障切换」逻辑，而是「平滑优先」逻辑（重点）

这是整个排错里最反直觉、也最值得记住的一点。

**chrony 的首要目标，是让系统时钟尽可能平滑、误差尽可能小，而不是让「源切换」发生得最快。**

chrony 官方 FAQ 里专门有一节叫 *"An unreachable source is selected?"*（为什么选中了一个不可达的源？），原文大意是：

> 当最佳源（`*` 标记的那个）变得不可达时，chronyd **不会立即切换到第二好的源**，目的是尽量减少时钟误差。只要基于之前测量得出的误差估计（root distance）仍然小于第二个源的误差估计，并且两个源的测量区间还有重叠，它就会让时钟继续自由运行（free-run）。如果第一个源明显比第二个准，可能**需要很多小时才会切换**，具体取决于轮询间隔（poll interval）。

翻译成人话：

1. 公网 pool 一开始是可达的（以前可能通，或者 chrony 假定它可达），chrony 把它当「最佳源」；
2. 后来它变得不可达了，但 chrony 觉得：我的时钟误差还在可接受范围内，何必冒险去切一个误差可能更大的源？**先让时钟自己跑着，继续等原源**；
3. 于是它就一直等、一直重试，而不是「啪」地一下切到 jumper。

### 4.3 原因三：`pool` 是动态源，会不断「换人」，让选择过程更不稳定

还有一个细节：`pool` 和 `server` 不一样。

- `server`：固定一台服务器，就那一台，没得选；
- `pool`：chrony 会通过 DNS 把 `2.centos.pool.ntp.org` 解析出**一堆**服务器地址（一个公网 pool 通常有几十上百台），然后在它们之间动态挑选、替换。

所以你的配置里表面是「两行」，实际是「一堆公网候选 + 一个内网候选」。那些公网候选全不可达，chrony 还会不停地用新解析出来的地址替换旧的、反复重试——**选择过程一直处于不稳定状态**，本应「躺赢」的本地源 `192.168.149.10` 也就一直没有被稳定地选为 `^*`。

### 4.4 为什么删掉那行就立刻 OK？

删掉公网 pool 之后，配置里只剩下一个源：

```text
pool 192.168.149.10 iburst
```

**没有第二个源可以比较，也就不存在「要不要切换」的问题**——chrony 没有别的候选，只能选它，于是立刻 `^*`。

### 4.5 为什么 WSL 可以？（对照组的价值）

WSL2 的网络和虚拟机是**完全独立的两条路**：

```text
node1_copy：VMnet2 仅主机 → 借道 jumper NAT 转发 → 公网（UDP 123 不通）
WSL2     ：Hyper-V 虚拟交换机 → 宿主机自己的 NAT → 公网（通）
```

WSL2 走的是宿主机（Windows）自己的 NAT 出口，根本不经 jumper，所以它访问公网 NTP pool 是通的，混用公网源当然没问题。**这也解释了为什么「对照实验」很重要**——WSL 能通，恰恰证明了问题不在公网 NTP 服务器、不在宿主机网络，而在虚拟机那套拓扑的出公网路径上。

## 5. 正确姿势与加固建议

经过这次排错，我的环境里 node1_copy 的正确配置就是：

```bash
# /etc/chrony.conf（仅主机节点）
pool 192.168.149.10 iburst     # jumper 的 NTP 服务，内网直达
```

如果以后 node2_copy 也做时间同步，同理只写它所在网段对应的 jumper 内网口：

```bash
pool 172.16.0.128 iburst
```

如果你想保留公网源做冗余，有三条路（按推荐程度排序）：

| 方案 | 做法 | 说明 |
| --- | --- | --- |
| ① 修好出公网路径（最彻底） | 放通 jumper 转发链路上的 UDP 123（firewalld + iptables） | 公网源本身可达，就没有「切不切」的纠结了 |
| ② 给内网源加 `prefer` | `pool 192.168.149.10 prefer iburst` | 让内网源优先被选中，公网源只做兜底 |
| ③ 限制不可达源存活时间 | 给公网源加 `maxunreach` | 需要 chrony 4.8+，超过时限的不可达源不再参与选择 |

## 6. 避坑清单（复习用）

这次排错总结出来的几条，下次直接照着查：

1. **分层排错**：客户端 → 服务端 → 中间路径 → 源头配置，一层层排除，不要上来就猜。
2. **「ping 通」≠「服务通」**：ping 走 ICMP，NTP 走 UDP 123，两条路径完全可能一个通一个不通。
3. **仅主机 / NAT 节点的「出公网路径」要单独确认**：拓扑上没有公网出口时，一切公网源都是「不可达」的代名词。
4. **chrony 选源是「平滑优先」不是「切换优先」**：不可达的源不会立刻被替换，可能要等很久；别对着 `^?` 干等，直接查配置。
5. **`pool` 是动态源**：一个 pool 背后是几十台服务器，不可达时会不断替换，别把它当一台 `server` 来理解。
6. **WSL 通 ≠ 虚拟机通**：WSL2 走宿主 NAT，虚拟机走 VMnet，两条路互不相干，对照实验要看懂对照组到底在对照什么。
7. **仅主机节点的时间同步，直接指向内网 NTP 服务器**：`pool 192.168.149.10 iburst`，一行搞定，别写公网源。

---

**参考**：chrony 官方 FAQ「An unreachable source is selected?」：<https://chrony-project.org/faq.html>

> 最后说句题外话：这次排错最有价值的地方，不是「删了一行配置」，而是搞懂了 chrony 的设计哲学——**时间同步系统里，稳定比反应快更重要**。很多「看起来不合理」的行为，背后都有它自己的设计理由。理解设计意图，比记住命令本身，能让你走得更远。
