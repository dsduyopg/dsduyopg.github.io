---
comments: true
giscusMapping: "og:title"
utterancesIssueTerm: "og:title"
title: "类若依项目低成本改造（中）：从本机到服务器，把中州养老部署上线"
slug: "zzyl-r2-server-deploy"
date: 2026-11-06
lastmod: 2026-11-06
draft: false
ShowToc: false
description: "把类若依（中州养老）项目从本机搬到三台虚拟机服务器：Maven 打 jar/war、JDK 11 与 Tomcat、Nginx 反向代理、BIND 正反解析，附 SELinux 403/502 与 DNS 三个错的完整排错过程。"
tags: ["Linux", "Nginx", "Tomcat", "MySQL", "Redis", "SELinux", "DNS"]
---

{{< toc >}}

> **前言**
>
> 这是“类若依项目低成本改造”系列的第二篇。**第一篇**在本机把后端、前端，以及两个外部依赖——对象存储（Cloudflare R2）和大模型（商汤日日新）——全部跑通；**本篇**把整套服务搬到服务器：三台 Linux 分工，打 jar 和 war 两种包，配 Nginx 反向代理，最后让域名解析生效。**第三篇**再写后期的日志与运维。
>
> 这一篇的难点不在写代码，而在“装完之后跑不起来”：端口放行了却返回 403、标签打完了却 502、`dig` 配完仍然解析不出来。正文按我实际动手的顺序写，每层做完给一个验收点，踩过的坑原样保留。

部署真正费时间的从来不是“装软件”，而是装完之后页面打不开的那一段。我这次踩的坑集中在两处：**SELinux 与防火墙的边界**，以及 **DNS 的细枝末节**。前者会让“端口明明放行了、进程也在跑”的服务返回 403 或 502；后者会因为一个文件名、一个单词、一个权限位，让整套解析直接失效。

行文顺序和我实际动手的顺序一致：先定节点分工，再按数据层 → 应用层 → 接入层 → DNS 推进。每做完一层给一个**验收点**，通过了再往下走。这是我这次最实在的体会——跳着做，出了问题根本说不清是哪一层坏的。

**阅读约定**

- 命令前会标节点，例如「node2 执行」；没标的说明三台都要做。
- `<数据库密码>`、`<Redis密码>`、`/path/to/xx.jar` 这类尖括号和示例路径是要替换的占位符，复制时别原样留着。
- IP、主机名、域名以我的实验环境为例：`192.168.88.170`~`172`，`node1.itacast.cn`，DNS 用域名 `node1.com`。你按自己的环境替换。
- 系统是 AlmaLinux 9：包管理 `dnf`，防火墙 `firewalld`，SELinux 默认 enforcing。

## 0. 先把三台机器的分工钉死

| 节点 | IP | 角色 | 主要软件 |
| --- | --- | --- | --- |
| node1 | 192.168.88.170 | 接入层 | Nginx（静态页 + 反向代理）、named（DNS） |
| node2 | 192.168.88.171 | 数据层 | MySQL 8、Redis、chrony（时间源）、日志盘 |
| node3 | 192.168.88.172 | 应用层 | JDK 11 + jar、Tomcat + war |

请求链路是这样的：

```text
浏览器 ──> node1:80 (Nginx)
             ├── /            ──> /var/www/dist   静态页面
             └── /prod-api/   ──> node3:8080/zzyl-admin   反向代理

node3（jar 或 war）
   ├──> node2:3306  MySQL
   ├──> node2:6379  Redis
   └──> 外网：R2 对象存储、商汤人脸识别

时间同步：node1、node3 ──> node2（chrony 服务端）
```

**为什么我的节点划分和指导书不一样。** 第一次实验我是拿 node2 当应用机的，做第二次时没仔细看要求，等发现时环境已经铺开了，硬改回去成本太高，就“将错就错”重新定义了一套分工：node2 只做数据和时钟，应用全压 node3，接入和 DNS 给 node1。为了不再把自己绕晕，我把这套分工写在纸上贴在屏幕边，跟指导书对不上的地方也标出来。后面每次敲命令前先扫一眼那张纸，“是哪台机器”这个问题就再没纠结过。

**实施顺序与验收点**

| 顺序 | 在哪台 | 做什么 | 通过标准 |
| --- | --- | --- | --- |
| 1 | 三台 | 主机名、`/etc/hosts`、SSH 免密、看清防火墙与 SELinux | 三台互 ping 都通、ssh 免密可登 |
| 2 | node2 | MySQL、导数据、Redis、chrony、日志盘 | node3 上能连 3306 和 6379 |
| 3 | node3 | 打包、JDK 11、jar / war 启动 | 本机 8080 打开正常 |
| 4 | node1 | 前端 dist、Nginx、SELinux 放行 | 浏览器进首页，接口有数据 |
| 5 | node1 | DNS 正向/反向解析 | `dig` 正常、域名可访问 |

先把“每层做完怎么算过”想清楚，比装完十来个软件再一起调要省事得多。

## 1. 三台都要做的基础配置

### 1.1 主机名与 `/etc/hosts`

三台机器 IP 依次 `192.168.88.170`、`171`、`172`，主机名 `node1`、`node2`、`node3`。先设主机名（每台执行一次，把 `node1` 换成当前节点）：

```bash
hostnamectl set-hostname node1
```

再配 `/etc/hosts`。不用一台一台 `vim` 敲，一条 `sed` 就能把三条解析记录一次写好，三台机器复用同一条命令：

