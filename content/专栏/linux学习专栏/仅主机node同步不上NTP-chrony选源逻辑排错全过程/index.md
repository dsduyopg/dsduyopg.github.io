# 仅主机 node 能 ping 通 jumper 却同步不上 NTP：chrony 选源逻辑排错全过程（删掉一行公网 pool 就好了）

> 跟着黑马课程做「时间同步」实验时的真实排错记录。现象：node1_copy（仅主机）能 ping 通 jumper，但 chrony 死活同步不上 NTP；同一台宿主机的 WSL 却好好的。查到最后，问题出在 `chrony.conf` 里一行公网 `pool` 上——删掉立刻恢复。
>
> 本文把每一步排查的命令、输出、判断依据都写全了，以后遇到「能 ping 通却同步不上时间」直接照这个流程走；也写给同样被这套拓扑坑过的同学。

@[toc]

## 0. 先看答案（赶时间的人只看这一节）

| 问题 | 答案 |
| --- | --- |
| 为什么同步不上 NTP | `chrony.conf` 里混配了公网源 `pool 2.centos.pool.ntp.org iburst`。仅主机节点没有公网出口，这个源永远不可达 |
| 为什么 ping 通但 NTP 不通 | ping jumper 是「本机到 jumper 自己」，不需要出公网；NTP 去公网 pool 要借道 jumper 的 NAT 转发，这条链路上 UDP 123 没放通 |
| 为什么 WSL 却可以 | WSL2 走宿主机自己的 NAT 出公网，和虚拟机所在的 VMnet 是两条完全独立的路径 |
| 为什么删掉公网 pool 就好了 | 配置里只剩一个可达的内网源，chrony 没有第二个源可比较，必然选中它 |
| 修复命令 | 删掉公网 pool 行 → `systemctl restart chronyd` → `chronyc sources` 看到 `^*` 即成功 |

```bash
# 修复前 /etc/chrony.conf（问题配置）
pool 2.centos.pool.ntp.org iburst   # ← 公网源，仅主机节点不可达，删掉它
pool 192.168.149.10 iburst          # ← 内网源（jumper 的 NTP），保留

# 修复后 /etc/chrony.conf（正确配置，仅主机节点只需这一行）
pool 192.168.149.10 iburst

# 重启并验证
systemctl restart chronyd
chronyc sources -v
```

`chronyc sources` 里看到行首是 `^*`（当前同步源）就是成功：

```text
MS Name/IP address         Stratum Poll Reach LastRx Last sample
^* 192.168.149.10               3     6    17    3  +535ns[+37us] +/- 133ms
```

## 1. 实验环境

这套拓扑沿用了之前 iptables 排错文章里的 jumper 网关机，外加一台 WSL 做对照组：

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

| 机器 | 网络模式 | 关键 IP | 角色 |
| --- | --- | --- | --- |
| jumper | VMnet8（NAT）+ VMnet2/VMnet3（仅主机） | `192.168.149.10` / `10.1.1.128` / `172.16.0.128` | 网关 + NTP 服务器（chronyd） |
| node1_copy | VMnet2（仅主机） | `10.1.1.1` | 出问题的节点 |
| node2_copy | VMnet3（仅主机） | `172.16.0.x` | 待同步节点（这次没涉及） |
| WSL2 AlmaLinux | 宿主机 NAT（Hyper-V 虚拟交换机） | 独立 | 对照组（它一切正常） |

> 网段以你虚拟网络编辑器里的实际配置为准。本实验里 chrony 源写的是 `192.168.149.10`（jumper 的 NAT 口），node1_copy 通过 jumper 内部转发可以直达。

## 2. 现象复现（问题长什么样）

### 2.1 node1_copy 上：ping 通

```bash
[root@node1 ~]# ping -c 2 192.168.149.10
PING 192.168.149.10 (192.168.149.10) 56(84) bytes of data.
64 bytes from 192.168.149.10: icmp_seq=1 ttl=64 time=0.5 ms   ← 网络是通的
64 bytes from 192.168.149.10: icmp_seq=2 ttl=64 time=0.4 ms
```

