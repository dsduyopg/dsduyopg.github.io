---
comments: true
title: "VMware 仅主机 + NAT 模式下 iptables 转发失败的排错全过程（MASQUERADE 挂错网卡）"
date: 2026-08-18
lastmod: 2026-08-24
draft: false
ShowToc: false
description: "照着教程敲了 MASQUERADE 却上不了外网？一个 ens160 和 ens33 的网卡名错位，加上重复规则掩盖问题，排查了一上午。本文完整还原抓包定位的全过程，并附上 10 分钟定位 NAT 转发故障的避坑清单。"
tags: ["Linux", "VMware", "iptables", "网络排错", "NAT"]

---

{{< toc >}}

> **前言**
>
> 今天上午做 VMware 内网流量转外网的实验，照着教程一行一行敲命令，结果 node 能 ping 通网关，却死活 ping 不通百度。
>
> 我查了路由表、翻了 iptables 规则、确认了内核转发、关了 firewalld……几乎把 Linux 网络栈翻了个底朝天，几度想直接跳过这个实验。直到最后敲下 `ip route get 8.8.8.8`，盯着输出沉默了三秒——**教程里写的是 `ens160`，而我的外网网卡，叫 `ens33`**。更讽刺的是，之前加过的重复规则把真正的问题掩盖了整整一上午。
>
> 一个网卡名的错位，一次规则的冗余，让我怀疑人生了大半天。如果你也在做 NAT 转发实验，遇到"node 能 ping 通网关却上不了外网"，希望这篇排坑记录能帮你省下这几个小时——**因为"低级错误"从来不低级，它只是隐蔽得恰到好处。**

**快速结论**

| 问题 | 答案 |
| --- | --- |
| 为什么不通 | `-o ens160` 挂到了不存在的网卡上，真实外网出口是 `ens33` |
| 怎么修 | 清掉 NAT 规则后用 `-o ens33 -j MASQUERADE` 重新添加 |
| 怎么验证 | 用 `ip route get 8.8.8.8` 找真实出口，再用 `iptables -t nat -S POSTROUTING` 核对 `-o` |

## 1. 实验环境

跟着黑马 Linux 云计算课程做网络拓扑实验，目标是让多台仅主机模式的虚拟机，通过一台拥有 NAT 网卡的"网关机"访问外网。

整体拓扑如下：

```text
┌──────────────────────────────────┐
│VMware 宿主机                     │
│（物理网卡 → 互联网）             │
└────────────────┬─────────────────┘
                 │
                 ▼
┌──────────────────────────────────┐
│jumper 网关机（3 块网卡）         │
│ens33: 192.168.149.10 ← 外网口    │
│ens36: 10.1.1.128     ← 内网口    │
│ens37: 172.16.0.128   ← 内网口    │
└─────────────┬────────────┬───────┘
              │             │
              VMnet2        VMnet3
              （仅主机）    （仅主机）
              ▼             ▼
        ┌────────────┐  ┌────────────┐
        │node1       │  │node2       │
        │10.1.1.x    │  │172.16.0.x  │
        └────────────┘  └────────────┘

   node1 / node2 ──ping──▶ 百度 ❌（本次故障）
   node1 / node2 ──ping──▶ 192.168.149.10 ✅（能通 jumper）
```

| 机器 | 网卡模式 | IP | 角色 |
| --- | --- | --- | --- |
| **jumper** | ens33：NAT 模式（VMnet8）　ens36：仅主机模式（VMnet2）　ens37：仅主机模式（VMnet3） | ens33: 192.168.149.10（外网口）　ens36: 10.1.1.128　ens37: 172.16.0.128 | 路由器/网关，负责帮内网机器转发流量 |
| **node1** | 仅主机模式（VMnet2） | 10.1.1.x（网关指向 10.1.1.128） | 内网机器，借 jumper 上外网 |
| **node2** | 仅主机模式（VMnet3） | 172.16.0.x（网关指向 172.16.0.128） | 内网机器，同上 |

**拓扑目标**：node1 和 node2 本身没有外网 IP，通过 jumper 做 NAT 转发访问互联网。

## 2. 故障现象

现象很直接：**node1、node2 都 ping 不通百度，但它们能 ping 通 jumper 的 ens33 网段（192.168.149.10）**；jumper 自己能正常 ping 通外网，我也已经开启了内网流量转外网的转发。

在 jumper 上执行了经典的 MASQUERADE 命令（照着视频抄的）：

```bash
iptables -t nat -A POSTROUTING -o ens160 -j MASQUERADE
```