```bash
sed -i -e '$a 192.168.88.170 node1 node1.itacast.cn\n192.168.88.171 node2 node2.itacast.cn\n192.168.88.172 node3 node3.itacast.cn' -e '3,$d' /etc/hosts && cat /etc/hosts
```

![执行 sed 后 /etc/hosts 的结果](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/c679a2d0-ab40-4dc3-9a10-0f0f7761020f.png)

（我最初贴出来的那条命令末尾多了一个单引号，`/etc/hosts' &&` 这样是跑不过去的，已经改掉了。）

这条命令好在**幂等**：无论跑几次，最终 `hosts` 都是那三行，不会越跑越多，反复重做实验的时候特别省心。但它的两个 `sed` 表达式**顺序不能换**，这是本篇第一个、也是当时最让我困惑的坑：

- `$a 文本`：在文件最后一行之后追加内容（`$` 表示最后一行，`a` 表示追加）；
- `3,$d`：删除第 3 行到文件末尾。

我“先删后加”和“先加后删”都试过。执行 `sed -e '3,$d' -e '$a 文本'` 时，第一次几乎一定失败，`hosts` 里只剩前面两行；第二次再跑反而成功了。原因在 `sed` 的处理方式上：

1. `sed` 逐行读入，对每一行按顺序执行所有命令；
2. `d` 会把当前行删掉并**立刻结束这一轮循环**，它后面的命令对这一行不再执行；
3. 第 3 行到末尾都被 `d` 匹配，最后一行自然也在其中——于是排在 `d` 后面的 `$a` 永远等不到执行机会；
4. 第二次跑时文件只剩两行，`3,$` 匹配不到任何行，`d` 不触发，最后一行才轮到 `$a` 执行，看起来就“第二次成功了”。

而 `a` 追加的文本是**排队输出**的：先把文本排进输出队列，等这一轮结束时再打印。所以只要 `$a` 排在 `d` 前面，就算这一行随后被 `d` 删掉，排队的文本依然会输出——这正是“先加后删”能成立的原因。

> **坑：** `d` 是“终止本轮”而不是“继续往下执行”。同一个 `sed` 里既有 `d` 又有 `a`/`i`/`c` 时，先想清楚谁在前。
>
> **提示：** 命令里的 `3` 不是固定的——看你 `hosts` 里第一条要清掉的旧记录在第几行，就换成几，例如 `5,$d`。

配置完验证：

```bash
getent hosts node1 node2 node3
ping -c 1 node2
```

顺手提一句：如果你的旧记录不是从第 3 行开始、而是东一段西一段散着，别硬拼 `sed`，整份重写更稳。我保留这条 `sed` 是因为它能在三台机器上原样复用，改一次跑三台。

### 1.2 SSH 免密

免密这一步没什么新东西，但可以很省事。常规流程是每台机器各 `ssh-keygen`、各自 `ssh-copy-id`，还要一路敲 `yes`。用一条循环命令，一次把公钥推到三台：

```bash
ssh-keygen -f ~/.ssh/id_rsa -P '' -q && for ip in 192.168.88.17{0..2}; do echo "正在推送到 $ip ..."; sshpass -p '123456' ssh-copy-id -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa.pub $ip; done
```

![一条循环命令把公钥推到三台机器](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/332e90a0-5a91-47e9-b922-a73c8598d4b2.png)

到 node2 上看一眼 `authorized_keys`，能查到刚推过去的公钥就说明成了：

```bash
cat ~/.ssh/authorized_keys
```

![node2 上确认公钥已写入](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/1561875b-6414-4b73-aa1c-fceba14e629c.png)

> **坑：** 这条命令**不幂等**。`ssh-keygen -f ~/.ssh/id_rsa` 遇到已存在的同名文件会重新生成，旧私钥就被覆盖，之前配好的免密全白费。跑之前先 `ls -l ~/.ssh/id_rsa` 确认有没有密钥、是不是你要用的那一把。
>
> **提示：** `sshpass -p '123456'` 把密码明文写在命令行里，只适合实验环境。生产上老老实实 `ssh-copy-id` 交互输入，或者上密钥托管。

说实话，这一行命令的价值不在“技术含量”，而在于免去三台机器来回翻上键、敲 `yes` 的烦躁。免密通了以后，往 node1 传 `dist`、往 node3 传 `jar` 都是一条 `scp` 的事。

### 1.3 防火墙与 SELinux：先把“两道门”分清

这一节是后面所有 403、502 的根源。**firewalld 和 SELinux 管的是两件不同的事**，很多人（包括当时的我）只放行了端口，然后对着“端口通了但服务报错”百思不得其解：

| 门 | 管什么 | 典型表现 | 怎么开 |
| --- | --- | --- | --- |
| firewalld | 外部能不能连上这个**端口** | 浏览器一直转圈、`curl` 超时 | `firewall-cmd --add-port` |
| SELinux | 进程能不能**读这个文件 / 连这个端口** | 403 Forbidden、502 Bad Gateway，端口和进程都正常 | `semanage fcontext`、`setsebool` |

判断依据是日志：

```bash
# 看最近的 SELinux 拒绝记录
ausearch -m avc -ts recent
grep denied /var/log/audit/audit.log | tail -n 20
```

真正的痛点在“该设什么标签、该开哪个布尔值”。以前我每次都去查 man、问 AI，参数又长又记不住。后来发现两个命令就够了：

