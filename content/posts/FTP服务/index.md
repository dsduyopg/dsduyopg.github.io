---
comments: true
title: "FTP服务"
date: 2026-08-18
draft: false
ShowToc: false
---
{{< toc >}}

## 一.⽂件传输协议FTP


**FTP（File Transfer Protocol） 是⼀种⽤于在⽹络上进⾏⽂件传输的协议，允许⽤⼾通过客⼾端和
 服务器之间上传、下载⽂件.**


![在这里插入图片描述](images/83e9af719357492fa331d2d8183b5234.png)


## 二.FTP的两种⼯作模式


### 主动模式


`主动模式，其实就是请求是由客户端发起的，但是数据传输过程则是由服务器发过来的`


```
1- 客⼾端与服务器之间建⽴ 控制连接，通常是通过端⼝ 21（即 FTP 的默认控制端⼝）
2- 当客⼾端准备接收数据时，它会通过 随机端⼝（通常是 20 以外的端⼝）向服务器请求建⽴
数据连接
3- 服务器通过控制连接得知客⼾端的端⼝号后，从端⼝ 20（服务器的 FTP 数据端⼝） 发起⼀
个连接到客⼾端指定的端⼝，⽤于数据传输

```


- 优势


```
1 服务器主动向客⼾端发起数据连接，通常对⼤多数服务器来说，这种⽅式较容易实现。

```


- 缺点


```
因为客⼾端通常位于防⽕墙或 NAT 后⾯，防⽕墙可能阻⽌来⾃服务器的外部连接，所以这种模式
可能会受到⽹络环境的限制，尤其在客⼾端位于 NAT 后时，可能⽆法建⽴连接。

```


![在这里插入图片描述](images/9f4b1f259e854013a1bbd34c0f159f19.png)


### 被动模式


`被动模式，其实就是请求是由客户端发起的，但是数据传输过程则是由客户端发过来的`


```
客⼾端与服务器之间建⽴ 控制连接（通常是端⼝ 21）。
客⼾端请求服务器在某个端⼝（⼀个随机端⼝）上等待数据连接。
服务器响应并告知客⼾端该数据端⼝号。
客⼾端随后向该端⼝发起连接进⾏数据传输。

```


- 优势


```
被动模式能更好地穿越防⽕墙和 NAT，因为所有连接都是由客⼾端发起的，服务器只是监听连
接，不会主动连接客⼾端。

```


- 缺点


```
需要服务器配置和开放更多的端⼝（通常是端⼝范围），可能会导致⼀些安全隐患

```


![在这里插入图片描述](images/c3c8e7e4424143fdaeebe80ae6a5ce30.png)


![在这里插入图片描述](images/c80ef31facd0464aa11ed36837456451.png)


```
总结：
• 主动模式：服务器发起数据连接，适合客⼾端有公⽹ IP 的情况，但可能受到客⼾端防⽕墙或 NAT
的限制。
• 被动模式：客⼾端发起数据连接，适⽤于客⼾端位于防⽕墙或 NAT 后时，能够绕过这些⽹络限制，
安全性和兼容性更⾼。

```


## 三.FTP服务器搭建


### 1.准备


`在这里，我们需要准备两台主机，一台充当服务器node2，另一台充当客户端node1`


### 2.服务端配置


#### 1.安装软件vsftp


`首先我们需要使用命令dnf install -y vsftpd`


```
dnf install vsftpd

```


#### 2.启动并配置 vsftpd 服务


`这里面我们需要使用系统服务，将他在本次活动中启动，以及在下一次开机的时候启动`


```
systemctl start vsftpd
systemctl status vsftpd
systemctl enable vsftpd

```


#### 3. 配置防⽕墙


`我们在使用ftp服务的时候，我们必须要做到，开放端口，但是呢，由于服务器的端口的开放是随机的，因此我们无法在防火墙里面采用端口的方式添加，只能采用依靠服务的方式添加了`


```
ss -tunlp #这里呢我们是查看服务的端口是21

```


![在这里插入图片描述](images/4d41dbcfc68a415dbae5741a479b5c69.png)


```
#然后我们知道的是，21端口显然不是这个服务用到的所有端口，21端口只是客户端的端口
firewall-cmd --permanent --add-service=ftp
firewall-cmd --reload

```


**然后呢，我这一步就相当于解决了，接下来呢，我们就要进行下一步了**


#### 4.基本访问配置修改配置文件


**这里呢，我们需要修改服务器的配置文件，这样才可以进行访问的**


注意，我们是在/etc/vsftp/vsftp.conf里面修改配置文件的


#### 准备工作


```
#前置：创建⼀个⽤于共享的⽬录,已经在⽬录下创建⼏个⽂件
mkdir -p /anon
echo 'hello' >> /anon/a.txt
echo 'hi' >> /anon/b.txt

```


#### 修改配置文件


以下是需要修改的地方的


```
#修改配置：
vi /etc/vsftpd/vsftpd.conf
#设置以下⼏个配置项：
anonymous_enable=YES # 允许匿名⽤⼾访问
anon_root=/anon # 设置匿名⽤⼾默认的根⽬录
anon_upload_enable=YES # 允许匿名⽤⼾上传⽂件
anon_mkdir_write_enable=YES # 运⾏匿名⽤⼾创建⽂件夹
anon_other_write_enable=YES # 允许匿名⽤⼾删除和重命名⽂件
#注意：修改配置⽂件， 记得重启下FTP服务
systemctl restart vsftpd

```