然后在 node1 上测试，结果就出问题了——没有出现老师演示的效果。

![1f9f9f22-78a3-4aad-99f4-c5a176f1568e](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/1f9f9f22-78a3-4aad-99f4-c5a176f1568e.png)

外网无法 ping 通：

![d0a74657-15f1-4f85-8011-48b5bf5d8258](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/d0a74657-15f1-4f85-8011-48b5bf5d8258.png)

但能 ping 通 jumper 的 ens33 网段（192.168.149.10）。

node2 上的结果和 node1 完全一样：无法 ping 通外网，但能 ping 通 jumper 的 NAT 网段。

## 3. 排查过程

### 3.1 检查默认网关

先在 node1 上核验：

```bash
ip route show
```

![7e9998a2-cbf6-471b-aeea-be8c2d0335f2](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/7e9998a2-cbf6-471b-aeea-be8c2d0335f2.png)

发现默认配置完全正确，正是目标的网段。node2 上的核查结果一样，它的默认网关显示为 172.16.0.128。这一步没有问题，继续下一步。

### 3.2 确认 node1 到 jumper 的内网连通性

这一步在"故障现象"部分已经描述过：node1 和 node2 都能访问 jumper 的 NAT 网段，没有问题。顺手把验证命令贴出来，方便照做：

```bash
# node1 上 ping jumper 的 ens36（内网口）
ping 10.1.1.128

# node2 上 ping jumper 的 ens37（内网口）
ping 172.16.0.128
```

能通说明内网这一段链路是健康的，问题大概率出在 jumper 的外网出口一侧。

### 3.3 确认 jumper 自己能上外网

在 jumper 上核验，结果也是正常的：

```bash
ping baidu.com
```

![2484c483-b87e-47ea-9ed3-530058ace41f](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/2484c483-b87e-47ea-9ed3-530058ace41f.png)

### 3.4 确认内核转发已开启

```bash
cat /proc/sys/net/ipv4/ip_forward
```

![4512766e-0ae0-4eea-9ff9-92bb2727e6e2](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/4512766e-0ae0-4eea-9ff9-92bb2727e6e2.png)

输出为 `1`，说明内核转发已开启——这一步是"能转发"的前提，但注意：**转发开启 ≠ NAT 已生效**，真正决定能不能上网的是后面的 MASQUERADE 规则。

### 3.5 确认 FORWARD 链放行

```bash
iptables -L FORWARD -n
```

发现 FORWARD 链的默认策略是 `DROP`，且没有任何放行规则！

**补上：**

```bash
iptables -A FORWARD -j ACCEPT
```

补完后测试——**还是不通**：

![6fbb382b-6143-4a24-aa0c-3527920d6139](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/6fbb382b-6143-4a24-aa0c-3527920d6139.png)

### 3.6 抓包定位（关键转折点）

在 jumper 上开两个终端抓包：

**终端 1：抓内网入口**

```bash
tcpdump -i ens36 icmp
```

**终端 2：抓外网出口**

```bash
tcpdump -i ens160 icmp
```

然后在 node1 上 `ping 8.8.8.8`。

**结果**：ens36 上能看到 ICMP 包进来；ens160 那个终端里的 `tcpdump` 一启动就直接报 `No such device exists` 并退出——因为 jumper 上压根没有 ens160 这块网卡，根本进不了抓包状态。这本身就暴露了问题：**我的外网网卡不叫 ens160。**

这说明：**包确实到了 jumper，但 NAT 转换没生效，包没有被扔到外网网卡上。**

问题锁定在 `iptables -t nat` 的 POSTROUTING 规则。

### 3.7 查看 NAT 规则（真相浮出水面）

```bash
iptables -t nat -S POSTROUTING
```

输出：

```bash
-P POSTROUTING ACCEPT
-A POSTROUTING -s 192.168.149.0/24 -o ens160 -j MASQUERADE
-A POSTROUTING -o ens160 -j MASQUERADE
```

两条 MASQUERADE 规则——**一条是我之前加的（带 `-s 192.168.149.0/24`），一条是后来加的（不带 `-s`）**，而且两条的 `-o` 都写着 `ens160`——问题就出在这里。

![93cf7b3f-2c59-402f-b0d8-47f211e381f9](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/93cf7b3f-2c59-402f-b0d8-47f211e381f9.png)

> 小提示：`iptables -L` 不带 `-v` 时只显示 `opt` 列，看不出 `-o` 是哪个网卡；用 `iptables -t nat -S POSTROUTING` 或加上 `-v` 才看得到出网口。这也是我一开始差点漏掉它的原因。