```bash
# 查所有 SELinux 类型（标签），筛出和当前服务相关的
seinfo -t | grep httpd
# 查所有布尔值，筛出和当前服务相关的开关
seinfo -b | grep httpd
```

![用 seinfo -t 查服务相关的标签](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/633b62bf-eb7d-4bc5-ad72-715972111779.png)

![用 seinfo -b 查服务相关的布尔值](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/f908661d-bbda-4e55-b6ce-736cbf68e43a.png)

两个命令配上 `grep`，比死记参数强太多：先看有哪些候选，再决定打哪个标签、开哪个开关，不用再背。我把这段提前讲，是因为等真到 §4.3 配 Nginx 报 403 的时候，你会感谢自己先认识了这两个命令。

几条常用命令，先放这里备查：

```bash
getenforce                        # 当前模式：Enforcing / Permissive
ls -Z /var/www/dist               # 看文件的 SELinux 上下文
semanage fcontext -l | grep httpd # 看已有的路径规则
semanage fcontext -a -t httpd_sys_content_t '/var/www/dist(/.*)?'
restorecon -Rv /var/www/dist      # 让新标签真正生效
setsebool -P httpd_can_network_connect on   # 允许 httpd 主动外连（-P 持久化）
```

> **提示：** 如果提示 `semanage: command not found`，先装 `dnf install -y policycoreutils-python-utils`。
>
> **提示：** `semanage fcontext` 只是**写规则**，不动文件。很多人加完规则就以为生效了，其实还得 `restorecon` 把规则真正盖到文件上（或者 `touch /.autorelabel` 后重启）。这是 SELinux 最常见的“我明明设了却没反应”。

## 2. 数据层部署（node2）

node2 承担四件事：MySQL、Redis、时间源、日志盘。MySQL 和 Redis 在第一篇已经装过一遍，这里不再从零讲，只给“够用”的命令，重点补**跨机部署新增的那部分**：远程账号、监听地址、防火墙，以及 node3 到底能不能连上——这才是这次真正会卡人的地方。

### 2.1 MySQL 8：能启动不等于能被远程连上

安装（MySQL 官方仓库，AlmaLinux 9 用 el9 的 repo 包）：

```bash
dnf install -y https://dev.mysql.com/get/mysql80-community-release-el9-1.noarch.rpm
dnf install -y mysql-community-server
systemctl enable --now mysqld
systemctl status mysqld --no-pager
```

初始密码在日志里，取出来做安全初始化：

```bash
grep 'temporary password' /var/log/mysqld.log
mysql_secure_installation
```

接下来是这次新增的关键点。后端跑在 **node3**，数据库在 **node2**，所以必须：

1. 建**远程可登录的账号**，不能只用 `root@localhost`；
2. 让 MySQL 监听 `0.0.0.0`，而不是只监听回环；
3. firewalld 放行 3306；
4. 建库、授权，最后**从 node3 实测**。

```sql
CREATE DATABASE IF NOT EXISTS `ry-zzyl`
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'zzyl'@'192.168.88.%' IDENTIFIED BY '<数据库密码>';
GRANT ALL PRIVILEGES ON `ry-zzyl`.* TO 'zzyl'@'192.168.88.%';
FLUSH PRIVILEGES;
```

```ini
# /etc/my.cnf.d/mysql-server.cnf
[mysqld]
bind-address = 0.0.0.0
```

```bash
systemctl restart mysqld
firewall-cmd --permanent --add-port=3306/tcp && firewall-cmd --reload
ss -lntp | grep ':3306'          # 应看到 0.0.0.0:3306 或 *:3306
```

> **坑：** `ss` 只显示 `127.0.0.1:3306` 时，node3 怎么连都是 `Can't connect`。这不是密码错，是根本没监听外网地址。

最后一定**从 node3** 实测一次，别在 node2 上试通就算完：

```bash
mysql -h node2.itacast.cn -P 3306 -u zzyl -p -e "select 1;"
```

返回 `1` 就说明账号、权限、网络三道都通了。

### 2.2 导入基础数据

把课程给的 `ry-zzyl_20240913.sql` 传到 node2 再导入：

```bash
mkdir -p /usr/local/zzyl_project/sql_data && cd /usr/local/zzyl_project/sql_data
mysql -uroot -p ry-zzyl < ry-zzyl_20240913.sql
```

导入完先别急着走，核对一下表：

```sql
USE `ry-zzyl`;
SHOW TABLES;
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'ry-zzyl';
```

> **提示：** SQL 文件里如果自带 `CREATE DATABASE`，前面就不用先建库。“命令没报错”也不等于数据完整：表少了，要么是 `sql_mode` 拦了，要么是导入中途断了，看 `SHOW WARNINGS` 和日志。

### 2.3 Redis：bind、密码、protected-mode 三件事

```bash
dnf install -y redis
systemctl enable --now redis
```

`/etc/redis/redis.conf` 里三处要看得懂：

```conf
bind * -::*
protected-mode yes
requirepass <Redis密码>
```

- `bind * -::*`：监听所有 IPv4 与 IPv6 地址，否则 node3 连不进来；
- `requirepass`：访问密码，后端配置里要写同一个；
- `protected-mode yes`：没有密码、且不是只绑回环时，Redis 会拒绝外部连接。**设了密码就可以保留 yes**，不必为了连通把它关掉。

```bash
systemctl restart redis
firewall-cmd --permanent --add-port=6379/tcp && firewall-cmd --reload

redis-cli -a '<Redis密码>' PING                        # node2 本机
redis-cli -h node2.itacast.cn -a '<Redis密码>' PING    # 在 node3 上执行
```