### 2.2 node1_copy 上：NTP 同步失败

```bash
[root@node1 ~]# chronyc sources
MS Name/IP address         Stratum Poll Reach LastRx Last sample
^? 2.centos.pool.ntp.org        3     6     0    -   ...
^? 2.centos.pool.ntp.org        3     6     0    -   ...
^? 2.centos.pool.ntp.org        3     6     0    -   ...
```

行首 `^?` 表示**不可达**。没有任何源被标成 `^*`，时间同步根本没起来。

### 2.3 对照：WSL 里同样混配公网源，却正常

```bash
# WSL2 (AlmaLinux) 里
chronyc sources
MS Name/IP address         Stratum Poll Reach LastRx Last sample
^* 2.centos.pool.ntp.org        2     6    377    3  +10ms[+9ms] +/- 30ms
```

同一份公网源，WSL 能用、虚拟机不能用——这就是整个问题的「别扭点」，也是排错的突破口。

## 3. 排错总思路：把链路分层，一层层排除

不要一上来就猜「是不是防火墙」「是不是 SELinux」。把整条链路拆成四层，从外到内排除：

```text
第 1 层  客户端（MobaXterm / 终端）     —— 它只是眼睛，不是手
第 2 层  服务端（jumper 的 NTP 服务）   —— 服务到底起没起？监听没监听？
第 3 层  中间路径（防火墙 / allow / NAT 转发）—— 请求到得了服务端吗？回包回得来吗？
第 4 层  源头配置（node1_copy 自己的 chrony.conf / 路由 / 网络模式）—— 它到底想连谁？
```

## 4. 排查过程（每一步：命令 + 输出 + 解读）

### 4.1 第 1 层：先排除客户端

- **怀疑**：现象是在 MobaXterm 里看到的，会不会是 MobaXterm 的问题？
- **排除**：MobaXterm 只是终端模拟器，只负责显示字符，不参与 NTP 同步。直接进 VMware 控制台操作，现象一样。
- **结论**：与客户端无关。`ping` 是在 node1_copy 里跑的，chrony 也是 node1_copy 里的服务，客户端连「手」都算不上。

> 教训：现象出现在哪个工具里，不等于问题出在哪个工具里。工具只是载体。

### 4.2 第 2 层：确认 jumper 的 NTP 服务到底通不通（关键一步）

**思路：先确认服务端是好的，再往下查。** 如果 jumper 的 NTP 服务本身没起，node 这边查破天也没用。

#### 4.2.1 宿主机上，用 w32tm 对 jumper 三个 IP 发 NTP 探测

Windows 自带 `w32tm /stripchart` 可以当 NTP 客户端发探测包：

```bash
w32tm /stripchart /computer:192.168.149.10 /samples:3 /dataonly
w32tm /stripchart /computer:10.1.1.128    /samples:3 /dataonly
w32tm /stripchart /computer:172.16.0.128  /samples:3 /dataonly
```

参数含义：`/stripchart` 持续发 NTP 请求并显示往返耗时；`/computer:` 目标服务器；`/samples:3` 发 3 个包；`/dataonly` 只显示数据不打印标题。

**输出**（三个 IP 都能回包，这里以其中一个为例）：

```text
10:00:00, +00.0000000s
10:00:01, +00.0052340s
10:00:02, +00.0048230s
```

有回包 = UDP 123 端口通、chronyd 在监听。

#### 4.2.2 再从 WSL 里发一个「手工构造」的原始 NTP 请求

不用 `ntpdate`（有些系统没装），直接用 Python 构造一个标准 NTP 请求包（48 字节，首字节 `0x1b`）：

```bash
wsl -d AlmaLinux-10 -- bash -lc "
python3 - <<'PY'
import socket
pkt = b'\x1b' + 47 * b'\0'          # 标准 NTP 客户端请求报文，48 字节
for host in ['192.168.149.10', '10.1.1.128']:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(4)
    try:
        s.sendto(pkt, (host, 123))
        data, addr = s.recvfrom(512)
        print(host, 'OK', len(data), 'bytes from', addr)
    except Exception as e:
        print(host, 'FAIL', repr(e))
    finally:
        s.close()
PY"
```

