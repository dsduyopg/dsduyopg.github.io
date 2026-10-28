---
comments: true
giscusMapping: "og:title"
utterancesIssueTerm: "og:title"
title: "rsync+inotify+system 实验练习"
slug: "rsync-inotify-system-lab"
date: 2026-10-28
lastmod: 2026-10-28
draft: false
ShowToc: false
description: "记录 rsync、inotifywait 与 systemd 实现实时同步的实验过程、配置步骤和问题排查。"
tags: ["Linux", "rsync", "inotify", "systemd", "SELinux"]
---

{{< toc >}}

> 前言：这个实验，是通过rsync结合inotfy实现系统级别的实时同步，我开始这个实验的时候，遇到了好多问题，有拼写错误，以及权限，用户组这些，密码本格式深层防火墙，反正就是我做的时候，遇到了许多意想不到的问题，我当时想既然是第一次做，掌握的不熟练，那么我就多练习几次，但是总会有新的问题诞生，这是一点，知道昨天，我做完的时候，也是遇到了问题，但是结合codex给我的分析，我拍了张快照从之前全新的快照节点恢复，又做了一遍，直到这个时候，我才终于独立将这个实验，完成了，因此我其实想要把我这几天这个实验的一些体会以及思考写下来，同时还有我遇到的的问题，都写下来，希望可以帮助大家节约时间，分享自己的心得体会，下面就是我的这个实验探究了

## 1. 实验目标与最终结果

### 1.1 要实现什么

需求说明：

`需求说明： 目前在企业服务node1节点中，/export/rsync_share目录用于存放需要备份的文件，公司希望能够实时监控该目录，并将变化同步到node2的/export/node1_share目录下，请运维工程师来实现 `

### 1.2 最终环境拓扑

我这里有两张，一个是用工具优化的，一个就是自己独立绘制的

下图是最终完成后的实验结构

```text
┌──────────────────── node1：客户端／同步发起端 ────────────────────┐
│                                                                   │
│  /usr/local/bin/real_time_rsync.sh                                │
│  /etc/systemd/system/rsync_real.service                           │
│  /etc/rsync.passwd                          # 只包含密码，权限 600 │
│                                                                   │
│  监控目录：/export/rsync_share/                                    │
│          │                                                        │
│          ├── systemd 启动 real_time_rsync.sh                      │
│          ├── inotifywait 监听文件变化                             │
│          └── rsync 推送文件                                       │
│                                                                   │
└───────────────────────────────┬───────────────────────────────────┘
                                │
                                │ TCP 873
                                │ backup_user@node2::node1_share
                                ▼
┌──────────────────── node2：服务端／接收端 ────────────────────────┐
│                                                                   │
│  /etc/rsyncd.conf                                                 │
│  /etc/rsyncd.passwd                       # 用户名:密码，权限 600 │
│  /etc/systemd/system/rsyncd.service                               │
│                                                                   │
│  rsync 模块：[node1_share]                                        │
│  接收目录：/export/node1_share/                                    │
│  SELinux：rsync_full_access 已配置                                │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

这里是我实验过程中手绘的结构草图。图中部分文件名后来进行过修正，最终配置以“实验架构”和正文中的配置清单为准

<img title="" src="https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/IMG_20261028_090530.png" alt="IMG_20261028_090530" data-align="right">

### 1.3 用到的主要东西

在这个实验当中，客户端是使用主要使用了 rsync inotifywait 以及sysem托管的东西，而服务器则是在守护管理里面把rsync的配置项注册进去

同时，在做这个实验的时候，需要注意SELlinux的，要打开相对应深层防火墙的权限，这个是一点，其他的都是小问题，需要特别注意就可以了

### 1.4 最终验证结果

我最后在node1上面对应的目录，上传了一个文件，发现这个日志文件开始记录了，客户端可以检测到目录变化，同时可以动态的把相对应的文件推送过去，通过截图可以知道，我的客户端这一侧其实是没有问题的，服务可以正常起来



![d5616a84-0e95-46e6-abb9-f929d8b572e5](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/d5616a84-0e95-46e6-abb9-f929d8b572e5.png)







![e9176478-627c-4d05-89d3-94dbae3ed7f9](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/e9176478-627c-4d05-89d3-94dbae3ed7f9.png)





然后，我在node2看了一下，发现文件也是可以同步过来的，在服务器这一侧没有受到深层防火墙的阻止，服务器这一侧和客户端都成功了，我这个实验其实也就完美的结束了



![cf278b81-8e86-469f-b088-df43c0cfebe6](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/cf278b81-8e86-469f-b088-df43c0cfebe6.png)

截图，出现其实说明我的这个实验做的没有什么太大的问题，基本功能是可以用的，然后我会就如何实现这个实验展开细说

## 2. 原理解释

### 2.1 rsync 与 rsync daemon 的区别

在我看来，rsync加上守护进程运行会更加平稳，可以持续不间断的运行，rsync 是负责文件传输的程序，`rsync daemon` 是它的常驻服务模式。daemon 持续监听 TCP 873，能够为客户端提供稳定的模块访问入口；但文件变化检测由 `inotifywait` 完成，每次变化后仍由独立的 rsync 客户端发起传输。因此，守护进程解决的是“服务持续可用”的问题，并不能单独保证每一次同步都成功。

> 总结：daemon 让服务端持续运行；systemd 让服务可靠托管；inotifywait 负责发现变化；rsync 负责真正传输。

### 2.2 inotifywait 如何触发同步



`inotifywait` 本身**不会直接调用 rsync**。它只负责监听文件系统事件，把“哪个文件发生了什么”输出成一行文本；真正调用 rsync 的是 shell 的 `while read` 循环

```text
systemd 启动 real_time_rsync.sh
        ↓