> **坑：** 两个 `PONG` 才算通。本机 `PONG`、远端 `Connection refused`，八成是 `bind` 或 firewalld；远端 `DENIED Redis is running in protected mode`，就是密码没配上。

### 2.4 chrony：让 node2 当时钟源头

时间不同步带来的问题很隐蔽——JWT 校验失败、验证码“刚发就过期”、日志时间对不上。三台机器时间必须一致。我让 node2 当时间源，node1、node3 都指向它（本来 NTP 该放 node1，前面说过，节点是我自己重排的）。

**node2（服务端）**，改 `/etc/chrony.conf`，把允许的网段打开：

```conf
# 允许本网段客户端来同步
allow 192.168.88.0/24
# 自己的时钟等级：网络里没有上游时钟时用它当源
local stratum 10
```

![chrony 服务端放开网段](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/8c427013-99cd-4b11-8d08-acaf85cf027d.png)

![chrony 配置确认](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/0d75ddc3-c184-4e8f-882c-ef0f9e276393.png)

![chrony 服务启动](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/8a308eab-cd49-4a32-8283-4a4639359d0d.png)

**node1 / node3（客户端）**，把上游指向 node2 就行，原来那些 `pool 2.centos.pool.ntp.org` 注释掉或替换：

```conf
pool node2.itacast.cn iburst
```

![客户端 pool 指向 node2](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/199a0af5-e6bc-4ab1-abb5-f5707349bb4f.png)

验证：

```bash
systemctl restart chronyd
chronyc sources
```

> **坑：** 刚改完配置，`chronyc sources` 经常显示 `^?`——表示这个源还没用上（不可达，或还没完成首次同步）。我一开始看到 `^?` 以为配错了，其实先 `systemctl restart chronyd`，再等十几秒到一分钟，就会变成 `^*`（当前同步源）和 `^+`（备用源）。配置没动过却一直 `^?`，才需要回头查网络和 `allow`。

三台都确认同步后 `date` 的输出应该基本一致，这一层就算过了。

### 2.5 日志数据盘

日志单独挂一块盘，计划是 `/mnt/zzyl_logs`，第三篇做日志同步的时候会用到：

```bash
mkdir -p /mnt/zzyl_logs
blkid                                   # 找到新盘，比如 /dev/sdb1
echo '/dev/sdb1 /mnt/zzyl_logs xfs defaults 0 0' >> /etc/fstab
mount -a && df -h /mnt/zzyl_logs
```

本篇只把目录和挂载准备好，具体怎么收集、怎么轮转、怎么同步，留到第三篇。

## 3. 应用层部署（node3）

这一层是把本机跑通的服务真正搬上服务器的关键：先把包打好（jar 和 war 两种都做），再装 JDK 11，最后分别验证。这里的问题最“防不胜防”，但说到底就两类——**版本对不对**、**启动方式合不合适**。

### 3.1 打包：jar 与 war 只差一行

两种产物走的是同一个 Maven 流程，区别只在 `pom.xml` 的 `packaging`：

```xml
<!-- jar 包 -->
<packaging>jar</packaging>

<!-- war 包 -->
<packaging>war</packaging>
```

改完在 IDEA 的 Maven 面板里点打包就行（我没有用命令行 `mvn clean package`，图省事，效果一样）：

![把 packaging 改成 war](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/fed77f4b-eacb-41db-a4e6-631a43d605b0.png)

![在 Maven 面板执行打包](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/ebd415d7-ddc5-412a-9123-630cffcec318.png)

`target` 目录里出现 war 文件就说明打包成功：

![target 目录下生成的 war](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/1ae00cc5-b8e7-47ab-a0d3-978530c47752.png)

把 `packaging` 换成 `jar` 再打一次，流程完全一样，得到：

![同样的流程得到的 jar](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/21f29a2c-d6d3-4c66-a0e9-040dec402a46.png)

> **注意：** 打包前先把配置改对。`application-prod.yml` 这次至少要动四处：数据库地址（node2）、Redis 地址（node2）、R2 对象存储的桶与密钥、商汤人脸识别的 appId 与密钥。**地址全部用域名或 node2 的 IP，绝不能留 `localhost`**——包是在 Windows 上打的，那里的 `localhost` 指的是你自己的电脑。
>
> **提示：** 密钥不要提交进仓库。实验里直接写在 `yml` 里没问题，正式项目用环境变量或配置中心；写进仓库的密钥迟早会跟着代码泄漏出去。

### 3.2 JDK 11：能显示版本，不代表版本对

我第一次做项目时装的是 JDK 8。当时在终端敲了个 `java`，看到有输出，就以为运行环境没问题，没再管 `JAVA_HOME`。结果这次启动直接抛异常：

![启动 jar 直接抛异常](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/46afcaa3-ef46-4748-a871-76bbcea3ded9.png)

这个报错的意思是：当前 JDK 版本和项目要求的（11）不兼容。这条教训很深刻——**“能执行 `java` 命令”什么都不说明，`java -version` 才是准的**。

装 11：

```bash
dnf install -y java-11-openjdk java-11-openjdk-devel
```

装完发现 `java -version` 还是旧的 8。原因是 `PATH` 里先命中了之前写进环境变量里的 JDK 8，优先级比新装的 11 高：

![旧版本优先级更高](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/38b66cb2-a9d7-46e6-95d2-2c5206caec0b.png)