**输出**：

```text
192.168.149.10 OK 48 bytes from ('192.168.149.10', 123)
10.1.1.128     OK 48 bytes from ('10.1.1.128', 123)
```

- 请求 48 字节、响应也是 48 字节 = 标准 NTP 协议握手成功；
- `0x1b` = 版本 3 + 客户端模式（mode 3），这是最基础的 NTP 请求头。

- **结论：jumper 的 chronyd 服务正常，三个网卡口都在监听 UDP 123，而且对宿主机、WSL 这些来源都放行。服务端没有问题。**

### 4.3 第 3 层：模拟「仅主机网段」的源 IP 去访问，排除防火墙 / allow 在拦

- **新问题**：上面测的是宿主机和 WSL 的来源，它们都不在 `10.1.1.0/24` 这个仅主机网段。万一 jumper 的 firewalld 或 chrony `allow` 列表只放行了某些来源，node 那边的请求还是会被拦。
- **办法**：在宿主机上**临时加一条路由**，让自己能以 `10.1.1.3`（仅主机网段的源地址）访问 `192.168.149.10` 的 123 端口，模拟 node 的视角。测完立刻删掉路由，不留后患。

```powershell
# 宿主机 PowerShell：临时路由 + 绑定源地址发 NTP
$ErrorActionPreference='Stop'
try {
    route.exe add 192.168.149.10 mask 255.255.255.255 10.1.1.128 metric 1 if 11
    $s = [System.Net.Sockets.Socket]::new([System.Net.Sockets.AddressFamily]::InterNetwork,
         [System.Net.Sockets.SocketType]::Dgram, [System.Net.Sockets.ProtocolType]::Udp)
    $s.Bind([System.Net.IPEndPoint]::new([System.Net.IPAddress]::Parse('10.1.1.3'), 0))  # 源地址
    $pkt = [byte[]]::new(48); $pkt[0]=0x1b
    $ep = [System.Net.IPEndPoint]::new([System.Net.IPAddress]::Parse('192.168.149.10'), 123)
    $s.SendTo($pkt, $ep) | Out-Null
    $s.ReceiveTimeout = 3000
    try {
        $buf = New-Object byte[] 512
        $n = $s.Receive($buf)
        "NTP from 10.1.1.3 to 192.168.149.10: OK ($n bytes)"
    } catch {
        "NTP from 10.1.1.3 to 192.168.149.10: FAIL - $($_.Exception.Message)"
    }
    $s.Close()
} finally {
    route.exe delete 192.168.149.10 2>&1 | Out-Null   # 用完即删
}
```

**输出**：

```text
NTP from 10.1.1.3 to 192.168.149.10: OK (48 bytes)
```

- **结论：从仅主机网段发过去的 NTP 请求，jumper 也回包。防火墙没拦来源，chrony 的 allow 列表也覆盖了。中间路径没问题。**

> 这一步的价值：把「服务端对 node 这个来源到底放不放行」这个问题彻底钉死了，后面就不需要再怀疑 firewalld / allow / SELinux。

### 4.4 第 4 层：收窄到源头——node1_copy 自己的 chrony 配置

服务端正常、路径正常，问题必然在 node1_copy 自己的配置上。直接看配置文件：

```bash
[root@node1 ~]# grep -vE '^\s*(#|$)' /etc/chrony.conf
pool 2.centos.pool.ntp.org iburst      # ← 公网源
pool 192.168.149.10 iburst             # ← 内网源（jumper）
```

**问题浮出水面：配置里「公网源 + 内网源」混配，而 node1_copy 是仅主机模式，出不了公网。**

顺手确认服务本身是活的（排除「chronyd 没启动」的可能）：

```bash
[root@node1 ~]# systemctl is-active chronyd
active
[root@node1 ~]# systemctl is-enabled chronyd
enabled
```

服务正常，问题就是「源选不上」。

### 4.5 验证：删掉公网 pool 那一行，立刻恢复