### 3.8 核对真实的外网网卡名

```bash
ip route get 8.8.8.8
```

输出：

```bash
8.8.8.8 via 192.168.149.2 dev ens33
```

`dev ens33`！外网出口是 **ens33**，不是 ens160！

![01840f1d-55b3-42da-b218-fa276e0c2597](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/01840f1d-55b3-42da-b218-fa276e0c2597.png)

**再确认一下 `ifconfig`（整理成关键信息）：**

```text
ens33: 192.168.149.10   ← NAT 模式，外网口（真实外网出口）
ens36: 10.1.1.128       ← 仅主机，内网口
ens37: 172.16.0.128     ← 仅主机，内网口
```

对比一下就很清楚了：**jumper 上根本没有 ens160 这块网卡**，`-o ens160` 的规则从一开始就是一条"死规则"，永远不会匹配任何流量。

![2cd27eb2-d5b2-44c1-bab5-a4618f960ebd](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/2cd27eb2-d5b2-44c1-bab5-a4618f960ebd.png)

**根因找到了：**

1. 视频里老师的机器外网网卡叫 `ens160`，我照抄写成了 `-o ens160`；

![c5dd78c1-5752-424e-937b-16cb301b2902](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/c5dd78c1-5752-424e-937b-16cb301b2902.png)

2. 我的真实外网网卡是 `ens33`；
3. MASQUERADE 规则挂在了**不存在的网卡（ens160）**上，包出去时根本没被伪装，外网的回包自然也就回不来。

## 4. 根因分析

这次故障其实是**三个因素叠加**成的"隐形陷阱"：

| 因素 | 怎么坑的 |
| --- | --- |
| **网卡名抄错** | 教程里是 `ens160`，我的是 `ens33`。一行字写错，后面全白费 |
| **规则重复** | 加了带 `-s` 和不带 `-s` 的两条，链里看起来"有规则"，实则都挂错网卡 |
| **环境不一致** | 老师的机器上 ens160 是外网口（机房 88 网段）、ens33 是内网口；我的机器 ens33 才是外网口（149 网段）、ens36/ens37 是内网口，两边网卡的角色完全对不上 |

> **为什么网卡名会不一样？** Linux 网卡名（ens33/ens36/ens160）是 udev 根据网卡的 PCI 总线位置自动生成的，不同的虚拟机模板、不同的宿主机硬件，命名就可能完全不同。所以**永远不要照抄教程里的网卡名**——动手前先 `ip -br link` 看一眼自己机器上到底叫什么，这是本文最核心的教训。

Linux 网络排错最"坑"的地方在于：**所有错误的表现完全一样——就是不通。** 你根本分不清是哪个环节出了问题，排查只能靠排除法一层层剥。更扎心的是，我当时太依赖教案了：**想着"把老师给的命令原样敲进 jumper 就能 OK"**——命令确实是通用的，可**网卡名不是**——老师的机器叫 ens160，我这台叫 ens33。当时只看到一长串英文字母就大意了，没有核对配置信息，于是最简单的问题被我排查来排查去，白白浪费了一上午。

还要注意：那条带 `-s 192.168.149.0/24` 的规则，即使把 `-o` 改成 ens33 也不会生效，因为 node1 的源地址是 `10.1.1.x`、node2 是 `172.16.0.x`，都不在 `192.168.149.0/24` 里。它属于"写错了两次"：出网口写错，来源网段也写错。

**为什么挂错网卡不报错？** 这里补一个关键原理：iptables 添加 `-o ens160` 规则时，**并不会校验这块网卡是否存在**。它只是在规则里记下"从 ens160 出去的流量才匹配这条规则"，而 ens160 压根不存在，所以这条规则永远匹配不到任何流量，于是被静默忽略——**命令执行成功，效果却是零**。这就是为什么抓包能看到包进 jumper，却始终没有被伪装、也没从外网口出去。这类错误隐蔽就隐蔽在：**iptables 不会给你任何报错提示，一切看起来都"正常"，只有结果不对。**

**为什么连回包都收不到？** MASQUERADE 的作用是把内网包源地址临时改成外网口地址。规则挂在 `ens160` 上，而实际出网口是 `ens33`，所以包离开 jumper 时源地址仍然是 `10.1.1.x` 或 `172.16.0.x`。外网回包的目标还是内网私有地址，互联网上根本没有这条回程路由，回包自然到不了 node。