之前的 `JAVA_HOME`、`PATH` 写在 `/etc/profile` 里。先看清要改哪几行：

```bash
cat -n /etc/profile
```

![查看 /etc/profile 中旧的环境变量行](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/046e7fae-00f7-416e-a132-dc71285cd402.png)

确认旧的三行在第 79~81 行，按行号删掉：

```bash
sed -i '79,81d' /etc/profile
```

再追加新的两行：

```bash
cat >> /etc/profile <<'EOF'
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-11.0.20.1.1-2.el9.x86_64
export PATH=$JAVA_HOME/bin:$PATH
EOF
source /etc/profile
```

> **坑：** 我最初是“追加 + 删最后两行”一条命令搞定的，写法近似 `sed -i -e '$a ...' -e '$-2,$d'`。`$-2` 不是合法的 sed 地址；就算换成能删最后两行的写法，也很容易把**刚追加的两行**一起删掉。改 `/etc/profile` 这类文件，先 `cat -n` 看清行号、按行号删，比“删最后 N 行”安全得多。
>
> **提示：** `JAVA_HOME` 要换成自己机器上的真实路径，`ls /usr/lib/jvm/` 确认目录名。`<<'EOF'` 里的单引号也不能去掉——去掉之后 `$JAVA_HOME` 会在写入时被当前 shell 展开成旧值，写进文件就成了死路径。

验证：

```bash
java -version     # 应为 11.x
echo $JAVA_HOME
```

![重载后版本切到 11](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/5e79a81b-c4bc-4191-ad75-036026902b6b.png)

> **提示：** 系统里同时有多个 JDK 时，`alternatives --config java` 也能切默认版本。但 `/etc/profile` 里的 `JAVA_HOME` 优先级更高，两处必须一致，否则会出现“`java -version` 是 11、应用却按 8 跑”的怪事。

### 3.3 启动 jar：前台先验证，再考虑挂后台

把打好的 jar 传到 node3 的 `/export`：

![jar 已上传到 /export](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/94d092df-c34c-4803-83be-82b028c9e924.png)

![确认文件在位](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/6c8f7a89-508d-498a-b98f-0c6b6a197a65.png)

先**前台**跑一次，日志直接在屏幕上，出问题第一时间能看到：

```bash
java -jar /export/zzyl-admin.jar
```

![jar 启动日志](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/95d3bd95-89d3-49e0-b7d4-700f474e211b.png)

![启动完成](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/2ae114b3-79f3-453a-bed2-67e55c4ae641.png)

浏览器访问 `http://192.168.88.172:8080/` 能打开，说明 jar 这条路通了：

![浏览器访问 node3:8080 正常](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/d98b6681-0161-4c60-bbfa-649002db4b66.png)

但前台一关终端进程就没了，所以要挂到后台。可选方案就这么几种：

| 方式 | 写法 | 适合场景 |
| --- | --- | --- |
| `nohup` | `nohup java -jar xx.jar > /export/zzyl-admin.log 2>&1 &` | 简单后台运行，日志落到指定文件 |
| `screen` | `screen -S zzyl` 里直接跑 | 想要一个能回看的交互终端 |
| `screen` + `nohup` | 两者叠加 | 没有收益，别这么干 |
| systemd | 写 unit 文件 | 真要长期维护时 |

nohup 最省事：

![nohup 后台运行](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/ce9d6195-1212-4f19-ad25-fca0711ad046.png)

screen 当然也可以：

![用 screen 起一个会话](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/5aaf0be8-7b10-4ee0-ab92-4c3a24a47998.png)

![在 screen 会话里运行 jar](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/a6f55609-e2e9-4a00-9f60-117308993006.png)

**关于 screen 和 nohup 叠加**：我原本专门写了一节来论证这件事，后来觉得用不着那么重，一句话就够——**别把两种托管方式叠在一起**。理由很实在：

- 排查地狱：`jobs` 看不到、`ps` 要翻两层，杀进程时容易漏杀或误杀，留下僵尸进程；
- 日志失控：`nohup.out` 默认落在当前目录，越写越大又不好找；
- 职责重叠：screen 和 nohup 互相“抢着”托管同一个进程，重启、迁移时必踩坑；
- 收益接近零：多一层托管，进程并不会更稳。

要么在 `screen` 会话里直接 `java -jar`，要么老老实实 `nohup ... &`，二选一。实验阶段也没必要立刻写成 systemd 服务——就这么几条命令，配置成本不划算；等真要长期维护了再迁移。

> **提示：** 用 `nohup` 时把日志重定向写清楚（`> /export/zzyl-admin.log 2>&1`），用 `echo $! > /export/zzyl-admin.pid` 记下 PID。后面停服务直接 `kill $(cat /export/zzyl-admin.pid)`，比 `ps aux | grep java` 干净得多。

### 3.4 war 包交给 Tomcat

jar 由 JDK 直接跑，war 得放进容器的 `webapps`。先装好 Tomcat，再把 war 丢进去：

![war 放进 Tomcat 的 webapps](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/814aff77-b227-4152-886f-1eae2ac8d992.png)

放行 8080 端口，然后浏览器访问：

![firewalld 放行 8080](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/14604c3d-46c2-472e-9323-fbc9d4f46cc4.png)

![Tomcat 启动状态](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/d110cbc5-b02f-4008-930c-6d7b91119c99.png)

![浏览器访问 war 应用](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/d7f12c8f-9171-449c-b497-eaa6198743da.png)

