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



这里我将配置文件的hosts allow写成了host allow,然后在服务项里将Install写成小写了，WantedBy也都写成小写了，将multi-user.target我拼成了multi-user.targer Service模块里的

```shell
ExecStart=/usr/bin/rsync --daemon --config=/etc/rsyncd.conf --no-detach
```

我写成了

```shell
ExecStart=/usr/bin/rsync --daemon --config=/etc/rsyncd.config --no-detach
```

也就是给conf文件写成了config，这里是服务器的拼写错误



在客户端的拼写错误也不遑多让，这里是将符号写错了

```shell
 while read -r dir action;
```

这里原来就是；可是我将其写成了：

以及也是在服务项里把



```shell
Restart=on-failure
```

写成了Restart=on-faliure,这些拼写的错误，多的很，其实此类问题也是最好规避的，我写完文件的时候，没有仔细检查，觉得写完就是写完了，其实不是这样的，写完也要看一下，代码书否逻辑实现了最重要的就是检查是否拼写错了，每次写完配置文件，脚本文件，服务文件，都要停下来，多看看，我可能太急躁了，不能静下心来，不断有拼写错误，这是不能容忍的，检查完核对完，发现和自己的思路一致，字母没有一点问题，就可以点击:x了，这类问题也是最好规避的。



### 4.2 然后就是格式问题了



这是一个老大难的问题了，我在完成这个实验的时候，会忘记给密码本赋予600 路径赋予专门的用户，我是在客户端忘记给我的密码本rsyncd.paswd授予600，同时呢，脚本的执行权柄我也没有授予，我当时看到bash ok呀，可以直接正常的执行该脚本，这是最为重要的一点，然后我就没有授予，客户端其他的倒是没有什么了

然后就是服务器了，这里当然也是没有正确的授予600给密码本，rsnyc的用户和组授予本地的相应目录，然后我的密码本格式也是问题原来应该是backup_user：·123456但是呢，我写成了backup_user 123456将：写成了 空格，这里出现的问题，我觉得也是可以尽量避免的，虽然有些格式如此设置有底层的要求，但是呢可以做完一个实验记下来一个，有些格式的设置也是比较的容易的，理解起来比较简单，比如node2设置的路径，因为我在本地配置文件声明了只能由rsynd访问，所以必须设置为rsync 这些仔细一想，自己就是会明白的，不需要知道如此多的依赖



### 4.3 然后就是防火墙的问题了



对于端口设置的防火墙比较容易，这里讨论就是深层防火墙，首先呢，在客户端要尽量避免设置在家目录，`ExecStart` 直接执行家目录脚本时，systemd 的 `init_t` 进程域需要获得对 `admin_home_t` 文件的 `execute` 权限。默认 SELinux 策略不授予该权限，因此服务报 `203/EXEC`。将脚本安装到 `/usr/local/bin` 后，文件通常继承 `bin_t` 类型，同时设置 `755` 权限，systemd 才能按预期执行。普通权限检查和无害的 SELinux 标签检查必须分别处理。所以这个就要放置在/usr/local/bin/下面的



对于服务器的话，sel是会阻止这个同步服务传送文件的，需要将服务器的rsync在sel的权限也放开，我服务端其也没有很好的设置sel策略。导致同步出现了问题

```shell
setsebool -P 'rsync_full_access' on
```



其实这就是我遇到的这三了问题，第三类问题也最问难以理解上下文，我知道的也不多 布尔值我也是看网上资料设置的，这个其实也是我这几天遇到的问题，我将其归纳为3类，但是这里面的每一个问题，当时都困住了我好长时间，非常烦躁，我正是靠着codex给我一点一点排查我的虚拟机问题，给出改进方案，我才得以将这个实验完成





## 5. 总结

这个实验，其实也是比较麻烦的，我做了好几天，关键的是，每天都有新的错误诞生，我极其的烦躁，每天都不断练习这个实验项目，但终究是搞定了这个实验，我昨天终于独立搞定了，其中的每个错误都是不小的挑战，极其麻烦，比如深层防火墙，我服务开起来了，就忘记开放这个深层防火墙了，好多东西写着写着，我都突然忘记了，直接进入下一步，准备工作我没有做好，我都开始，写入配置文件，脚本了，所以我觉得，以后再做此类实验的时候，应当首先完成的是，基于准备工作的完成，准备工作完成之后，可以开启下一项的目标，我可能当时操作的顺序太乱了，想到哪，我就操作到哪里，没有一点顺序可言，这样操作一定会导致忘记应该完成的基本工作，比如创建目录，安装软件包



   其他的都没有什么，这是我这几天做实验的一些心得体会吧，写出来，希望对于大家有些帮助，可以帮助大家节约一些时间。