## 5. 正确配置（最终生效）

在 jumper 上执行：

```bash
# 1. 清空 nat 表（干掉所有错误/重复规则）
iptables -t nat -F

# 2. 用正确的网卡名（ens33）重新添加 MASQUERADE
iptables -t nat -A POSTROUTING -o ens33 -j MASQUERADE

# 3. 确认规则已经挂在 ens33 上
iptables -t nat -S POSTROUTING

# 4. 确保内核转发开启（若未开）
sysctl -w net.ipv4.ip_forward=1
echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.conf
sysctl --system

# 5. 保存规则（防止重启丢失；CentOS 7 需先安装 iptables-services 才有此命令）
service iptables save
```

> 注意：`iptables -t nat -F` 会清空整个 nat 表，实验环境里方便，但正式服务器可能还有端口转发等其他规则。生产环境应优先用 `iptables -t nat -D POSTROUTING <规则编号>` 删除具体错误规则。

> 如果开着 firewalld，它可能在你重启服务或重载规则时覆盖 iptables 配置。实验里我确认 `systemctl status firewalld` 是 `inactive (dead)` 后才继续的。

> 如果系统不支持 `sysctl --system`，可以用 `sysctl -p` 重新加载配置。

> 在 RHEL 8 / CentOS Stream 等新发行版上，默认防火墙可能是 nftables 或 iptables-nft，`service iptables save` 不一定存在，持久化方式也不同，建议按发行版文档配置。

> 实验环境不加 `-s` 最省事，`-o ens33 -j MASQUERADE` 就够用。如果想更严谨，建议只转换内网来源，并且要同时覆盖两个内网段：
>
> ```bash
> iptables -t nat -A POSTROUTING -o ens33 -s 10.1.1.0/24 -j MASQUERADE
> iptables -t nat -A POSTROUTING -o ens33 -s 172.16.0.0/16 -j MASQUERADE
> ```
>
> 同理，`iptables -A FORWARD -j ACCEPT` 适合实验环境；正式环境建议按内网口到外网口放行，并只放行已建立连接的回程流量。
>
> ```bash
> iptables -A FORWARD -i ens36 -o ens33 -j ACCEPT
> iptables -A FORWARD -i ens37 -o ens33 -j ACCEPT
> iptables -A FORWARD -i ens33 -o ens36 -m state --state ESTABLISHED,RELATED -j ACCEPT
> iptables -A FORWARD -i ens33 -o ens37 -m state --state ESTABLISHED,RELATED -j ACCEPT
> ```

**在 node1/node2 上确认：**

```bash
# 网关指向 jumper 对应内网口的 IP；replace 可避免默认路由已存在时 add 报错
ip route replace default via 10.1.1.128    # node1
ip route replace default via 172.16.0.128  # node2
```

> 注意：`ip route add` / `ip route replace` 都是临时生效的，重启后就会丢失。要永久生效，需要把路由写进网卡配置文件（如 `/etc/sysconfig/network-scripts/route-<网卡名>`，把 `<网卡名>` 换成该 node 实际出网口的名称）或用 NetworkManager 配置。

配置完成后，再测试就一切正常了。

测试：

```bash
ping 8.8.8.8      # ✅ 通！
ping baidu.com    # ✅ 通！DNS 也 OK！
```

![c535cb4b-e7e2-4857-9c15-ebb0fca68bf9](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/c535cb4b-e7e2-4857-9c15-ebb0fca68bf9.png)

![414e4091-69c0-4fe6-a9ef-c5773378f3d2](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/linuxVMware%20%E4%BB%85%E4%B8%BB%E6%9C%BA%20%2B%20NAT%20%E6%A8%A1%E5%BC%8F%E4%B8%8B%20iptables%20%E8%BD%AC%E5%8F%91%E5%A4%B1%E8%B4%A5%E7%9A%84%E6%8E%92%E9%94%99%E5%85%A8%E8%BF%87%E7%A8%8B%EF%BC%88MASQUERADE%20%E6%8C%82%E9%94%99%E7%BD%91%E5%8D%A1%EF%BC%89/images/414e4091-69c0-4fe6-a9ef-c5773378f3d2.png)

测试时建议分两步看：

1. `ping 8.8.8.8` 通了，说明 NAT 转发没问题；
2. `ping baidu.com` 通了，说明 DNS 也没问题。

如果只通 IP 不通域名，先查 DNS，不要再回头怀疑 MASQUERADE。