```bash
[root@node1 ~]# sed -i '/2.centos.pool.ntp.org/d' /etc/chrony.conf   # 或用 vim 删
[root@node1 ~]# systemctl restart chronyd
[root@node1 ~]# chronyc sources -v
MS Name/IP address         Stratum Poll Reach LastRx Last sample
^* 192.168.149.10               3     6    17    3  +535ns[+37us] +/- 133ms
[root@node1 ~]# timedatectl
               Local time: ...
               ...
         System clock synchronized: yes     ← 出现 yes，同步成功
```

- 行首 `^*` = 当前同步源（最准的那个）；
- `System clock synchronized: yes` = 系统时钟已由 chrony 接管校准。

**问题解决。** 但如果你以为到此为止，那就亏了——真正值钱的是下面这个问题。

## 5. 为什么删掉一行就好了？（核心原理，三个原因叠加）

### 5.1 原因一：仅主机节点没有公网出口，公网源「永远不可达」

node1_copy 是**仅主机模式**（VMnet2），这种虚拟网络默认**没有 DHCP、没有 NAT、没有公网出口**。它想访问公网，唯一的办法是借道 jumper 的 NAT 转发（就是之前 iptables 排错文章里配的那套 MASQUERADE）。

而实测这条转发链路上 **UDP 123 没有放通**——所以 `2.centos.pool.ntp.org` 对 node1_copy 来说不是「暂时不通」，是**拓扑上就没有这条路**。

**重点：ping 通和 NTP 通，是两码事。**

```text
node1_copy → ping jumper 192.168.149.10
  = 本机到「jumper 自己」，jumper 内部转发即可，不需要出公网 → 通

node1_copy → NTP 去 2.centos.pool.ntp.org
  = 本机 → jumper → NAT 转发 → 公网 → 回包原路返回
    UDP 123 在转发链路上没放通 → 不通
```

### 5.2 原因二（重点中的重点）：chrony 是「平滑优先」，不是「故障切换」

这是整个排错里最反直觉、最值得记住的一点。

**chrony 的首要目标，是让系统时钟尽可能平滑、误差尽可能小，而不是让「源切换」发生得最快。**

chrony 官方 FAQ 专门有一节 *"An unreachable source is selected?"*（为什么选中了一个不可达的源？），原文大意：

> 当最佳源（`*` 标记的那个）变得不可达时，chronyd **不会立即切换到第二好的源**，目的是尽量减少时钟误差。只要基于之前测量得出的误差估计（root distance）仍然小于第二个源的误差估计，并且两个源的测量区间还有重叠，它就会让时钟继续自由运行（free-run）。如果第一个源明显比第二个准，可能**需要很多小时才会切换**，具体取决于轮询间隔（poll interval）。

翻译成人话：

1. 公网 pool 一开始是可达的（或 chrony 假定它可达），chrony 把它当「最佳源」；
2. 后来它变得不可达，但 chrony 觉得：我的时钟误差还在可接受范围内，何必冒险去切一个误差可能更大的源？**先让时钟自己跑着，继续等原源**；
3. 于是它就一直等、一直重试，而不是「啪」地一下切到 jumper。

**所以 node1 不是「找不到」jumper 的 NTP，而是 chrony 主观上「不想切」。**

### 5.3 原因三：`pool` 是动态源，会不断「换人」，让选择过程更不稳定

`pool` 和 `server` 有本质区别：

| 指令 | 行为 |
| --- | --- |
| `server 1.2.3.4` | 固定一台服务器，就那一台，没得选 |
| `pool ntp.xxx.org` | 通过 DNS 解析出**一堆**服务器地址，在其中动态挑选、替换 |

`2.centos.pool.ntp.org` 是 CentOS 的公共 NTP 池，背后有几十上百台服务器。你写的「一行 pool」，实际是「一堆公网候选 + 一个内网候选」：

```text
pool 2.centos.pool.ntp.org iburst   →  几十个公网候选（全部不可达，而且会被不断替换）
pool 192.168.149.10 iburst          →  一个内网候选（可达，但被晾在一边）
```

