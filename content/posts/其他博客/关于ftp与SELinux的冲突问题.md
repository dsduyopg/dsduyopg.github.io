

@[TOC](关于ftp与SELinux的冲突问题)
# 1.问题背景
**首先这个问题诞生于如此条件下，我在跟随佳乐老师创建完lisi，zhangsan，wangwu之后呢，我就用lisi作为用户登录服务器node1，这里面设置了禁锢操作，路径是/export/public，而public里面拥有2个文件夹.一个是logs，另一个是src，同时设置了黑白名单,张三设置在黑名单，王五和李四设置在白名单**
# 2.遇到的问题
**1.遇到的问题其实就是，在我用lisi把客户端的根目录下的a.log，发送给服务器的logs目录，无法操作**
![在这里插入图片描述](https://i-blog.csdnimg.cn/direct/31d543a0e0d74a2facd0b57caacd8359.png)
**2.后来，我在logs目录下创建文件夹也是无法操作的，也是显示权限不足**
![在这里插入图片描述](https://i-blog.csdnimg.cn/direct/55c072190ed842009aa2962c3868c3fc.png)
==但是呢，我在服务器的这个logs目录下创建文件夹是可以创建的==
![在这里插入图片描述](https://i-blog.csdnimg.cn/direct/96f60e65512b4a38be2d95aa4d888fd8.png)

``3.就很奇怪，再去服务器是可以搞定的，是可以创建文件夹的，但是在客户端是没有办法进行创建的，我当时以为是logs的权限设置的不对，用的是root创建，权限大的缘故，但是其实并不是如此的,后面我在服务器用了lisi照样是可以创建的``
![在这里插入图片描述](https://i-blog.csdnimg.cn/direct/5596133494e8476a96424bbf30353246.png)
4.``后来，我仔细检查了这些文件夹的权限，并再次赋权,这次显然也是不行的``
![在这里插入图片描述](https://i-blog.csdnimg.cn/direct/ed81cf0aff1743229e25473bf7b232d7.png)

# 3.问题解决的方法
``解决的办法，后来，我把我的问题，这些比较奇怪的地方，我问了千文，后来，在他的帮助之下我成功了，在客户端我成功的在服务器的logs上面创建了文件夹，这意味着什么呢，显然这意味着，我可以把客户端家目录的a.log上传给服务器的logs里面，结果显然和我想的一样``
**下面是千文告诉我的解决方案，让我一步一步排查，最后成功找到了问题关键所咋**
## 1.ai的方法




这个对比信息非常关键！它直接帮我们**排除了文件系统权限问题**。

## 为什么本地能写、FTP 不能写？

本质区别在于**执行写入的"身份"不同**：

| 场景 | 执行者 | 受什么约束 |
|------|--------|-----------|
| 本地 `mkdir` | lisi 自己的 shell 进程 | 只看文件系统的 rwx 权限 ✅ |
| FTP `mkdir` | **vsftpd 守护进程**代为执行 | 受 `vsftpd.conf` 开关 + **SELinux 对 ftpd 的策略**双重约束 ❌ |

所以本地能写，**完全不能证明** FTP 也能写。问题 100% 卡在 FTP 守护进程这一层。下面两个是头号嫌疑。

---

## 嫌疑一：`write_enable` 没开（最常见！）

vsftpd 的 `write_enable` **默认是 NO**。如果配置文件里没显式写 `write_enable=YES`，那么所有写操作（上传、mkdir、删除、改名）一律拒绝，正好对应你看到的 `533` 和 `550`。而它**不影响读和 ls**，所以你能登录、能列目录。

```bash
grep -i write_enable /etc/vsftpd/vsftpd.conf
```

- 如果**没有这一行**，或显示 `write_enable=NO` → 就是它！

修复：
```bash
echo "write_enable=YES" >> /etc/vsftpd/vsftpd.conf
systemctl restart vsftpd
```

---

## 嫌疑二：SELinux 拦住了 ftpd

SELinux 是针对**守护进程上下文（ftpd_t）** 做限制的，本地 shell 不受这套规则管，所以同样会出现"本地行、FTP 不行"。

**最快验证法**——临时关掉 SELinux 测一次：
```bash
getenforce            # 先看状态，多半是 Enforcing
setenforce 0          # 临时切到宽容模式
```
然后**不要重启 vsftpd**，直接在客户端 lftp 里再 `mkdir` 一次：
- 如果**成功了** → 确认是 SELinux，永久解决：
  ```bash
  setsebool -P ftpd_full_access on
  setenforce 1        # 记得开回去
  ```
- 如果**还是失败** → 不是 SELinux，回到嫌疑一。

---

## 兜底：看日志，让服务器自己告诉你原因

```bash
# vsftpd / PAM 的拒绝记录
tail -n 30 /var/log/secure

# SELinux 的拒绝记录（最有价值）
ausearch -m avc -ts recent | grep ftp
# 或
cat /var/log/audit/audit.log | grep -i denied | tail
```
日志里会写明到底是 `write_enable` 拒绝，还是 SELinux 的 `avc: denied`。

---

## 建议的排查顺序

1. 先 `grep write_enable /etc/vsftpd/vsftpd.conf`，没有就加上并重启 → 重试
2. 还不行就 `setenforce 0` 重试 → 判断是否 SELinux
3. 都不行就看 `/var/log/secure` 和 `ausearch` 的报错贴给我

> 补充一句：你之前把 chroot 根目录 `/export/public` 设成 777 的话，记得要么改回 **755**，要么在配置里加 `allow_writeable_chroot=YES`，否则某些版本会直接拒绝登录。不过你现在能登录能 cd，说明这一项暂时没卡你，先聚焦上面两点。

把第 1 步 `grep` 的结果和第 2 步 `setenforce 0` 后的现象告诉我，基本就能一锤定音。
## 2.我看出了什么
``看了千文的描述，我知道了，大概率就是 SELinux 的权限问题，解决方案，千文也告诉我了``
```poweshell
`Enforcing` —— 这就对上了！SELinux 正处于**强制模式**，而它对 `ftpd` 守护进程的写操作是单独设防的，本地 shell 完全不受这套规则管，所以才会出现"服务器本地能 mkdir、客户端 FTP 不能"的典型症状。再加上你的目录在 `/export/public` 这种**自定义路径**下，SELinux 给它的文件类型往往不是 FTP 可写的类型，被拦几乎是必然的。

下面按顺序做，逻辑上能一次性把"开关"和"SELinux"两个变量都隔离清楚。

## 第 1 步：先确认写开关是开的（避免误判）

```bash
grep -i write_enable /etc/vsftpd/vsftpd.conf
```

- 如果**没有这一行**或显示 `write_enable=NO` → 补上并重启：
  ```bash
  echo "write_enable=YES" >> /etc/vsftpd/vsftpd.conf
  systemctl restart vsftpd
  ```
- 如果已经是 `write_enable=YES` → 不用动，直接下一步。

> 为什么先查它：写要成功必须 `write_enable` 和 SELinux **同时放行**。若这个开关没开，下一步关 SELinux 也救不活，会让你误以为"不是 SELinux 的锅"。

## 第 2 步：临时关掉 SELinux 做隔离测试

```bash
setenforce 0          # 切到宽容模式，立即生效，无需重启 vsftpd
getenforce            # 应显示 Permissive
```

## 第 3 步：回客户端 lftp 重试

```
lftp lisi@192.168.149.128
cd /logs
mkdir 222
```

## 看结果分支判断

**✅ 如果这次成功了** → 元凶确认含 SELinux。做**永久修复**（二选一）：

```bash
# 方案A：放开 ftpd 的整体访问（最省事，覆盖大多数场景）
setsebool -P ftpd_full_access on

# 方案B：只给目标目录打上"FTP可读写"的上下文（更精细、更安全）
semanage fcontext -a -t public_content_rw_t "/export/public/logs(/.*)?"
semanage fcontext -a -t public_content_rw_t "/export/public/src(/.*)?"
restorecon -Rv /export/public

# 修完务必把 SELinux 开回去验证
setenforce 1
```
开回 `Enforcing` 后再到客户端测一次，能写才算真正解决。

**❌ 如果 `setenforce 0` 后仍然失败** → 不是 SELinux（或不止它），去看日志，让服务器自报原因：

```bash
tail -n 30 /var/log/secure
ausearch -m avc -ts recent 2>/dev/null | grep -i ftp
```

---

⚠️ 提醒：`setenforce 0` 是**临时**的，机器一重启就恢复 `Enforcing`，所以验证完一定要执行上面的永久修复，别让它一直裸奔在宽容模式。

`请把 **第 1 步 `grep` 的输出** 和 **第 3 步关 SELinux 后客户端的现象** 发给我，基本就能一锤定音了。
## 3.我的解决方案
``显然，我是按照setenforce 0 之后，重启服务器，然后就可以了``
![在这里插入图片描述](https://i-blog.csdnimg.cn/direct/f7018adaac4d428abc446956a54d2284.png)


# 4.给我们的警示

``给我们的启发其实就是，在学习Linux过程之中，人工智能永远是你的最好的老师，只要你将自己的问题发给他，跟着他的提示一步一步进行排查，然后将排查得到的结果发送给ai，那么他将会告诉你一个中肯的建议，一般都是成功的，这个 SELinux 确实挺麻烦的，当时我以为是我的配置文件出错了，后来呢，我不断尝试，修改配置文件，但是依然没有成功，我才在千文的指导之下明白了他的存在。