inotifywait 持续监听目录
        ↓
文件发生变化
        ↓
内核产生 inotify 事件
        ↓
inotifywait 输出一行“路径 + 事件”
        ↓
while read 读取这一行
        ↓
循环体执行一次 rsync
        ↓
node2 接收同步结果
```

> `inotifywait` 负责发现变化，shell 循环负责把事件转换为同步动作，rsync 负责实际传输。`inotifywait` 不传输文件，也不判断文件内容是否相同，它只是事件触发器。

### 2.3 客户端和服务端完整数据流

```text
① 用户在 node1 创建或修改文件
                    ↓
② Linux 内核产生 inotify 事件
                    ↓
③ inotifywait 将“路径 + 事件”写入管道
                    ↓
④ shell 的 while read 读取事件
                    ↓
⑤ node1 启动一个临时 rsync 客户端
                    ↓
⑥ rsync 通过 TCP 873 连接 node2
                    ↓
⑦ node2 的 rsync daemon 读取 /etc/rsyncd.conf
                    ↓
⑧ 检查 hosts allow / hosts deny
                    ↓
⑨ 进入 node1_share 模块并验证用户名和密码
                    ↓
⑩ daemon 使用 uid=rsync 访问 /export/node1_share
                    ↓
⑪ 双方交换文件列表并比较文件大小、时间等属性
                    ↓
⑫ node1 传输新增或变化的数据
                    ↓
⑬ node2 写入文件，并使用 --delete 删除多余文件
                    ↓
⑭ 客户端 rsync 退出
                    ↓
⑮ inotifywait 继续等待下一次变化
```





然后，写到这里的时候，我就开始，写明如何详细部署这个实验的rsync服务器了



## 3. 详细操作步骤

### 3.1 服务端的详细操作步骤

#### 1. 准备工作

这里需要创建一个用于访问的用户

```shell
dnf install -y rsync
useradd rsync
echo "123456" | passwd --stdin rsync

```

![34debde5-8745-470a-8cd3-c35b0a1a46f0](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/34debde5-8745-470a-8cd3-c35b0a1a46f0.png)

到这里其实没有多大的问题，但是呢需要注意的是，stdin应当加上--否则就像我一样，创建用户无法有效创建，直到我在stdin前面加上了--，就发现可以正常的创建用户。

![2e6c6c7a-9940-4a59-98e9-5dcc1b6a7f4e](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/2e6c6c7a-9940-4a59-98e9-5dcc1b6a7f4e.png)

创建完用户之后，应当在建立一个本地的目录



```shell
mkdir -p /export/node1_share  
```

这里其实也要有注意的，需要把目录的所有者和所属组都设置为rsync，我前几次都栽在这上面了，细节需要特别注意



```shell
chown -R rsync:rsync /export/node1_share
```





![b93a5065-082a-4cea-b1c2-c233aaf407fd](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/b93a5065-082a-4cea-b1c2-c233aaf407fd.png)



最后，可以看到建完之后的目录结构应当是这样的



这些搞定之后，建立密码本，这个也需要额外注意，格式

```shell
echo "backup_user:123456" >/etc/rsyncd.passwd
```

>  这里的用户名可以随便，但是需要和后面的模块的认证用户的名字相一致，同时需要注意，这里的用户名和密码之间应当是:，不能是其他任何符号，否则服务也会起不来，特别要注意

建立完密码本，并没有结束，还要给他赋予600权限，只能所有者访问这个密码本，都是小细节，都需要特别注意



```shell
chmod 600 /etc/rsyncd.passwd
```

这个时候，密码本 路径 用户名都搞定了，然后就开启防火墙，注意这里的防火墙需要开两层，一层是端口，另一层是深层防火墙





- 这里，我就先开启873端口的防火墙
  
  

```shell
firewall-cmd --add-port=873/tcp --permanent && firewall-cmd --reload
```

![b63c34cd-0c9e-487e-a0bd-770eda96bc51](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/b63c34cd-0c9e-487e-a0bd-770eda96bc51.png)



到这里，发现这个端口被开启了，接下来就是深层防火墙





- 开启深层防火墙

这里其实有两种开启的方法，一种就是比较粗糙了，另一种就是精细化的开启

粗糙的这个，其实非常简单就是把值设置0

```shell
setenforce 0 && getenforce
```

这里其实和systemctl stop firewalld这个是一个道理的，对于所有的服务都松绑了，不能精细化

```shell
setsebool -P 'rsync_full_access' on
```

![7fdcfb6c-02dd-4a78-9c70-be71c9f85df7](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/7fdcfb6c-02dd-4a78-9c70-be71c9f85df7.png)

这里其实就是，用布尔值进行操作的，而且是永久的，我用的就是这个。



#### 2. 修改配置文件



```shell