能打开，war 这条路也通了。几个经验：

- **war 的文件名就是访问路径**：`zzyl-admin.war` 对应 `http://node3:8080/zzyl-admin/`，改了名字 URL 就得跟着改；
- Tomcat 启动后要等它把 war 解压完，`catalina.out` 里出现部署完成的日志，再去看页面；
- Tomcat 用哪个 JDK 取决于 `JAVA_HOME`。这也是 3.2 节为什么非得把 `JAVA_HOME` 改对——war 版本不匹配的报错，往往就出在这里。

到这里 node3 结束：两种产物都能独立启动。下面去 node1。

## 4. 接入层部署（node1）

node1 是用户真正访问的入口：Nginx 先把前端静态文件发出去，再把 `/prod-api/` 转给 node3。整篇文章里问题最多的地方就是这里。

### 4.1 前端打包

在项目前端目录执行生产构建：

```bash
npm run build:prod
```

> **提示：** 前端请求的接口前缀（一般是 `.env.production` 里的 `VUE_APP_BASE_API`）要设成 `/prod-api`，和 Nginx 里的 `location /prod-api/` 对上。这一步不对，静态页照样能打开、接口却全 404，很容易把锅扣到 Nginx 头上。

构建完会生成 `dist` 目录：

![前端构建生成的 dist 目录](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/998a2815-a6cb-4cdd-b931-779117f0ebba.png)

把 `dist` 拷到 node1，放到 `/var/www/dist`（Nginx 的 `root` 就指这里，两处必须一致）：

```bash
scp -r dist node1:/tmp/
ssh node1 'mkdir -p /var/www && cp -r /tmp/dist /var/www/'
```

![把 dist 复制到 node1](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/f15dd63a-ac07-4384-b439-0f841e0eec94.png)

### 4.2 Nginx 配置：静态页、单页路由、反向代理

先装：

```bash
dnf install -y nginx
systemctl enable --now nginx
```

配置写在 `/etc/nginx/nginx.conf`。`http` 块里加三个 CORS 头，`server` 块里配静态目录和反向代理：

![nginx.conf 的 server 部分](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/d262f620-7e66-4018-b2a5-88783fa84aeb.png)

```nginx
http {
    # 三个 CORS 头，放在 http 层
    add_header Access-Control-Allow-Origin *;
    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS, PUT, DELETE";
    add_header Access-Control-Allow-Headers "Origin, X-Requested-With, Content-Type, Accept, Authorization";

    server {
        listen 80;
        server_name ns1.node1.com;

        # 请求体与缓冲
        client_max_body_size     60m;   # 允许的最大请求体
        client_body_buffer_size  512k;  # 请求体缓冲
        client_header_buffer_size 2k;   # 请求头缓冲

        # 处理静态页面
        location / {
            root  /var/www/dist;
            index index.html index.htm;
            try_files $uri $uri/ /index.html;
        }

        # 处理反向代理
        location /prod-api/ {
            proxy_pass http://192.168.88.172:8080/zzyl-admin/;
            proxy_set_header Host      $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header Upgrade    $http_upgrade;
            proxy_set_header Connection upgrade;
        }
    }
}
```

改完先检查语法再重载：

```bash
nginx -t && systemctl reload nginx
firewall-cmd --permanent --add-port=80/tcp && firewall-cmd --reload
```

> **提示：** 上面只保留了关键部分。实际是在原有 `nginx.conf` 的 `http`/`server` 块里改，别整份覆盖——`mime.types`、`error_page`、默认 `server` 这些还得留着，否则静态资源会被当成 `application/octet-stream` 直接下载，或者干脆 404。

这份配置里有四个地方值得单独说，因为它们**不影响启动，只影响能不能用**：

**① `try_files $uri $uri/ /index.html`**
Vue 是单页应用。从首页点链接进 `/system/user` 没问题，但直接刷新这个地址，服务器上并没有对应的文件，会返回 404。`try_files` 的作用就是“找不到文件就交回 `index.html`，让前端路由自己处理”。

**② `proxy_pass` 末尾那个斜杠**
`location /prod-api/` 配 `proxy_pass .../zzyl-admin/`，会把 `/prod-api/user/list` 改写成 `/zzyl-admin/user/list`。**末尾的 `/` 一丢，路径就原样带过去变成 `/prod-api/user/list`，后端直接 404。**

**③ 反代地址里的 IP**
这里要填 node3 的真实地址，我这里是 `192.168.88.172`。照抄别人的配置时最容易出事的就是这个 IP——网段不同、机器换过，都会安静地失败（表现为 502 或超时）。

**④ `add_header` 的继承规则**
子级（`location`）里只要写了自己的 `add_header`，父级（`http`/`server`）的就**不再继承**。所以我这三个头放在 `http` 层，`location` 里没有再加别的 `add_header`，否则会悄无声息地丢掉。
另外，**同源部署（前端和接口都走 node1）其实用不到 CORS**，这三个头是模板里带的，留着无妨；真正做前后端分离、域名不同的时候才关键。

### 4.3 403 与 502：SELinux 的两道门

放行 80 端口之后，页面出来的是 403：

![放行防火墙后访问返回 403](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/5127484f-69b8-4eae-9d4f-99ea14ab82a6.png)

`403 Forbidden` 且 `curl -I` 能连上，说明端口通了、Nginx 也收到请求了——问题出在 **Nginx 读不了 `/var/www/dist` 里的文件**。查日志：