那些公网候选全不可达，chrony 还会**不停地用新解析出来的地址替换旧的、反复重试**——选择过程一直处于不稳定状态，本应「躺赢」的本地源 `192.168.149.10` 也就一直没有被稳定地选为 `^*`。

### 5.4 为什么删掉那行就立刻 OK？

删掉公网 pool 后，配置里只剩一个源：

```text
pool 192.168.149.10 iburst
```

**没有第二个源可以比较，也就不存在「要不要切换」的问题**——chrony 没有别的候选，只能选它，于是立刻 `^*`。

### 5.5 为什么 WSL 可以？（对照实验的真正价值）

WSL2 和虚拟机的网络是**两条完全独立的路**：

```text
node1_copy：VMnet2 仅主机 → 借道 jumper 的 NAT 转发 → 公网（UDP 123 不通）→ 失败
WSL2     ：Hyper-V 虚拟交换机 → 宿主机（Windows）自己的 NAT → 公网（通）    → 成功
```

WSL2 走的是宿主机自己的 NAT 出口，**根本不经 jumper**，所以它访问公网 NTP pool 是通的，混用公网源当然没问题。

**这也正是「对照组」的价值**：WSL 能通，恰恰证明了问题不在公网 NTP 服务器、不在宿主机网络，而在**虚拟机那套拓扑的出公网路径**上。对照实验如果只记「一个通一个不通」就完了，等于白做；要问「对照组到底在对照什么」，结论才出得来。

## 6. 怎么彻底修好 & 加固

### 6.1 仅主机节点：只留内网源（本次修复）

```bash
# /etc/chrony.conf（node1_copy 正确形态）
pool 192.168.149.10 iburst
systemctl restart chronyd
chronyc sources -v
```

### 6.2 以后 node2_copy 怎么做？

同理，只写它所在网段对应的 jumper 内网口：

```bash
# node2_copy（172.16.0.x 网段）
pool 172.16.0.128 iburst
```

**只写内网源，别写公网 pool**——这是仅主机节点的铁律。

### 6.3 如果非要保留公网源做冗余，按推荐程度排序

| 方案 | 做法 | 说明 |
| --- | --- | --- |
| ① 修好出公网路径（最彻底） | 放通 jumper 转发链路上的 UDP 123（firewalld + iptables FORWARD 规则） | 公网源本身可达，就没有「切不切」的纠结了 |
| ② 给内网源加 `prefer` | `pool 192.168.149.10 prefer iburst` | 让内网源优先被选中，公网源只做兜底 |
| ③ 限制不可达源的存活时间 | 给公网源加 `maxunreach 600` | 需要 chrony 4.8+；超过时限的不可达源不再参与选择，强制切走 |

```bash
# 方案②示例
pool 192.168.149.10 prefer iburst
pool 2.centos.pool.ntp.org iburst maxsources 2
```

## 7. 常用命令速查表（以后直接抄）

### 7.1 chrony 状态查看

```bash
chronyc sources          # 源列表（关键命令，看 ^* ^? ^+）
chronyc sources -v       # 详细版
chronyc tracking         # 当前同步状态、误差、频率偏移
chronyc activity         # 每个源的在用/在线状态
chronyc -a makestep      # 立即大幅校时（漂移大时用）
timedatectl              # 看 System clock synchronized 是不是 yes
```

### 7.2 `chronyc sources` 输出列含义（这次排错靠它）

```text
MS Name/IP address         Stratum Poll Reach LastRx Last sample
^* 192.168.149.10               3     6    17    3  +535ns[+37us] +/- 133ms
^? 2.centos.pool.ntp.org        3     6     0    -   ...
```