vim /etc/rsyncd.conf

# /etc/rsyncd: configuration file for rsync daemon mode

# See rsyncd.conf man page for more options.

# configuration example:

 uid = rsync
 gid = rsync
 use chroot = no
 max connections = 4
 port=873
 pid file = /var/run/rsyncd.pid
 exclude = lost+found/
 transfer logging = yes
 timeout = 900
 ignore nonreadable = yes
 dont compress   = *.gz *.tgz *.zip *.z *.Z *.rpm *.deb *.bz2

# [ftp]
#        path = /home/ftp
#        comment = ftp export area
[node1_share]
comment=this is auto sync'service
path=/export/node1_share/
read only=no
write only=no
auth users=backup_user
secrets file=/etc/rsyncd.passwd
hosts allow=192.168.88.0/24
hosts deny=*







```

这里需要在全局变量下面，新建一个port参数值就是873，那个node1_share模块是可以随便取名的





#### 3. 设置为服务项

```shell

vim /etc/systemd/system/rsyncd.service
[Unit]
Description=this is auto sync's service
[Service]
ExecStart=/usr/bin/rsync --daemon --config=/etc/rsyncd.conf --no-detach
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
[Install]
WantedBy=multi-user.target


```

然后，保存文件，重载服务的文件

```shell
systemctl daemon-reload
```



#### 4. 开启服务



```shell
systemctl start rsyncd
systemctl enable rsyncd
systemctl status rsyncd
```

![1b07e7d2-cc1a-4f1c-81e9-d4e1a1abe0a2](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/1b07e7d2-cc1a-4f1c-81e9-d4e1a1abe0a2.png)



这里服务成功起来，服务端的配置也就完成了

### 3.2 客户端的详细操作步骤

先安装客户端依赖：

```shell
dnf install -y rsync inotify-tools
```



#### 0. 先测试服务端 rsync 的服务是否正常



```shell
rsync rsync://backup_user@node2/node1_share
```

![93ec18d4-2924-4b1e-931e-ab84eda8deb6](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/93ec18d4-2924-4b1e-931e-ab84eda8deb6.png)



到这里，其实就可以发现服务端的是起来了，然后就开是客户端的操作了



#### 1. 准备工作



- 建立一个密码本

```shell
echo "123456" >/etc/rsync.passwd
chmod 600 /etc/rsync.passwd
```

注意，这里千万不能忘记书写600这个，到时候也会报错的

- 建立也给备份目录

```shell
mkdir -p /export/rsync_share/
```

这里的目录不需要授予特别的权限



在写脚本之前需要注意的是，最好放置在/usr/local/bin/这个目录里面，因为放置其他目录比如/root下面可能会导致sel阻止脚本执行，或者执行受到严格控制，这里我就放置在/usr/local/bin下面



#### 2. 开始写脚本文件

```shell
vim /usr/local/bin/real_time_rsync.sh

#!/bin/bash
DIR=/export/rsync_share/
TARGET=backup_user@node2::node1_share
LOG=/var/log/rsync.log

inotifywait -r -m -e delete,modify,create,attrib --format '%w%f %e' "$DIR" |
        while IFS= read -r dir action;
        do
                echo "establish rsync $(date '+%F %T') 路径是$dir,动作是$action">>"$LOG" 2>&1
                rsync -avz --delete --password-file=/etc/rsync.passwd "$DIR" "$TARGET" >>"$LOG" 2>&1
                echo "finish rsync $(date '+%F %T') 路径是$dir,动作是$action">>"$LOG" 2>&1
        done