![audit 日志里 nginx 读取被拒绝](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/7a1580f1-41c6-4a43-931d-598834c7ca8c.png)

`denied` 明明白白写着是 SELinux 拦的：`/var/www` 不在 httpd 允许读取的上下文里。打标签，再让规则真正生效：

```bash
semanage fcontext -a -t httpd_sys_content_t '/var/www/dist'
semanage fcontext -a -t httpd_sys_content_t '/var/www/dist(/.*)?'
restorecon -Rv /var/www/dist
```

![执行 semanage 打标签](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/d9317c01-a303-487f-b875-5e7c2c1ad702.png)

> **提示：** 只读的静态资源用 `httpd_sys_content_t` 就够了。`httpd_sys_rw_content_t` 是给**需要写入**的目录准备的（上传目录、缓存目录），乱给等于多开一道门。

标签打完，403 消失，页面也能打开了，但数据没有——接口直接 502。

原因换了一个：Nginx 处理 `/prod-api/` 时要用 `httpd_t` 去**主动连接** `192.168.88.172:8080`，而 SELinux 默认不允许 httpd 往外连。用 `seinfo -b | grep httpd` 把布尔值的候选翻出来：

![seinfo -b 查 httpd 相关布尔值](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/e5e42c6c-7362-490a-b899-200685685b43.png)

日志和这个判断对得上（`name_connect ... dest=8080`）：

![audit 日志显示 nginx 连接 8080 被拒绝](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/7922d689-4a1b-4f85-b918-fe313bd1b3c2.png)

```bash
setsebool -P httpd_can_network_connect on
```

![打开布尔值后页面正常](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/596f1e0f-99e2-47e7-a26d-1e5eb542f0f6.png)

这一段的经验可以直接背下来：

| 现象 | 先查什么 | 处置 |
| --- | --- | --- |
| 403 Forbidden | `ls -Z` 看文件上下文、audit 里 `denied { read }` | `semanage fcontext` + `restorecon` |
| 502 Bad Gateway | audit 里 `denied { name_connect }` | `setsebool -P httpd_can_network_connect on` |

两个都是“防火墙已经放行、进程也在跑”却不通，区别只在 SELinux 拦的环节不同：一个拦“读文件”，一个拦“连端口”。

### 4.4 上线验证

浏览器直接访问 node1：

![node1 访问正常](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/e1861ca6-04d2-4c58-aa43-c69f31148bbc.png)

能看到验证码、能登录、数据能查出来，说明静态资源和反向代理都通了。node1 的基本部署到此结束，只剩 DNS。

## 5. DNS 配置：三个小错误，让解析一直不生效

最后一块是 DNS。在 node1 上用 BIND 给 `node1.com` 做正反向解析，让 `ns1.node1.com` 指向 node1、`node2.node1.com` 指向 node2。

```bash
dnf install -y bind bind-utils
```

`/etc/named.conf` 里加正向和反向两个 zone：

```conf
options {
    listen-on port 53 { any; };
    listen-on-v6      { none; };
    allow-query       { any; };
    recursion no;
};

zone "node1.com" IN {
    type master;
    file "/var/named/node1.com.db";
};

zone "88.168.192.in-addr.arpa" IN {
    type master;
    file "/var/named/88.168.192.rev";
};
```

正向文件 `/var/named/node1.com.db`：

```conf
$TTL 1D
@   IN  SOA ns1.node1.com. root.node1.com. (
        2026110401 ; serial
        1H         ; refresh
        15M        ; retry
        1W         ; expire
        1D )       ; minimum
    IN  NS  ns1.node1.com.
ns1     IN  A   192.168.88.170
node1   IN  A   192.168.88.170
node2   IN  A   192.168.88.171
node3   IN  A   192.168.88.172
www     IN  A   192.168.88.170
ntp     IN  A   192.168.88.171
```

反向文件 `/var/named/88.168.192.rev`：

```conf
$TTL 1D
@   IN  SOA ns1.node1.com. root.node1.com. (
        2026110401
        1H
        15M
        1W
        1D )
    IN  NS  ns1.node1.com.
170 IN  PTR node1.node1.com.
171 IN  PTR node2.node1.com.
172 IN  PTR node3.node1.com.
```

文件生成后属主、权限、上下文都要对，否则 named 读不了：

```bash
chown root:named /var/named/node1.com.db /var/named/88.168.192.rev
chmod 640         /var/named/node1.com.db /var/named/88.168.192.rev
restorecon -Rv /var/named
systemctl enable --now named
```

下面是我实际踩的三个错，一个比一个隐蔽。

### 5.1 错一：zone 文件名写错（node1 写成 node2）

`systemctl status named` 直接是 failed 状态，日志说文件找不到：

![named 启动失败，提示文件找不到](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/22b1e5b1-0908-4799-8cb9-a908f00351d2.png)

到 `/var/named` 一看，文件名叫 `node2.com.db`：

![ls /var/named 发现文件名写成了 node2](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/051092c1-7687-4626-a588-b0efd134c449.png)

配置里写的是 `node1.com.db`，实际落盘的是 `node2.com.db`——名字差一个数字，`zone ... loading from master file ... failed: file not found`。改文件名或改配置，二选一，改完记得两边都对上。

### 5.2 错二：`none` 写成了 `no`

文件名改对，named 还是起不来。翻主配置才发现，对应位置本该写 `none`，我写成了 `no`（我这个错落在 `listen-on-v6 { none; };` 这一句上），named 直接报语法错误。