测试结果：node1 可以正常连接到外网，node2 在这次测试中同样可以。实验成功，排错过程到此结束，有兴趣的朋友可以继续往下看避坑清单。

**重启后建议再验证一遍：**

```bash
sysctl net.ipv4.ip_forward
iptables -t nat -S POSTROUTING
```

**确认 MASQUERADE 真的匹配到了包：**

让 node1 持续 ping 的同时，在 jumper 上执行：

```bash
iptables -t nat -L POSTROUTING -n -v --line-numbers
```

如果 MASQUERADE 规则下面的 `pkts/bytes` 一直在涨，说明规则正在命中，NAT 已经生效；如果一直为 0，说明流量根本没走到这条规则上。

## 6. 避坑清单（收藏备用）

下次再遇到"内网通、外网不通"的 NAT 转发问题，按这个顺序查，**10 分钟定位**：

| # | 检查项 | 命令 | 期望结果 |
| --- | --- | --- | --- |
| 1 | 网卡列表 | `ip -br link` | 确认实际网卡名，别凭记忆写 |
| 2 | 内核转发是否开启 | `cat /proc/sys/net/ipv4/ip_forward` | 输出 `1` |
| 3 | 外网出口网卡是谁 | `ip route get 8.8.8.8` | 记住 `dev` 后面的网卡名 |
| 4 | MASQUERADE 是否挂在正确网卡 | `iptables -t nat -S POSTROUTING` | `-o` 后面必须是第 3 步的网卡名 |
| 5 | 是否有重复/冲突规则 | `iptables -t nat -S` | 只保留一条干净的 MASQUERADE |
| 6 | FORWARD 链是否放行 | `iptables -L FORWARD -n -v` | 有 ACCEPT 规则或 policy ACCEPT |
| 7 | firewalld 是否干扰 | `systemctl status firewalld` | 应为 `inactive (dead)` |
| 8 | 内网机器的网关 | `ip route \| grep default` | 指向 jumper 对应内网口 IP |
| 9 | DNS 是否配置 | `cat /etc/resolv.conf` | 有可用 `nameserver` |

> 补充：如果按上面查完还不通，大概率是**规则挂在了不存在的网卡上**——先 `ip link show` 确认所有网卡名，再回头核对第 3、4 步。这正是本文踩的坑。

## 7. 写在最后

这个实验，理论上非常容易，但我却折腾了好久——这里查查，那里看看，还截了图去问元宝。它先说我这里没问题、那里也没问题，接着又列了一堆排查顺序让我挨个试，结果一点用也没有；再追问，就说我配置重复了、写得不安全了、防火墙有问题……反正在它看来，我浑身都是毛病。

我当时急坏了，心想：老师讲课的时候根本没用到这么多服务，也没有让我配置什么服务项，就是简简单单的 `ping` 而已啊，它是不是在胡说八道？

后来实在无奈，我把 `ifconfig` 敲在终端里，一行一行盯着看。看着看着，目光停在了老师讲义里那行"内网流量转外网流量"上——咦，老师这里怎么用的是 **ens160**？我的网卡明明是 **ens33** 啊！

我想着想着就明白了：原来老师在机房用的是 88 网段（外网口 ens160、内网口 ens33），而我的环境和他不一样——我的外网口反而叫 ens33、内网口是 ens36/ens37，两边网卡的角色完全对调。环境不同，配置自然也不一样。而老师当时并没有强调"这里的配置要根据自己的环境修改"，再加上我以为命令是通用的，只看到一长串英文字母就大意了，于是问题就这样发生了。

想通之后，解决就非常快了。上午我还问过元宝"我明明和老师写的命令一样，怎么他的可以、我的不行"，它没有给出建设性建议，只是淡淡地说"老师已经演示无数遍了，你自己肯定环境不对"，再问哪里不对，就支支吾吾说不出所以然。

现在看来，"和老师写的一样"简直是一个笑话——尤其是在 Linux 里，**每一条语句都要明白它的含义**，不理解环境差异，就会闹问题、耽搁时间。

最后，希望大家看完这段错误经验后，能及时发现问题、纠正错误，节省宝贵时间。也想多说一句关于 AI 的看法：**不要尽信 AI**，那样还不如没有 AI。AI 更适合帮你核对思路、解释命令，而不是替你做第一步定位；在你连问题都还没找到时，它给的通用排查建议往往只会让问题继续打转。真正解决问题的关键，还是先靠自己的双手把环境看清楚。找到错误之后，AI 其实非常有用，但前提是**你自己先找到错误**。

希望这篇文章对你有所帮助。