### 3.客⼾端配置


`这个其实与服务器是很类似的，只不过呢，这个不需要配置防火墙，不需要修改配置文件`


### 1.安装软件


`我们需要下载的软件其实就是lftp`


```
dnf install lftp -y

```


### 2.连接ftp服务器


```
#格式1：lftp ftp://用户名:密码@服务器ip地址
#格式2：lftp ftp://服务器ip地址(匿名)

```


![在这里插入图片描述](images/53951331a2fa459e9ddbec3956b4d4a9.png)


### 4. windows浏览器访问


- 打开windows⽂件资源管理


![在这里插入图片描述](images/87a401f5ce864ae68e04bb2adb02f956.png)


- 地址栏中输⼊：ftp://192.168.149.128


![在这里插入图片描述](images/7c4f998ad29e41fdb53e505e2a888c5b.png)


`我们发现，在客户端登陆的时候是无法修改名字的`


![在这里插入图片描述](images/463cb3644ab848c19420418467e62561.png)


**我把windows里的图片复制到服务器里面也是不行的**
 ![在这里插入图片描述](images/e77af62a25a74a09aed2b565323d6753.png)


**我通过赋予111文件夹777权限那么的话，是有权力对他进行修改的**


![在这里插入图片描述](images/c3291384f3ed4609aaf922dcc5357710.png)


![在这里插入图片描述](images/1f044d86c24a4ac1ac31930e40c3598d.png)


发现在客户端里面是可以创建的


**我再次把一张图片移动到这个文件夹里面发现是可以的**


![在这里插入图片描述](images/83c2ca194a694f1fbd15b01d6dc43acb.png)


### 1根目录是不能放权的


**我们把根目录也放权为777，我们来看一下结果**


![在这里插入图片描述](images/7a9ea84083f0406f89dafc55e50807cd.png)


**然后，当我们在客户端登陆的时候，会发现用ls /会出现500错误**


![在这里插入图片描述](images/8d0261af95f344f68bcaea8ca5899cc8.png)


## 四.禁⽌匿名⽤⼾访问


### 1.修改配置文件


**这个是在/etc/vsftpd/vsftpd.conf 的文件进行修改，**


```
anonymous_enable=NO # 禁⽤匿名⽤⼾访问
local_enable=YES # 允许本地⽤⼾登录
write_enable=YES # 允许写⼊操作（上传⽂件）
#保存⽂件并退出，重启服务
systemctl restart vsftpd

```


### 2.创建⼀个普通⽤⼾⽤于后续访问FTP


**这一步如果电脑有其他用户的话，就不需要创建了，我就用itheima**


### 3.node1 客⼾端访问查看


```
lftp ftp://⽤⼾名[:密码]@ftp服务器主机地址

```


![在这里插入图片描述](images/468e282d1ad6410a9a34dc3e011b95b5.png)


windows访问


![在这里插入图片描述](images/8e9bd60c11ed46b7838aa84ec3f82e5b.png)


![在这里插入图片描述](images/79bf3109fa16461e84d49574df1e15e3.png)


## 五.禁锢在指定的数据⽬录中


### 1.创建⼀个本地⽤⼾的数据⽬录


**这里我们需要在data里面创建要给kefu文件夹**


```
mkdir -p /data/kefu
echo 'hello' >> /data/kefu/a.txt

```


### 2.修改配置⽂件


```
vi /etc/vsftpd/vsftpd.conf
# 添加以下内容
local_root=/data/kefu # 设置默认访问的路径地址 ,如果不指定， 默认访问的是该⽤⼾的家
# 修改以下内容： 前⾯的#去除即可
chroot_local_user=YES # 限制所有本地⽤⼾（即服务器上的普通⽤⼾）只能访问他们的 home
#保持退出后，重启vsftpd服务
systemctl restart vsftpd


```


### 3.创建⽤⼾， 指定⽤⼾的家⽬录为禁锢的数据⽬录下


**这个我们还用itheima**


### 4.客⼾端测试访问


lftp ftp://ftpuser:123@192.168.88.102六.⽤⼾名单列表使⽤


## 七.⽤⼾名单列表使⽤


- 1.给配置文件/etc/vsftpd/vsftpd.conf里面涉及到的禁锢命令给禁用掉

- 2.把/etc/vsftpd这个黑名单文件的root给注释掉


![在这里插入图片描述](images/c528408b83454a7687b272762b1c9295.png)


- 3.在配置文件/etc/vsftpd/vsftpd.conf里面把userlist_enable=YES启用用户名单


![在这里插入图片描述](images/0ebfc28d384a4300ae4f3b34a32d8824.png)


- 4.我们重启服务


```
systemctl restart vsftpd
systemctl status vsftpd

```


- 5.测试连通性


![在这里插入图片描述](images/b27d88b8b6d54dfca5e600d80a22574e.png)


注意：开了黑白名单，要是不在白名单里面那么就在黑名单里面把user_list里面的root给注释掉，那么我再次用ftp服务访问128主机的话，是不能访问的，原因就是这个，因为此时他在黑名单里面的如果在配置文件里面把userlist_enable设置为NO就相当于不使用黑白名单了，此时如果删掉白名单里面的root是不影响用ftp访问128主机的。