这类问题不用猜，先让 named 自己检查：

```bash
named-checkconf /etc/named.conf
named-checkconf -z /etc/named.conf     # 连 zone 文件一起检查
named-checkzone node1.com /var/named/node1.com.db
```

`named-checkconf -z` 会一次报出语法错误和 zone 文件的加载错误，比反复重启 named 看 journal 快得多。

### 5.3 错三：`cp named.empty` 带来的权限与上下文

语法也改对了，named 还是起不来，这次日志变成了 `permission denied`：

![journalctl 里 named 读取 zone 文件 permission denied](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/94bf74b3-8b12-4894-b4cd-de461e467bb1.png)

问题出在“图省事”上：我当时是 `cp /var/named/named.empty /var/named/node1.com.db` 再改内容。模板文件复制过来，**属主、权限模式、SELinux 上下文**全都跟着过来了，而 named 进程（用户 `named`）没有读权限。

> **坑：** 从模板 `cp` 出来再改，会同时继承两样东西：**文件权限**（属主/模式）和 **SELinux 上下文**。`chown`/`chmod` 解决前者，`restorecon` 解决后者。只修一个，报错会从 `permission denied` 变成另一种，很容易误以为“还没修好”。

### 5.4 验证

```bash
systemctl status named --no-pager
ss -lntup | grep ':53'
dig @192.168.88.170 ns1.node1.com
dig @192.168.88.170 node2.node1.com
dig -x 192.168.88.171 @192.168.88.170
```

![dig 正向解析正常](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/ffff244c-b255-43df-aa5b-6f75d0c3d7ff.png)

`dig` 后面一定要带 `@192.168.88.170`，否则它会去问 `/etc/resolv.conf` 里配的 DNS，测的不是你刚配的这台。

再把机器自己的 DNS 指向 node1：

```bash
cat > /etc/resolv.conf <<'EOF'
nameserver 192.168.88.170
EOF
```

> **提示：** 实验环境直接改 `/etc/resolv.conf` 最省事；但如果网卡由 NetworkManager 管理，重启后这个文件会被覆盖回去，正式环境用 `nmcli`/`nmtui` 设 DNS 更稳。

然后浏览器用域名访问：

![用域名访问后台，链路全通](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E7%AC%AC%E4%BA%8C%E6%AC%A1%E5%AE%9E%E9%AA%8C/pictures/bead6b97-dae9-46d8-b9af-6ad56a2febf8.png)

`http://ns1.node1.com/index` 能打开、数据正常，说明 **正向解析 → Nginx → 反向代理 → node3 后端** 这条完整链路通了。

## 6. 部署期问题速查表

折腾完把散落的坑收成一张表，下次照着查比翻正文快：

| 现象 | 大概率原因 | 处置 |
| --- | --- | --- |
| 浏览器一直转圈 / 超时 | firewalld 没放行端口 | `firewall-cmd --permanent --add-port=N/tcp` 后 reload |
| 403 Forbidden | SELinux 静态文件上下文不对 | `semanage fcontext` + `restorecon -Rv` |
| 502 Bad Gateway | SELinux 不允许 httpd 主动连后端 | `setsebool -P httpd_can_network_connect on` |
| 接口 404，静态页正常 | `proxy_pass` 少了末尾斜杠 | 改成 `.../zzyl-admin/` |
| 刷新深层路由 404 | 单页应用没回落 | `try_files $uri $uri/ /index.html` |
| `java -version` 还是 8 | `JAVA_HOME`/`PATH` 指向旧 JDK | 按行号删旧行，重写 `/etc/profile` |
| 打包后连不上数据库 | 配置里还留着 `localhost` | 改成 node2 的地址 + 建远程账号 |
| `Can't connect to MySQL` | 只监听 127.0.0.1 | `bind-address = 0.0.0.0` |
| Redis `protected mode` 拒绝 | 没配 `requirepass` | 设密码后重启 |
| 验证码不显示、令牌校验失败 | 三台时间不同步 | `chronyc sources` 确认出现 `^*` |
| named 报 `file not found` | zone 文件名和配置不一致 | `ls /var/named` 对照 `named-checkconf -z` |
| named 报 `permission denied` | `cp` 模板文件带来的权限/上下文 | `chown root:named` + `chmod 640` + `restorecon` |

## 7. 小结

全上服务器这件事，麻烦不在“装软件”，而在**排错**。装 MySQL、Redis、Nginx、Tomcat，照着文档敲基本都能过；真正耗掉一晚上的，是端口通了却 403、标签打完了却 502、文件明明在那儿 named 却说找不到。

我把每个报错原样记下来，是因为我小错误不断——拼写、文件名、权限位，几乎每一处都踩过。写这篇文章的时候我甚至有点心虚：博客写得细，不等于水平高，恰恰是因为坑踩得多、笔记记得多。但如果这些记录能让别人少熬一个晚上，那这份“负担”就还算有点用。

最后说两句体会：

- **别为几行命令硬写脚本。** 三五条命令专门维护一个脚本，改起来比手敲还麻烦；一条能复用的拼接命令（比如那条 `sed`、那条 `for` 循环）刚好卡在两者之间，既省事又不失可控。
- **先定角色和验收点，再动手。** 节点分工写在纸上、每层做完先验收，看着笨，实际上省下了“这到底是哪台机器坏了”的反复排查。

三台机器的服务全部跑通，浏览器用域名进后台，数据正常——这一篇的目标就算完成了。第三篇接着做日志和监控。