| 列 | 含义 | 怎么看 |
| --- | --- | --- |
| M（标记位） | `^` 服务器，`=` 对等节点，`#` 本地时钟 | 服务器源就是 `^` |
| S（状态） | `*` 当前同步源（最优）；`+` 可用的候选项；`-` 不可用（测量中）；`?` 不可达；`x` 时间错误；`~` 样本乱序 | **看到 `^*` 才说明同步成功；全是 `^?` 就是源不可达** |
| Stratum | 时钟层级，越小越准（1 最准，16 不可用） | 3 代表这台是从 stratum 2 同步来的，正常 |
| Poll | 轮询间隔（秒，以 2 为底的对数） | 6 = 64 秒轮询一次 |
| Reach | 最近 8 次轮询的到达率（八位二进制转八进制） | **0 = 最近 8 次全没响应；377 = 全部成功**；17 这种小数字 = 到达率极差 |
| LastRx | 距最后一次收到响应多少秒 | `-` 表示从未收到过响应 |
| Last sample | 最近一次测量的偏移 ± 误差 | 正负号 + 数值是偏差，越小越准 |

### 7.3 服务管理

```bash
systemctl status chronyd
systemctl is-active chronyd
systemctl restart chronyd
systemctl enable --now chronyd
```

### 7.4 排查网络路径

```bash
ping -c 3 192.168.149.10                 # ICMP 通不通
ip route                                 # 路由表，看默认路由指向哪
ss -unlp | grep 123                      # 本机 UDP 123 有没有监听
chronyc sources                          # 源状态（最快判断）
```

## 8. 如果现象不一样：对照表（按你的现象找答案）

| 你看到的现象 | 大概率原因 | 查什么 |
| --- | --- | --- |
| `chronyc sources` 全是 `^?` | 源不可达：公网源但没公网出口 / IP 写错 / 防火墙拦 | 见 §4.2~4.3；直接 `ping` 那个源 IP |
| 只有一个源，状态 `^?` | 源地址写错、服务端没起、防火墙拦 | `ss -unlp | grep 123`、`ping` 源 IP、关防火墙试 |
| 有 `^+` 但没有 `^*` | 有候选源，但误差/层级不够，选源中 | `chronyc tracking` 看误差；给源加 `prefer` |
| `chronyd` 未运行 | 服务没启动 | `systemctl start chronyd && systemctl enable chronyd` |
| 同步成功但时间还是不准 | 漂移太大、源层级太高 | `chronyc -a makestep`；换个 stratum 更低的源 |
| WSL 正常、虚拟机不行 | 虚拟机出公网路径问题（NAT/仅主机拓扑） | 对照 §5.5，查虚拟机到公网的转发链 |
| 所有机器都不同步 | jumper 自己的 NTP 服务/时间有问题 | 在 jumper 上 `chronyc tracking`、`ss -unlp | grep 123` |

## 9. 复习要点（避坑清单）

1. **分层排错**：客户端 → 服务端 → 中间路径 → 源头配置，一层层排除，别上来就猜防火墙/SELinux。
2. **「ping 通」≠「服务通」**：ping 走 ICMP，NTP 走 UDP 123，两条路径完全可能一个通一个不通。
3. **仅主机/NAT 节点的「出公网路径」要单独确认**：拓扑上没有公网出口时，一切公网源都是「不可达」的代名词。
4. **chrony 选源是「平滑优先」不是「切换优先」**：不可达的源不会立刻被替换，可能要等很多小时；别对着 `^?` 干等，直接查配置。
5. **`pool` 是动态源**：一个 pool 背后是几十台服务器，不可达时会不断替换，别把它当一台 `server` 来理解。
6. **WSL 通 ≠ 虚拟机通**：WSL2 走宿主 NAT，虚拟机走 VMnet，两条路互不相干；对照实验要看懂对照组到底在对照什么。
7. **仅主机节点的时间同步，直接指向内网 NTP 服务器**：`pool 192.168.149.10 iburst`，一行搞定，别写公网源。
8. **修复后一定要验证**：`chronyc sources` 出 `^*`、`timedatectl` 显示 `System clock synchronized: yes`，才算真的修好。

---

**参考**：chrony 官方 FAQ「An unreachable source is selected?」<https://chrony-project.org/faq.html>

> 最后说句题外话：这次排错最有价值的地方，不是「删了一行配置」，而是搞懂了 chrony 的设计哲学——**时间同步系统里，稳定比反应快更重要**。很多「看起来不合理」的行为，背后都有它自己的设计理由。理解设计意图，比记住命令本身，能让你走得更远。