```



这里，也要注意的，需要特别注意，哪怕bash real_time_rsync.sh可以成功执行，就不要以为，不需要授予x权限了，或者认为既然bash可以成功执行脚本文件那么的话，我到时候注册进入守护进程也可以成功执行，这里其实就错了，这里必须要写上，a+x，只有如此的话，后面启动服务项的时候才不会报错

```shell
chmod a+x /usr/local/bin/real_time_rsync.sh
```

#### 3. 注册入服务项

```shell
vim /etc/systemd/system/rsync_real.service

[Unit]
Description=this is auto sync
[Service]
ExecStart=/usr/local/bin/real_time_rsync.sh
Restart=on-failure
[Install]
WantedBy=multi-user.target
```

然后，重载文件，启动服务，发现也是可以的。



![908fedac-31ce-482e-8d43-af29dc7eb016](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/rsync%2Binotify%E5%AE%9E%E9%AA%8C/pictures/908fedac-31ce-482e-8d43-af29dc7eb016.png)

到这里，其实这个实验就完成了，接下来呢，我就对于我之前做这个实验的时候遇到的问题，前面是我的经验吧，可以帮助大家节约时间，下面就是我的问题，以及对于问题的诠释了



## 4. 遇到的一些问题



### 4.1 拼写问题

这个实验里，我因为急着往下做，犯了不止一次拼写错误。它们看起来都是小问题，但每一个都能让服务直接失效。

| 文件 | 我的错误写法 | 正确写法 | 结果 |
| --- | --- | --- | --- |
| `rsyncd.conf` | `host allow` | `hosts allow` | 参数可能被 rsync 静默忽略 |
| systemd 单元 | `multi-user.targer` | `multi-user.target` | 开机启动目标无效 |
| systemd 单元 | `Restart=on-faliure` | `Restart=on-failure` | 自动重启策略被忽略 |
| systemd 单元 | `/etc/rsyncd.config` | `/etc/rsyncd.conf` | daemon 找不到配置文件 |
| 客户端脚本 | `while read -r dir action:` | `while read -r dir action; do` | `read` 语法错误，循环体不执行 |

其中服务端的配置文件路径错误最直接：

```ini
ExecStart=/usr/bin/rsync --daemon --config=/etc/rsyncd.conf --no-detach
```

我最初写成了：

```ini
ExecStart=/usr/bin/rsync --daemon --config=/etc/rsyncd.config --no-detach
```

把 `conf` 写成了 `config`，服务就一直无法正常启动。

客户端的问题更隐蔽：我把 `while read` 后面的分号 `;` 写成了冒号 `:`。分号是 shell 用来分隔命令的，冒号会被当成变量名的一部分，导致 `read` 失败；但 `inotifywait -m` 仍在运行，所以 systemd 看起来还可能显示服务正常。

这些错误让我意识到，写完配置、脚本和 systemd 单元后不能马上假设它已经正确。至少应该停下来检查文件名、参数名、路径和标点，再执行语法检查或查看服务日志。



### 4.2 权限和文件格式问题

这个实验中，我在密码文件和脚本权限上反复踩坑。

客户端密码文件必须只保存密码，并且只有所有者可以读取：

```text
内容：123456
路径：/etc/rsync.passwd
权限：600
```

我一开始忘了执行 `chmod 600`，rsync 直接拒绝使用密码文件。

服务端密码文件则必须保存“用户名:密码”：

```text
backup_user:123456
```

我最初把冒号写成了空格，后来虽然改对了格式，又忘记给文件设置 `600` 权限。服务端的认证依赖 `auth users`、密码文件内容和密码文件权限三者同时正确，少一项都可能出现 `auth failed`。

另一个容易漏掉的是模块目录的属主。配置中声明了：

```ini
uid = rsync
gid = rsync
```

因此 node2 的接收目录必须允许 `rsync` 用户写入。否则 daemon 能启动，但上传文件或删除文件时会出现 `Permission denied`。

脚本权限也让我迷惑过。使用：

```shell
bash /usr/local/bin/real_time_rsync.sh
```

可以运行，是因为真正执行的是 bash，脚本只需要读权限。但 systemd 的 `ExecStart` 直接执行脚本时，脚本本身必须具有执行权限。因此不能因为 bash 能运行就忽略 `chmod`。



### 4.3 防火墙和 SELinux 问题

这里需要先区分两件事：

- firewalld 负责放行 TCP 873。
- SELinux 负责控制进程可以执行、读取或写入哪些文件和端口。

我习惯把它叫作“深层防火墙”，但它实际是 SELinux。

客户端最初把脚本放在 `/root`，`ExecStart` 直接执行该脚本时，systemd 报出 `203/EXEC`。SELinux 日志中的关键记录是：

```text
avc: denied { execute }
scontext=system_u:system_r:init_t:s0
tcontext=unconfined_u:object_r:admin_home_t:s0
tclass=file permissive=0
```

这说明 systemd 的 `init_t` 进程域不能直接执行家目录中的 `admin_home_t` 文件。后来把脚本放到 `/usr/local/bin`，该位置通常使用更适合执行的 `bin_t` 标签，同时给脚本设置执行权限，服务才能正常启动。

因此，这里需要分别检查两件事：

```shell
chmod 755 /usr/local/bin/real_time_rsync.sh
ls -Z /usr/local/bin/real_time_rsync.sh
```

普通 Linux 权限检查和 SELinux 类型检查会同时发生，两者不能互相替代。

服务端也会遇到 SELinux 问题：daemon 可以启动并监听 873，但在接收文件时可能因为不能写入目标目录而失败。本实验使用了：

```shell
setsebool -P rsync_full_access on
```

这个布尔值可以放宽 rsync 的访问范围，适合当前实验验证；生产环境应根据实际目录设置更精细的 SELinux 文件上下文。

第三类问题涉及的进程域、文件类型和布尔值比较抽象。我一开始也没完全理解，只能通过 AVC 日志、`getenforce` 和实际同步结果逐项排查。它也是整个实验最耗时间的一类问题。





### 4.4 服务 active 但文件没有同步

这个实验中还有一个很容易误判的地方：`systemctl status rsync_real.service` 显示 `active`，但 node1 修改文件后，node2 一直没有收到。

原因是 `inotifywait -m` 会持续监控目录，它本身不会因为循环体执行失败而立即退出。所以服务看起来一直在运行，但真正处理事件的 `while read` 可能已经失败，rsync 根本没有被调用。

正确的循环写法是：

```bash
inotifywait -r -m \
  -e delete,modify,create,attrib \
  --format '%w%f %e' \
  "$DIR" |
while IFS= read -r dir action; do
    rsync -avz --delete \
      --password-file=/etc/rsync.passwd \
      "$DIR" "$TARGET" >>"$LOG" 2>&1
done
```

这里的分号是 shell 的命令分隔符。如果误写成冒号：

```bash
while read -r dir action:
```

`read` 会把 `action:` 当成非法变量名，循环体不执行，但 `inotifywait` 仍然继续运行。

排查时可以按下面顺序检查：

```shell
systemctl status rsync_real.service --no-pager
journalctl -u rsync_real.service -n 100 --no-pager
tail -n 100 /var/log/rsync.log
```

然后在 node1 手工创建文件：

```shell
touch /export/rsync_share/debug.txt
```

如果 `inotifywait` 收到了事件，但日志里没有 rsync 的执行结果，就要检查 `while read` 的语法和脚本是否已经重新加载。修改脚本后还应执行：

```shell
systemctl restart rsync_real.service
```

这个问题的关键在于：**服务 active 只说明监控进程没有退出，不能证明事件处理循环和 rsync 都执行成功。**

## 5. 总结

这个实验我连续做了好几天，几乎每天都会遇到新的错误，中间也确实非常烦躁。最后我从快照恢复环境，重新按步骤做了一遍，才真正独立完成。

现在回头看，真正麻烦的并不是某一条 rsync 命令，而是很难判断问题出在哪一层：

```text
systemd 服务没有起来
→ 脚本没有执行权限，或者被 SELinux 阻止
inotifywait 正常运行，但文件没有同步
→ while read 或 rsync 命令没有真正执行
daemon 正常运行，但目标端没有文件
→ 认证、目录属主、firewalld 或 SELinux 有问题
```

所以以后再做这类实验，我会先按顺序完成准备工作，而不是想到哪做到哪：

1. 安装软件包。
2. 创建用户和目录。
3. 设置目录属主和密码文件权限。
4. 编写并检查配置、脚本和 systemd 单元。
5. 启动服务并检查实际状态。
6. 分别验证新增、修改和删除。
7. 最后在 SELinux Enforcing 模式下再测一次。

这次实验让我最深的体会是：**服务显示 `active` 不代表功能一定成功，配置写完也不代表已经生效。** 只有逐层检查日志、权限和实际文件结果，才能确认整条同步链路真的可用。

这些就是我几天做实验积累下来的经验和体会，希望能帮助大家少走一些弯路。
