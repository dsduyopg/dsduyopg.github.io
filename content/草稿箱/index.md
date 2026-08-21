---
comments: true
title: "Telegram 双备份系统实战：加密 + 明文双通道 + 机器人取文件"
date: 2026-08-18
lastmod: 2026-08-21
draft: false
ShowToc: false
description: "用 Telegram 私有频道搭建免费自动备份系统：加密 + 明文双通道、实时同步、机器人取文件、一键安装包，全程 AI 写代码，含完整实施步骤和踩坑记录。"
tags: [Telegram, 备份, Teldrive, 自动化, AI辅助开发]

---



 {{< toc >}}

> 我怕电脑坏了，博客、课件、代码和考研资料全丢，于是用 Telegram 的私有频道给自己搭了一套免费的自动备份系统：加密 + 明文双通道，文件有变化 5 秒内自动上传，机器人随时查目录、按序号取文件，开机自启，最后还封装成了一键安装包。
> 
> 全程 AI 写代码，我只做需求设计、测试验证和问题排障。这篇文章把完整实施过程和踩过的坑都记录下来，想搭类似系统的人可以直接照着做。

> 声明：本文是 AI 辅助开发实践记录。代码由 AI 辅助生成，作者负责需求设计、方案选型、测试、部署和排障。文中出现的手机号、Token、频道 ID 均为占位符，请勿直接复制使用。

> **太长不看**
>
> - 用 Telegram 私有频道搭了一套免费双备份系统：加密备份 + 明文直传双通道
> - 文件变化后约 5~10 秒自动上传，每小时全量同步兜底
> - 机器人支持查目录、翻页、按序号取文件，Windows 服务开机自启
> - 完整记录 23 个实施踩坑，并封装成一键安装包
> - 需要准备：Windows 10/11 + Python 3.11+ + Telegram 账号

我最怕的事，是电脑突然坏了。博客、课件、代码、考研资料，全都存在本地硬盘里，坏了就真的什么都没了。U 盘会丢、会坏；网盘要么容量小，要么限速，要么收费；而且都是手动上传，经常想不起来备份。

其实这个问题，我上一个项目就尝试解决过。当时我做了 Git 自动同步方案，先问了 AI 一个问题：远端仓库大小、单个仓库能存的文件数，到底有什么限制？它告诉我：Gitee 的空间限制比 GitHub 严格得多，空间小；GitHub 也不是无限的，同样有空间和单仓库大小的上限。

那时我就意识到，只靠 Git 一个小工具，解决不了所有备份问题。同步博客这种文件少、体积小的场景没什么压力，但一旦要同步课件、学习资料这类又多又大的文件，就很吃力了。Git 项目虽然也能备份，但只适合小文件。我需要探索一种新的范式，来摆脱这个困境。

我把上面的痛点整理成了明确的需求：

* **容量要大**——网盘装不下我的课件和学习资料
* **速度不能太慢**——别像某些网盘一样上传下载都限速
* **要自动**——手动上传总会忘，最好"文件一改，自动同步"
* **要异地保存**——电脑坏了、U 盘丢了，文件还在别处，能恢复
* **成本要低**——个人使用，不想年年交钱

国内网盘首先排除——要么容量小，要么要付费，要么限速。后来我想到了自己天天在用的那个 Telegram 机器人（bot）：它就部署在 Telegram 上，而 Telegram 的私有频道可以存放大量文件，这不正好和我的需求相符吗？容量近乎用不完，速度也够用，还能自动上传、异地保存。这就是这个项目的直接推动力。

下面我将详细介绍这个项目：从方案选型、系统架构，到一步步搭建、踩过的坑，再到整套系统的最终效果。



## 1. 最终做成了什么

### 1.1 如何想到的

最初我的需求是模糊的，只知道自己想要"大容量、低成本、自动化"，但具体怎么架构，脑子里还是一片空白。

转折点在做上一个项目（Git 自动同步）的时候。我问 AI：Git 能通过自动化实现本地仓库的推送，那 Telegram（简称 TG）能不能也通过脚本自动推送？当时它给的答案是"不能"——因为 Git 是通过命令行操作的，所以可以用脚本封装；而 TG 是图形界面，没有命令行入口，脚本很难直接操作。不过它给了我两个方向：

* 一个是利用 **Teldrive** 在 TG 上的 API 接口，可以通过命令直接执行

* 另一个是用 **Python（Telethon）**，通过代码直接调用 Telegram 的接口

* 这两个方向，后来正好成了我两条备份链路的雏形：**Teldrive 走加密备份，Telethon 走明文直传**——图形界面拦不住脚本，只要走对接口就行。
  
### 1.2 最终的结果

一套 Windows 上的双备份系统：

* **加密备份**：Teldrive + PostgreSQL + rclone，文件分片加密后上传到私有频道，内容不可直接查看

* **明文直传**：Telethon 直传，文件在 Telegram 客户端里可以直接查看、下载

* **实时同步**：目录有变化，约 5~10 秒内自动上传；每小时还有全量同步兜底

* **机器人**：发命令查总目录、今日更新，回复序号就能把对应文件发到私聊

* **后台服务**：NSSM 注册三个 Windows 服务，开机自启、崩溃自动重启

* **一键安装包**：把整套系统封装成可以复制到其他电脑使用的安装包

电脑自动备份，手机也能直接传文件进频道，两边数据互通。

## 2. 用到的技术

| 组件                   | 作用                        | 为什么选它                  |
| -------------------- | ------------------------- | ---------------------- |
| Teldrive             | 文件分片、加密、上传 Telegram 的核心服务 | 开源，自带网页端和 API          |
| PostgreSQL 17        | 保存 Teldrive 的文件索引、分片、频道信息 | 原生 Windows 服务，稳定直观     |
| rclone（Teldrive 专用版） | 加密备份的同步工具                 | 只有专用版才带 `teldrive:` 后端 |
| Telethon             | 明文直传和机器人逻辑                | Python 的 Telegram 客户端库 |
| NSSM                 | 把脚本注册成 Windows 服务         | 开机自启、崩溃重启              |
| PowerShell           | 备份服务主逻辑                   | Windows 自带             |

几个关键决策，都写一下当时的考虑：

1. **为什么选 Telegram？** 免费、容量大、跨设备（电脑和手机都能访问）、不依赖国内网盘的速度和容量限制。缺点是依赖第三方平台，所以只作为异地副本，本地保留原文件。

2. **为什么加密和明文两条通道？** 加密备份安全，文件加密后都是乱码，查看必须依赖 Teldrive 网页端；一旦丢失密钥或配置文件，或者更换电脑，数据就成了死数据。明文直传恰好解决了这些缺点：可以跨设备直接查看文件，下载恢复不再依赖电脑，也不需要定期备份密钥，但安全性低。所以两个都要：重要资料走加密，日常文件走明文——方便读写、记录博客、查阅复习资料。

3. **为什么不用 Docker，用原生 PostgreSQL？** Docker 对服务器友好，但 Windows 本地使用多了一层虚拟化依赖，开机自启和维护不如原生服务直观，还会拖累开机速度、占用系统资源；原生服务更简单、更稳，不过首次配置要多花点心思。

4. **为什么 rclone 必须用 Teldrive 专用版？** 官方普通版 rclone 不认识 `teldrive:` 这个后端。这个问题曾经导致我的整个加密备份失效，我在实际操作中就踩过这个坑，提醒大家注意。

5. **为什么分片设 500 MB、默认覆盖模式？** 分片越大，Telegram 消息条数越少，方便管理；但又不能设得过大——传输 1G 左右的大文件时，中途失败不会从头重传，而是从断点继续。日常备份不需要每次修改都留历史版本，默认覆盖只保留最新版，需要版本历史的目录可以单独开启 version 模式；这样还能避免频道消息过多，触发官方限制，带来账号风险。

## 3. 准备工作

动手之前，除了上一节表格里的六个组件（Teldrive、PostgreSQL、rclone 专用版、Telethon、NSSM、PowerShell），还需要准备：

**环境与账号**

* Windows 10/11 电脑

* 一个 Telegram 账号（手机装好 App，用来接收登录验证码）

* 能正常访问 Telegram 的网络环境

**软件**

* Python 3.11 或更高版本（安装时勾选 Add Python to PATH）

* Python 依赖：`telethon`、`requests`、`pillow`

**频道与机器人**

* 两个 Telegram **私有**频道：一个加密频道，一个明文频道

* 一个机器人 token（在 `@BotFather` 创建）

> 本文重点讨论这套系统的架构思路，不是以安装这些组件为主，但是还是会把这个操作流程说一下的；把它们准备好再往下看，体验会更顺。

**组件安装顺序**

Python 3.11+ → PostgreSQL 17 → Teldrive → rclone 专用版 → NSSM → Python 依赖(telethon/requests/pillow)

**初始化顺序**

创建两个私有频道 → 登录 Teldrive 拿 token 填 rclone.conf → 登录 Telethon 存会话 → @BotFather 创建机器人填 token → NSSM 注册三个服务 → 添加备份目录并测试

**操作顺序**

Python → PostgreSQL → Teldrive → rclone → NSSM → 依赖库 → 频道 → Teldrive 登录 → Telethon 登录 → 机器人 → 注册服务 → 加目录测试





## 4. 架构

### 4.1 项目架构

先看这套系统装完之后长什么样。所有程序都放在用户目录下，加密备份和明文直传两条链路各自独立：

```text
%USERPROFILE%\.teldrive-backup\            ← 备份系统的"家"
├─ teldrive-backup.ps1      加密备份服务（rclone + Teldrive，分片加密上传）
├─ rclone.conf              rclone 配置（teldrive: 后端）
├─ backup-config.json       备份源、同步间隔、排除规则
├─ logs\                    同步日志
└─ direct\                  明文直传 + 机器人
   ├─ direct-watch.ps1      明文直传服务
   ├─ direct_upload.py      上传与机器人核心
   ├─ direct_config.json    频道、备份源配置
   ├─ bot_config.json       机器人配置（敏感，不展示）
   └─ meta\                 配置和数据库的每小时备份
```

全部验证通过后，我把这套系统封装成了一键安装包，可以在其他电脑上直接部署：

```text
一键安装包\
├─ setup.ps1         主入口（环境检查 / 安装 / 初始化 / 注册服务）
├─ backup.ps1        双备份统一菜单
├─ install-*.ps1     各组件安装模块
├─ modules\          公共安装逻辑
├─ files\            备份脚本本体
└─ 一键安装.bat      一键入口
```

### 4.2 系统架构



整套系统分两条备份链路，外加一个检索机器人，跑在三个 Windows 服务上。

```text
本地目录
  ├─ 加密备份: FileSystemWatcher -> rclone -> Teldrive API -> Telegram 私有频道（加密）
  └─ 明文直传: FileSystemWatcher -> Telethon -> Telegram 频道（可直接查看）

机器人
  ├─ /start 开始
  ├─ /status 查看状态
  ├─ /today 今日更新
  ├─ /all 全部目录
  ├─ 翻页 / 跳页 / 回复序号取文件
  └─ 每日更新 + 停止按钮
```

三个 Windows 服务：

| 服务             | 对应程序                        | 作用                    |
| -------------- | --------------------------- | --------------------- |
| TeldriveServer | `teldrive.exe run`          | Teldrive Web 服务 + API |
| TeldriveBackup | `teldrive-backup.ps1 watch` | 加密备份监听（rclone）        |
| TeldriveDirect | `direct-watch.ps1 watch`    | 明文直传监听（Telethon）      |

加密和明文两条链路互相独立，各自有频道、各自的锁和 manifest 日志，互不影响。

## 5. 实施步骤

### 5.1 第 1 步：安装 Python



Python 官网下载 Windows 安装包，安装时**一定要勾选 "Add Python to PATH"**。

验证：

```powershell
python --version
```

能输出版本号就成功

![0c151313-21d6-4116-9322-db53f3ba6c87](./images/0c151313-21d6-4116-9322-db53f3ba6c87.png)



### 5.2 第 2 步：安装 PostgreSQL 17（原生服务，不用 Docker）

安装完成后把服务设为自动启动：

```powershell
Set-Service -Name postgresql-x64-17 -StartupType Automatic
Start-Service postgresql-x64-17
```

> 注意：如果启动失败，先看 Windows 事件日志。我遇到过安全策略干扰，重启系统后恢复正常。

创建 Teldrive 的数据库账号和库（密码用占位符）：

```powershell
psql -U postgres -h 127.0.0.1 -p 5432 -c "CREATE ROLE teldrive LOGIN PASSWORD 'DB_PASSWORD';"
psql -U postgres -h 127.0.0.1 -p 5432 -c "CREATE DATABASE teldrive OWNER teldrive;"
```

> 注意：这里我们**不需要**把 PostgreSQL 注册成 NSSM 服务。
> 
> 原因：PostgreSQL 安装时就已经注册成了 Windows 原生服务（服务名 `postgresql-x64-17`），能直接被服务管理器（SCM）管理，停止服务时会走优雅关库流程（停连接、刷脏页、安全落盘）。而 NSSM 是用来把"不能自己当服务"的普通程序（脚本、exe）包装成服务的，给 PostgreSQL 套一层反而多一道中转，服务停止时可能变成直接杀进程，导致数据库非正常退出，下次启动就要走 recovery（恢复）流程。所以上面用 `Set-Service` / `Start-Service` 直接管理就够了。

![db3e9447-769d-4bf0-85dd-30995a2ed6ab](./images/db3e9447-769d-4bf0-85dd-30995a2ed6ab.png)

```bash
$env:Path += ";C:\Program Files\PostgreSQL\17\bin"
pg_isready -h 127.0.0.1 -p 5433
psql --version
#当前窗口直接刷新 PATH



pg_isready -h 127.0.0.1 -p 5433
Get-Service postgresql-x64-17
netstat -ano | findstr :5433
psql -U postgres -h 127.0.0.1 -p 5433 -c "SELECT version();"
#这个是校验这个数据库安成功的命令



```



### 5.3 第 3 步：安装 Teldrive

Teldrive 是核心服务，负责把文件分片、加密、上传到 Telegram。把 `teldrive.exe` 放到 `%USERPROFILE%\.installer\bin\`，配置文件 `config.toml` 放到 `%USERPROFILE%\.teldrive\`（里面是占位符）：

```toml
# ========== Teldrive 核心配置说明 ==========

[db]
# PostgreSQL 数据库连接串
# 格式：postgres://用户名:密码@地址:端口/库名
# ⚠️ DB_PASSWORD 是占位符，要换成真实密码
# ⚠️ 端口按自己实际的写（本文是 5433）
data-source = "postgres://teldrive:DB_PASSWORD@127.0.0.1:5433/postgres"

# 启用 SQL 预编译语句：性能更好，也能防 SQL 注入
prepare-stmt = true

[db.pool]
# 连接池开关
enable = true
# 空闲时最多保留的连接数（复用连接，省去反复建连的开销）
max-idle-connections = 25
# 单个连接最长存活时间，到期自动回收换新
max-lifetime = "10m"
# 同一时刻最大并发连接数，防止拖垮数据库
max-open-connections = 25

[jwt]
# 允许访问的用户名白名单；空数组 = 不限制，任何 Telegram 账号都能用
# 建议填上自己的用户名，如 ["my_username"]，防止别人蹭你的存储
allowed-users = []

# JWT 签名密钥（登录令牌用它签发和验证）
# ⚠️ 必须换成随机长字符串，不要用字面量 JWT_SECRET，否则别人能伪造登录
secret = "JWT_SECRET"

[tg.uploads]
# 上传文件的加密密钥（对应"加密通道"）
# 设置了 = 文件先本地加密再传 Telegram，存的是密文
# 留空   = 明文直接传（明文通道）
# ⚠️ 密钥丢失后已加密的文件永远无法解密，务必备份！
encryption-key = "ENCRYPTION_KEY"
```

**必须改的 3 处**

| 行                             | 现在                  | 改成         | 为什么                 |
| ----------------------------- | ------------------- | ---------- | ------------------- |
| `data-source`                 | `DB_PASSWORD``5432` | 真实密码`5433` | 占位符密码 + 你实际端口是 5433 |
| `[jwt] secret`                | `"JWT_SECRET"`      | 随机长字符串     | 占位符，不换别人能伪造登录       |
| `[tg.uploads] encryption-key` | `"ENCRYPTION_KEY"`  | 随机密钥       | 占位符，加密通道靠它          |

**建议改的 1 处**

| 行                     | 现在        | 建议改成        | 为什么                   |
| --------------------- | --------- | ----------- | --------------------- |
| `[jwt] allowed-users` | `[]`（不限制） | `["你的用户名"]` | 防止别人登录你的 Teldrive 蹭存储 |

**不用动的行**

* `prepare-stmt = true` —— 保持开启即可

* `[db.pool]` 整个块 —— 25/10m/25 对单机够用，不用调

* `max-idle-connections` / `max-lifetime` / `max-open-connections` —— 同上

> 注意[jwt] secret和[tg.uploads] encryption-key这两行，密钥可以自己写，但是要注意密钥不能太短，太简单，长度要求32B,我们可以使用powershell自动生成密钥，以下是生成密钥的命令

```bash
$b = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [System.BitConverter]::ToString($b).Replace("-","")
```

![d8bcb257-407a-4e10-9813-332f1dac646a](./images/d8bcb257-407a-4e10-9813-332f1dac646a.png)

修改完配置文件，我们使用以下命令查看是否成功运行

```text
# 第 1 层：进程正常、端口在听
Get-Process teldrive                     # 能看到进程
netstat -ano | findstr :8080             # 8080 在监听

# 第 2 层：Web 可访问（返回 200）
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8080

# 第 3 层：确认新配置真的连上了数据库（能查到一行即成功）
psql -U postgres -h 127.0.0.1 -p 5433 -d postgres -c "SELECT usename, state FROM pg_stat_activity WHERE usename='teldrive';"
```

三条快速判断：进程存在 + 8080 返回 200 = 配置文件格式正确；pg_stat_activity 能查到 teldrive 连接 = 密码/端口改对了；浏览器能登录并能上传下载文件 = 全部配置生效。
常见坑：`psql` 报"不是内部命令"是因为 PostgreSQL 的 bin 目录没加进 PATH，用完整路径 `"C:\Program Files\PostgreSQL\17\bin\psql.exe"` 代替即可

![1893ba45-8516-4df2-96a6-e532633d72df](./images/1893ba45-8516-4df2-96a6-e532633d72df.png)

我通过使用以上命令确认 Teldrive 服务可以正常使用。

下图是我已经登录好的 Teldrive 网页。

![4a57b6a7-d830-4a26-b4fc-24aca048b3ca](./images/4a57b6a7-d830-4a26-b4fc-24aca048b3ca.png)

### 5.4 第 4 步：安装 Teldrive 专用 rclone（最关键的一步）

普通官方 rclone 不支持 `teldrive:` 后端，必须用 `github.com/tgdrive/rclone` 的 Teldrive 专用版。装完**必须验证后端**：

& "$env:USERPROFILE\.installer\bin\rclone.exe" help backends

输出里必须能看到：

```text
> teldrive     Tel Drive
```

![f1c3f573-b486-43e8-ba97-54fda7477d2a](./images/f1c3f573-b486-43e8-ba97-54fda7477d2a.png)

到这一步，也没有问题，发现是可以显示teldrive     Tel Drive这两个服务的，其中，我刚开始安装这个服务的时候，用的并非是专用版本的是普通的，发现本地文件无法同步到远端了，后面的部分我会为大家详细介绍我遇到的这个问题。

### 5.5 第 5 步：安装 NSSM

NSSM 用来把脚本注册成 Windows 服务：

```powershell
nssm version
```

![d963c79d-57cf-40e4-b5fb-d5f1c1eefa2c](./images/d963c79d-57cf-40e4-b5fb-d5f1c1eefa2c.png)

### 5.6 第 6 步：安装 Python 依赖

```powershell
python -m pip install --upgrade telethon requests pillow
```

![5eeab885-0f95-4614-b1dc-ce63bbd72f7e](./images/5eeab885-0f95-4614-b1dc-ce63bbd72f7e.png)



### 5.7 第 7 步：创建 Telegram 私有频道

手机 Telegram 里创建两个频道（**必须是私有**）：一个加密频道，一个明文频道。把机器人添加进明文频道并设为管理员。

**本次，我就创建了private_database  linux_data私有频道，和一个机器人**



### 5.8 第 8 步：登录 Teldrive 并填 Token

`access_token` **不是填在 Teldrive 网页里**，而是填回你本机 rclone 的配置文件 `rclone.conf` 中 `[teldrive]` 段落的那一行——把 `PASTE_ACCESS_TOKEN` 这个占位符替换成真正的 token 字符串即可。
**具体操作**

**第 1 步：从浏览器拿到 token**

1. 浏览器打开 `http://localhost:8080`，用 Telegram 登录 Teldrive
2. 登录成功后，按 **F12**​ 打开开发者工具 → 切到 **Application（应用**​ 或 Storage（存储）**​ 选项卡 → 找**Cookies​ → `http://localhost:8080`
3. 在 cookie 列表里找到名为 **`access_token`**​ 的那条，复制它的 **Value**​ 值

> 💡 如果你的 cookie 里没有 `access_token`，只有 **`user_session`**，那就复制 `user_session` 的值——它就是旧版本里的 access token。

**第 2 步：填回 rclone.conf**

找到 rclone 的配置文件（一般在 `~/.config/rclone/rclone.conf` 或 Windows 下 `C:\Users\<用户名>\.config\rclone\rclone.conf`），把 `[teldrive]` 段改成：
    [teldrive]
    type = teldrive
    api_host = http://localhost:8080
    access_token = 这里粘贴你刚复制的那串长字符串
    chunk_size = 500M
    upload_concurrency = 4
    encrypt_files = true
    random_chunk_name = true
    channel_id = 0
    root_folder_id =

注意几点：

* `access_token =` 后面**直接粘字符串**，不要带引号（官方示例虽然写了引号，但实际 INI 配置里值通常不包引号）
* **删掉**​ `PASTE_ACCESS_TOKEN` 这个占位符，它就是提示你"粘贴到这里"的意思
* `root_folder_id` 不填就是根目录，可留空

改完保存，然后跑 `rclone ls teldrive:` 测试一下能不能列出文件，能列出来就说明 token 填对了。

> ⚠️ 这个 token 就是你 Telegram 账号的会话凭证，**等同于登录态**，别泄露给别人。

如果你是用 `rclone config` 命令交互式添加的，它会在 `access_token>` 这一行让你粘贴，效果和在文件里改是一样的。

![15cc275e-e5f9-42d1-adc1-a3934d2197d4](./images/15cc275e-e5f9-42d1-adc1-a3934d2197d4.png)

验证连通：

```powershell
& "$env:USERPROFILE\.installer\bin\rclone.exe" lsd teldrive: --config "$env:USERPROFILE\.teldrive-backup\rclone.conf"
```

能看到目录就说明通了。

![874da9db-aa78-4a7f-a417-fe816a40b35e](./images/874da9db-aa78-4a7f-a417-fe816a40b35e.png)



**第三步**

由于前几步我们安装了Telethon，这一步，我们需要给telethon登录



| 方式         | 需要什么                              | 没有的        |
| ---------- | --------------------------------- | ---------- |
| 手机号登录      | api_id + api_hash + 手机号 + 验证码     | 不需要 token  |
| **Bot 登录** | api_id + api_hash + **bot_token** | 不需要手机号/验证码 |

注意：**即使是 bot 登录，api_id 和 api_hash 也还是要的**（Telethon 用它标识客户端），只是不用手机号那一步。

**这里我以手机登录为主**
手机号登录（明文直传用）

------------

步骤

1. 写一个登录脚本（或你的 `direct_upload.py`），填入 api_id/api_hash：
   
   

```python
Python from telethon import TelegramClient api_id = 123456 # 换成你的 
api_hash = "你的hash" # 换成你的 
client = TelegramClient("user_session", api_id, api_hash) client.start() # 触发登录流
print("登录成功")
```



1. 运行脚本，按提示依次输入：
   
   * **手机号**（带国家码，如 `+8613800000000`）
   
   * **验证码**（Telegram 发到 APP/短信，5 位数字）
   
   * **两步验证密码**（如果你的账号开启了 2FA，才会问）

2. 提示 `登录成功`，当前目录会生成 **`user_session.session`** 文件

3. 之后每次运行自动复用 session，**不再需要重新登录**（除非删了 session 文件）

> 对应你博客里的命令就是：`python direct_upload.py login --phone +8613800000000`，脚本内部封装了上面这套流程。



### 5.9 第 9 步：注册三个 Windows 服务

用 NSSM 注册（以加密备份为例）：

```powershell
nssm install TeldriveBackup "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.teldrive-backup\teldrive-backup.ps1" watch
nssm set TeldriveBackup Start SERVICE_AUTO_START
nssm start TeldriveBackup
```

**注意**：NSSM 服务环境不会继承普通用户 PATH，必须显式设置 `PYTHON_EXE`、`RCLONE_EXE` 等变量，否则服务找不到 Python。

![366edd51-071e-4790-9dbf-efaba4397a1a](./images/366edd51-071e-4790-9dbf-efaba4397a1a.png)



![812f7201-257c-4edb-bef9-aaf85e75f46d](./images/812f7201-257c-4edb-bef9-aaf85e75f46d.png)



![3b134cf8-308f-4be3-ab47-3e183100ccd3](./images/3b134cf8-308f-4be3-ab47-3e183100ccd3.png)

### 5.10 第 10 步：添加备份目录

加密备份：

```powershell
set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

![68804f73-485a-4896-add3-6e31cc0b407d](./images/68804f73-485a-4896-add3-6e31cc0b407d.png)



选 `1) Add backup folder`。明文直传先选 `4) List chats`、`5) Set target chat`，再选 `1) Add backup folder`。

添加完成后，目录一有变化就会自动上传。



![afb83185-5688-49ad-b1fb-2969488bfe89](./images/afb83185-5688-49ad-b1fb-2969488bfe89.png)



![d3f37fe2-3945-4216-80ab-8c772cbaea44](./images/d3f37fe2-3945-4216-80ab-8c772cbaea44.png)



这里面在direct 备份里我选择

D:\linux\linux_heima chat: -1004425264068 prefix: linux_heima mode: overwrite
D:\picture chat: -1004387615517 prefix: picture mode: overwrite
D:\my-blog chat: -1004476355877 prefix: my-blog mode: overwritete  这两个目录，我将为大家验证是否，可以自动备份





## 6. 验证



经过验证，脚本是可以进行自动备份的，随后我将这两脚本封装成为一个脚本，一个界面.



**我在备份的时候选择的是，忽视隐藏文件**

* 隐藏目录/隐藏文件是脚本故意跳过的。`should_skip_path` 会跳过任何以 `.` 开头的路径、`.log` 文件和 0 字节文件。目前 `D:\linux\linux_heima` 有 269 个、`D:\my-blog` 有 310 个隐藏文件被跳过，`direct_state.json` 里也确实没有任何隐藏路径。
* 普通文件均已同步完成：三个备份源当前待传均为 0，`direct_state.json` 记录与本地文件保持一致
  
  

这个是我在脚本加入了统计隐藏文件，实际备份文件的功能，这样，我们校对起来是比较容易的



![d650cdb2-ffa0-4585-b647-9e06d73a7745](./images/d650cdb2-ffa0-4585-b647-9e06d73a7745.png)

同时，我在频道里加了 `manifest.txt` 统计文件。manifest 不是由本地备份的，所以不计入本地统计；验证后发现 `linux_heima` 可以正常自动备份，其他目录同理。





然后我会在机器人上面也进行验证



![0250845a-b84a-4bf5-93ce-c54b4df43229](./images/0250845a-b84a-4bf5-93ce-c54b4df43229.png)



![8c070a03-a42e-48b2-8eb0-3a9bf77ac0e1](./images/8c070a03-a42e-48b2-8eb0-3a9bf77ac0e1.png)



![d0b4bc6c-175d-46ac-8ab4-6614562ca1e0](./images/d0b4bc6c-175d-46ac-8ab4-6614562ca1e0.png)







![d82552b4-cd2e-4765-9853-93c4a87f2919](./images/d82552b4-cd2e-4765-9853-93c4a87f2919.png)



文件改动测试



![66263a0c-6362-4014-8c1d-60263e149a1a](./images/66263a0c-6362-4014-8c1d-60263e149a1a.png)

追加内容之后



![d586642f-e3a8-4efa-bfd5-21fbf23aba28](./images/d586642f-e3a8-4efa-bfd5-21fbf23aba28.png)





app显示出来的



![b68f8118-d437-4cf8-85b5-b4716fc3353b](./images/b68f8118-d437-4cf8-85b5-b4716fc3353b.png)



![cadf1da0-a5e7-466f-8fdd-9e578b819537](./images/cadf1da0-a5e7-466f-8fdd-9e578b819537.png)



经过校验，加密备份和明文备份都验证成功。从文件备份、读取，到灾备恢复和异常处理，这套系统都能覆盖；需要加密的重要资料可以走加密通道，同时必须妥善备份密钥。整个项目也从最初的模糊概念，逐步打磨成基于 Teldrive 和 Telethon 的“加密 + 明文”双轨备份方案。下面从原理细节展开核心实现。

## 7. 技术原理

### 7.1 原理细节

#### 1.1技术原理总览

| 技术                | 解决什么问题            | 核心原理                            |
| ----------------- | ----------------- | ------------------------------- |
| FileSystemWatcher | 监听目录变化            | Windows 文件系统事件                  |
| Debounce 防抖       | 避免频繁触发上传          | 事件后等待 N 秒再执行                    |
| 文件锁               | 防止多个同步同时执行        | 独占打开锁文件                         |
| rclone sync       | 加密备份同步            | 对比本地和远端差异                       |
| Teldrive          | 分片、加密、上传 Telegram | 调用 Telegram API 上传分片            |
| PostgreSQL        | 保存文件索引            | 记录文件、分片、频道状态                    |
| Telethon          | 明文直传              | Telegram MTProto 客户端库           |
| 状态文件              | 记住已上传文件           | 保存 size、mtime、message_id        |
| manifest          | 记录目录和日期           | 本地生成日志上传频道                      |
| 长轮询               | 机器人接收消息           | getUpdates 定时拉取                 |
| 回调按钮              | 机器人交互             | Inline Keyboard + callback_data |
| NSSM              | 开机自启              | 把命令注册成 Windows 服务               |



#### 1.2核心概念详解

##### 1.2.1 FileSystemWatcher：文件监听

```powershell
PowerShell 用 `System.IO.FileSystemWatcher` 监听目录： $w = New-Object System.IO.FileSystemWatcher $w.Path = $src.path $w.IncludeSubdirectories = $true $w.NotifyFilter = [System.IO.NotifyFilters]::FileName -bor ` [System.IO.NotifyFilters]::LastWrite -bor ` [System.IO.NotifyFilters]::Size -bor ` [System.IO.NotifyFilters]::CreationTime $w.EnableRaisingEvents = $true Register-ObjectEvent -InputObject $w -EventName Changed -MessageData $message -Action $action Register-ObjectEvent -InputObject $w -EventName Created -MessageData $message -Action $action Register-ObjectEvent -InputObject $w -EventName Deleted -MessageData $message -Action $action Register-ObjectEvent -InputObject $w -EventName Renamed -MessageData $message -Action $action

要点：

* `IncludeSubdirectories = $true` 监听子目录
* `NotifyFilter` 只关心文件名、修改时间、大小、创建时间
* 事件触发后不立即同步，而是把目录标记为 dirty
```



##### 1.2.2Debounce：防抖

写文件时系统会触发多次事件，直接同步会浪费资源。

所以事件回调只做两件事：

```powershell
$st.dirty[$key] = $true $st.lastChange[$key] = [DateTime]::UtcNow
```



主循环每次检查：

```powershell
$last = $state.lastChange[$key] if ($last -and (($now - $last).TotalSeconds -ge $DebounceSeconds)) { $due += $key }
```



只有距离最后一次变化超过 `debounceSeconds` 才真正同步。

##### 1.2.3 文件锁：防止重复同步

两个进程不能同时执行 rclone 或 Telethon 上传，否则会产生重复记录。

锁的原理是独占打开文件：

```powershell
$stream = [System.IO.File]::Open( $lock, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None )
```



第二个进程尝试打开时会被拒绝，返回 `$null`，表示“另一个同步正在运行”。

##### 1.2.4 手动同步优先级

手动执行 `Sync now` 时，如果后台正在同步，不能直接杀掉 rclone，否则可能留下半成品数据库记录。

方案：

* 手动同步创建 `sync.priority` 文件
* 后台循环发现该文件后，停止下一个任务
* 手动同步等待当前文件传完，然后获取锁执行
* 手动执行完成后删除 priority 文件
* 后台下一轮从头继续

##### 1.2.5 rclone sync：加密备份同步

核心命令：

```powershell
& $RcloneExe sync `
    $source.path `
    "teldrive:backup/$($source.remotePath)" `
    --config $RcloneConfig `
    --create-empty-src-dirs `
    --transfers 4 `
    --checkers 8 `
    --log-file $log `
    --log-level INFO
```

含义：

* `sync` 让远端和本地一致
* `teldrive:` 是 Teldrive 专用 rclone 后端
* `--create-empty-src-dirs` 保留空目录
* `--transfers 4` 同时上传 4 个文件
* `--checkers 8` 同时检查 8 个文件

##### 1.2.6 Teldrive 后端

Teldrive 是 Telegram 网盘服务：

* 文件切成多个分片
* 分片加密后上传 Telegram
* PostgreSQL 保存文件索引和分片 ID
* rclone 通过 `teldrive:` 后端调用 Teldrive API

```text
# rclone.conf
[teldrive]
type = teldrive
api_host = http://localhost:8080
access_token = PASTE_ACCESS_TOKEN
chunk_size = 500M
upload_concurrency = 4
encrypt_files = true
random_chunk_name = true
channel_id = 0
root_folder_id =
```



关键参数：

| 参数                   | 含义          |
| -------------------- | ----------- |
| `chunk_size`         | 分片大小，500 MB |
| `upload_concurrency` | 并发上传数       |
| `encrypt_files`      | 是否加密文件      |
| `random_chunk_name`  | 分片文件名是否随机化  |
| `channel_id`         | 上传到哪个频道     |

##### 1.2.7 PostgreSQL 的作用

数据库表 `teldrive.files` 保存：

* 文件名
* 文件类型
* 大小
* 状态：`active`、`pending_deletion`
* 频道 ID
* 分片信息 `parts`
* 父目录 ID
* 哈希

索引是恢复的关键，只删 Telegram 消息不删索引，会导致 rclone 认为文件还在。

##### 1.2.8 Telethon：明文直传

Telethon 是 Python 的 Telegram MTProto 客户端库。

```powershell
登录： python direct_upload.py login --phone +8613800000000

上传： async def upload_one(client, chat, file_path, name, message_id=None, mode="overwrite"): if mode == "overwrite" and message_id: try: await client.edit_message( chat, message_id, file=str(file_path), text=name, force_document=True, ) return True, message_id except Exception as exc: print("edit failed, sending new:", name, exc) msg = await client.send_file( chat, str(file_path), file_name=name, caption=name, force_document=True, ) return True, msg.id
```



##### 1.2.9 overwrite 和 version 两种模式

overwrite：

* 查找同名旧消息
* 用 `edit_message` 覆盖原文件
* 频道里只保留最新版

version：

* 不查找旧消息
* 每次直接 `send_file`
* 每次修改都保留为新消息

##### 1.2.10 状态文件：记住已上传文件

直接上传脚本用 `direct_state.json` 保存状态：

```powershell
sig = { "size": stat.st_size, "mtime": int(stat.st_mtime), } entry = state.get(key) if entry and entry.get("size") == sig["size"] and entry.get("mtime") == sig["mtime"]: continue

key 的组成： 本地根目录 + 频道 ID + 远端文件名

只有 size 或 mtime 变化，才重新上传。
```



##### 1.2.11 manifest 日志和轮替

manifest 是频道文件目录，记录：
    文件名 | 修改时间 | 覆盖时间 | 添加时间

超过 `manifest_max_size`（默认 50 MB）后自动轮替：

```powershell
rotated = manifest_path.with_name( manifest_path.stem + "-" + stamp + manifest_path.suffix ) manifest_path.replace(rotated)

只保留最近 `manifest_max_files`（默认 10）份。
```



##### 1.2.12 机器人长轮询

机器人使用 Telegram Bot API 的 `getUpdates`：

```powershell
url = "https://api.telegram.org/bot" + token + "/getUpdates?timeout=2&offset=" + str(offset) updates = json.loads(urllib.request.urlopen(url, timeout=5).read().decode("utf-8"))

`offset` 表示已经处理到哪个 update，处理完后写回 `bot_offset.txt`，避免重复处理。
```



##### 1.2.13 回调按钮

目录消息带 Inline Keyboard：

```powershell
{ "text": "上一页", "callback_data": "page_prev", }, { "text": "下一页", "callback_data": "page_next", }, { "text": "跳转到页码", "callback_data": "jump_page", }
```



用户点击后，Telegram 返回 `callback_query`，机器人根据 `callback_data` 处理。

##### 1.2.14 NSSM 服务

NSSM 把任意命令注册成 Windows 服务：

```powershell
nssm install TeldriveBackup powershell -NoProfile -ExecutionPolicy Bypass -File "...\teldrive-backup.ps1" watch nssm set TeldriveBackup Start SERVICE_AUTO_START nssm set TeldriveBackup AppEnvironmentExtra "PYTHON_EXE=..." "RCLONE_EXE=..." nssm start TeldriveBackup
```



服务环境必须显式设置，因为服务不继承用户 PATH。

##### 1.2.15 pending 和 orphan 清理

pending 清理：

1. 查询数据库 `status='pending_deletion'` 的分片消息 ID
2. 用 Telethon 删除 Telegram 旧消息
3. 删除数据库 pending 记录

orphan 清理：

1. 查询数据库 active 分片消息 ID
2. 扫描频道所有消息
3. 删除数据库中不存在、但频道里残留的旧消息

##### 1.2.16 元数据备份

加密脚本可以把 `config.toml`、`rclone.conf`、数据库 dump 上传到频道，防止配置丢失。

注意：

* 配置和密钥属于敏感信息
* 如果配置本身加密，需要额外保存解密方式
* 建议单独放到一个只有自己能访问的频道
  
  

### 7.2 脚本细节

#### 2.1 teldrive-backup.ps1

总行数约 1100 行，核心函数：

| 函数                                   | 作用                      |
| ------------------------------------ | ----------------------- |
| `Get-Config` / `Save-Config`         | 读写 `backup-config.json` |
| `Get-NormalizedPath`                 | 路径标准化                   |
| `Test-PathOverlap`                   | 防止父子目录重复备份              |
| `Add-BackupDir` / `Remove-BackupDir` | 管理备份源                   |
| `Sync-Source`                        | 执行一次 rclone sync        |
| `Sync-All`                           | 同步所有目录                  |
| `Get-SyncLock` / `Release-SyncLock`  | 互斥锁                     |
| `Test-RcloneReady`                   | 检查 Teldrive 是否可用        |
| `New-Watchers` / `Remove-Watchers`   | 文件监听                    |
| `Watch-Service`                      | 后台服务主循环                 |
| `Invoke-PendingCleanup`              | 删除 pending 旧消息          |
| `Invoke-OrphanCleanup`               | 删除孤儿消息                  |
| `Repair-Channel`                     | 重建频道索引                  |
| `Purge-Channel`                      | 清空整个频道                  |
| `Backup-Metadata`                    | 备份配置和数据库                |

同步前检查后端：
    function Test-TeldriveBackend {
        $help = & $RcloneExe help backends 2>&1 | Out-String
        return $help -match 'teldrive'
    }
    if (-not (Test-TeldriveBackend)) {
        throw "rclone does not include the teldrive backend: $RcloneExe"
    }

后台服务主循环：
    while ($true) {
        try {
            # 1. 配置变化时重载
            # 2. 检查 dirty 目录是否过了防抖时间
            # 3. 检查 Teldrive 是否可用
            # 4. 获取锁，逐个同步
            # 5. 同步后清理 pending 和 orphan
            # 6. 每 60 分钟做一次全量同步
            # 7. 每 60 分钟清理旧日志
        } catch {
            Write-Host "[watch] error: $_"
        }
        Start-Sleep -Seconds 2
    }

#### 2.2 direct-watch.ps1

总行数约 860 行，核心函数：

| 函数                                      | 作用                    |
| --------------------------------------- | --------------------- |
| `Invoke-DirectPython`                   | 调用 `direct_upload.py` |
| `Get-DirectLock` / `Release-DirectLock` | 扫描互斥锁                 |
| `Invoke-DirectScan`                     | 执行一次上传扫描              |
| `Add-Source` / `Remove-Source`          | 管理明文备份源               |
| `Restore-Direct`                        | 恢复远端文件                |
| `New-Watchers` / `Remove-Watchers`      | 文件监听                  |
| `Watch-Service`                         | 明文服务主循环               |
| `Push-MetaDirect`                       | 上传配置和状态               |
| `Purge-ChatDirect`                      | 清空频道                  |
| `Set-BotSchedule`                       | 设置机器人每日发送时间           |
| `Set-ManifestSize`                      | 设置 manifest 大小        |

服务启动时会：

1. 先做一次初始扫描
2. 上传 manifest
3. 上传 meta 状态
4. 清理 meta 重复记录
5. 进入监听循环

#### 2.3 direct_upload.py

总行数约 1470 行，是明文直传和机器人的核心。

命令：

| 命令              | 作用                |
| --------------- | ----------------- |
| `login`         | Telegram 登录       |
| `chats`         | 列出会话              |
| `set-chat`      | 设置默认频道            |
| `scan`          | 扫描并上传             |
| `changed`       | 检查是否有变化           |
| `restore`       | 恢复远端文件            |
| `paths`         | 列出远端路径            |
| `manifest`      | 生成 manifest       |
| `delete-remote` | 删除远端路径            |
| `purge-chat`    | 清空频道              |
| `clean-pending` | 清理 pending        |
| `clean-orphans` | 清理孤儿              |
| `clean-saved`   | 清理 Saved Messages |
| `clean-meta`    | 清理 meta 重复        |
| `bot-check`     | 机器人长轮询            |
| `bot-digest`    | 发送每日更新            |

扫描上传核心逻辑：

```powershell
async def cmd_scan(args): cfg = load_config() state = load_state() async with TelegramClient(cfg["session"], API_ID, API_HASH) as client: await client.connect() pending = [] for s in cfg.get("sources", []): root = s["path"] chat = s.get("chat") or cfg["chat"] prefix = s.get("prefix") or "" mode = (s.get("mode") or "overwrite").lower() for path in sorted(Path(root).rglob("*")): if not path.is_file(): continue if should_skip_path(path): continue rel = remote_name(Path(root), path) name = (prefix + "/" + rel) if prefix else rel key = root + "|" + str(chat) + "|" + name stat = path.stat() sig = {"size": stat.st_size, "mtime": int(stat.st_mtime)} entry = state.get(key) if entry and entry.get("size") == sig["size"] and entry.get("mtime") == sig["mtime"]: continue existing = entry.get("message_id") if entry else None pending.append((chat, path, name, key, sig, mode, existing)) # 并发上传 sem = asyncio.Semaphore(4) async def worker(item): async with sem: ok, mid = await upload_one(client, chat, path, name, existing, mode) if ok: state[key] = { "size": sig["size"], "mtime": sig["mtime"], "message_id": mid, "uploaded_at": int(time.time()), } save_state(state) await asyncio.gather(*(worker(item) for item in pending))

恢复： async def cmd_restore(args): async with TelegramClient(cfg["session"], API_ID, API_HASH) as client: await client.connect() async for message in client.iter_messages(cfg["chat"]): if not message.document: continue name = (message.message or "").strip() if remote and name != remote and not name.startswith(remote + "/"): continue target = dest / Path(name) target.parent.mkdir(parents=True, exist_ok=True) await message.download_media(file=str(target))

恢复时的安全检查： if rel.is_absolute() or ".." in rel.parts: print("skip unsafe name:", name) continue
```



#### 2.4 安装模块

一键安装包由多个模块组成：

| 文件                            | 作用                    |
| ----------------------------- | --------------------- |
| `setup.ps1`                   | 主入口                   |
| `backup.ps1`                  | 双备份统一菜单               |
| `install-rclone.ps1`          | 安装 Teldrive 专用 rclone |
| `install-teldrive.ps1`        | 安装 Teldrive           |
| `install-nssm.ps1`            | 安装 NSSM               |
| `install-postgres.ps1`        | 安装/检测 PostgreSQL      |
| `install-services.ps1`        | 注册服务                  |
| `modules/common.ps1`          | 公共函数                  |
| `modules/init-teldrive.ps1`   | 初始化数据库和配置             |
| `modules/init-direct.ps1`     | 初始化明文直传               |
| `modules/install-runtime.ps1` | 安装运行环境                |

安装 rclone 的修复后逻辑：
    $rcloneZip = Join-Path $dirs.InstallDir 'rclone-tgdrive-windows-amd64.zip'
    $rcloneUrl = Get-GithubAssetUrl 'tgdrive/rclone' 'windows.*amd64.*\.zip$'
    Download-File $rcloneUrl $rcloneZip
    # 安装后校验后端
    $backendOk = & (Join-Path $dirs.BinDir 'rclone.exe') help backends 2>&1 | Out-String
    if ($backendOk -notmatch 'teldrive') {
        throw 'Installed rclone does not include the teldrive backend'
    }

#### 2.5 bat 入口

bat 的作用：

* 调用 PowerShell
* 保持菜单循环
* 选择退出才关闭窗口

注意事项：

* 必须使用 CRLF 换行
* 内容尽量用 ASCII
* 中文编码容易在 GBK 下被拆坏

## 8. 实施过程中遇到的问题与解决



### 1. Chrome 无法登录 Teldrive，Edge 可以

现象：

- Chrome 打开 Teldrive 网页反复失败
- 换 Edge 后可以正常登录

原因：

- 多为浏览器缓存、Cookie 或扩展拦截

解决：

- 清理 Chrome 缓存和站点 Cookie
- 临时关闭广告拦截/隐私扩展
- 或直接使用 Edge 完成登录

状态：已解决。

### 2. 使用原生 PostgreSQL 而不是 Docker

现象：

- 不想依赖 Docker，希望数据库作为 Windows 原生服务运行

原因：

- Docker 增加一层虚拟化，维护和开机自启不如原生服务直观

解决：

- 安装 PostgreSQL 17 原生版
- 注册为 Windows 服务 `postgresql-x64-17`
- 配置 `teldrive` 数据库和账号

状态：已解决。

### 3. PostgreSQL 服务无法启动

现象：

- `Start-Service postgresql-x64-17` 报错

原因：

- 系统 Device Guard / 相关安全策略干扰，重启后恢复正常

解决：

- 检查服务账户和日志
- 重启 Windows
- 确认服务设置为 Automatic

状态：已解决。

### 4. Telegram 频道显示 600 多个文件，本地只有 500 多个

现象：

- `private_database` 客户端显示 600+ 文件
- 本地实际文件少于该数字

原因：

- 频道里残留历史消息、重复上传、旧分片
- Telegram 客户端缓存旧数量

解决：

- 用 Telethon 脚本统计真实消息数
- 清空频道消息和数据库记录后重新上传
- 客户端退出重进刷新

状态：已解决。

### 5. 清空频道后再次同步只上传 2 个文件

现象：

- 手动删除频道文件后，再次同步只上传了少量文件

原因：

- 只删了 Telegram 消息，数据库索引还在
- rclone 认为远端仍存在文件，不再上传

解决：

- 正确步骤：先删除 Telegram 消息，再清空数据库文件记录
- 再执行同步

状态：已解决。

### 6. 加密备份产生重复记录

现象：

- 同一文件出现多条记录
- 几 MB 的文件被分成多个片段

原因：

- 旧记录被标记为 `pending_deletion`，未及时清理
- 早期分片大小过小
- 本地源路径重复或父子目录重叠

解决：

- 同步后自动删除旧消息和孤儿消息
- 分片大小调整为 500 MB
- 禁止同一频道下父子目录重叠
- 排除隐藏文件、`.log`、0 字节文件

状态：已解决。

### 7. rclone 报 HTTP 500

现象：

- `Internal Server Error`

原因：

- Teldrive 服务临时故障或并发请求过高

解决：

- rclone 自动重试
- 等待后重试
- 清理孤儿分片

状态：已解决。

### 8. 机器人按钮没有反应

现象：

- 点击“总目录”“今日更新”没有回复

原因：

- 目录消息太长，超过 Telegram 单条消息限制，发送时报 HTTP 400

解决：

- 改为分页发送，每页 20 条
- 增加上一页 / 下一页 / 跳转页码按钮

状态：已解决。

### 9. 机器人把文件发到了 Saved Messages

现象：

- 回复序号取文件，文件跑到“已保存消息”

原因：

- 远端文件用 Telethon 以当前账号发送给自己，Telegram 自动放进 Saved Messages

解决：

- 改为机器人 `copyMessage` / `forwardMessage` 直接转发到私聊
- 增加清理 Saved Messages 残留的命令

状态：已解决。

### 10. 手机上传的文件在机器人目录里看不到

现象：

- 手机直接传文件/图片到频道，`/all` 里没有

原因：

- 目录扫描只识别 document 消息
- 手机图片默认是 photo 消息，不是 document

解决：

- 目录同时扫描 document / photo / video
- 无标题图片显示为 `photo_xxx.jpg`
- 选择序号后直接转发

状态：已解决。

### 11. 0 字节文件无法上传

现象：

- Telegram 报 `The number of file parts is invalid`

原因：

- Telegram 无法上传 0 字节文件

解决：

- 上传前过滤 0 字节文件

状态：已解决。

### 12. bat 双击一闪而过

现象：

- 双击 bat 窗口立即关闭

原因：

- bat 使用 LF 换行，Windows 批处理解析异常
- 中文编码在 GBK 下被拆坏

解决：

- 改为 CRLF 换行
- bat 内容改为纯英文 ASCII

状态：已解决。

### 13. bat 执行后直接退出，无法回到菜单

现象：

- 选择操作后，按任意键就退出

解决：

- 改为 `goto` 标签循环菜单
- 只有选择“退出”才关闭

状态：已解决。

### 14. 添加备份路径失败，提示 mode must be overwrite or version

现象：

- 选择“浏览文件夹”后添加失败

原因：

- PowerShell 变量 `$mode` 和参数 `$Mode` 同名冲突
- 选择“2 浏览”后 `Mode` 被写成 `2`

解决：

- 把局部变量改名为 `$choose`

状态：已解决。

### 15. 输入 q 报错

现象：

- 设置 manifest 大小或机器人时间时输入 `q` 报类型转换错误

解决：

- 支持 `q` 取消
- 非法输入提示后返回，不再崩溃

状态：已解决。

### 16. NSSM 后台服务找不到 Python

现象：

- `TeldriveBackup` 服务日志显示 python not found

原因：

- 服务环境没有继承用户 PATH

解决：

- 在 NSSM 服务环境变量中显式设置 `PYTHON_EXE`
- 同时设置 `TELDRIVE_DIRECT_ROOT`

状态：已解决。

### 17. Telethon 会话数据库被锁

现象：

- `database is locked`
- `telegram session is busy`

原因：

- 多个进程同时使用同一个 Telegram 会话

解决：

- 增加 tg.lock 互斥锁
- 清理过期锁文件
- 避免手动命令和后台服务同时运行

状态：已解决。

### 18. manifest 每小时都更新

现象：

- 备份源包含脚本、配置、数据库 dump
- 这些文件变化后不断上传

原因：

- 工具自身文件也在备份源内

解决：

- 明确 manifest 的更新来源
- 可选：把工具目录从备份源中排除

状态：已理解并记录。

### 19. manifest 需要日志轮替

需求：

- 日志超过设定大小后自动新建文件
- 保留最近 N 份历史

实现：

- 默认 50 MB 轮替
- 保留最近 10 份
- 每个频道使用独立 manifest 文件

状态：已实现。

### 20. 本地日志无限增长

解决：

- 默认保留 30 天
- 每小时自动清理
- 增加手动清理命令

状态：已实现。

### 21. rclone 不认识 teldrive 后端，加密备份突然失效

现象：

- `private_database` 不再同步新文件
- 服务日志反复出现：

```text
CRITICAL: Failed to create file system for "teldrive:":
didn't find backend called "teldrive"
```

- 之前一直正常，某次操作后突然全部失败

原因：

- 加密备份依赖 Teldrive 专用版 rclone，它才带 `teldrive` 后端
- 一键安装包旧版从 `downloads.rclone.org` 下载官方普通版 rclone
- 某次运行安装/修复流程时，官方版 v1.75.0 覆盖了原来的 Teldrive 专用版
- 之后每次调用 rclone 都不认识 `teldrive:`，所以同步全部失败

解决：

- 用 `rclone help backends` 检查是否包含 `teldrive`
- 下载 `github.com/tgdrive/rclone` 的 Teldrive 专用版替换
- 旧官方版另存为 `rclone-v1.75.0-official.exe` 备份
- 重新触发同步，确认频道恢复更新
- 修改一键安装包：rclone 改为从 `tgdrive/rclone` 下载，安装后校验后端
- 环境检查增加后端校验
- 备份脚本同步前先检查后端，缺失时直接给出明确错误

状态：已解决，并已加入脚本和一键安装包。

### 22. 加密备份不实时同步（private_database 频道长时间不更新）

现象：

- 本地新增/修改文件后，加密备份不马上上传
- `private_database` 频道长时间没有新记录
- 明文直传脚本正常，只有加密备份不正常

原因：

- `TeldriveBackup` 服务原本只依赖 `FileSystemWatcher`
- `FileSystemWatcher` 会漏事件（大批量复制、程序直接写入、事件积压时）
- 漏掉事件后，原实现要等很久的整点扫描，最长 60 分钟才上传
- 本次一次性新增 400+ 文件（`博客\CSDN博客本地留档`）时全部漏掉，导致频道一直不更新

解决：

- 新增 `Get-DirSignature`：统计目录内有效文件数和最后修改时间总和
- `Watch-Service` 增加 5 秒轮询，每次比对目录签名，发现变化立即标记为待同步
- 保留 `FileSystemWatcher` 做事件触发，两者互为兜底
- 同步完成后记录签名，避免重复同步
- 已同步更新：本机脚本、一键安装包脚本、项目复盘代码原文、一键安装包 zip
- 新增 `重启加密备份服务.bat`，重启后新监听逻辑生效

状态：已修复。后台正在自动追赶本次漏掉的 400+ 文件，追赶期间手动同步和自动同步共用锁，不会产生重复记录。

### 23. 手动同步中断后 sync.priority 残留，实时同步再次停止

现象：

- `private_database` 长时间不更新
- `service.stdout.log` 反复出现 `[watch] manual sync requested, stopping background sync`
- `logs\sync.priority` 文件一直存在且时间很久

原因：

- 手动 `sync` 启动时写入 `sync.priority`，如果窗口在等待锁或同步过程中被关闭，文件不会删除
- 旧逻辑只判断文件是否存在，残留文件会让后台同步一直放弃

解决：

- 新增 `Test-PriorityBlocking`：`sync.priority` 超过 10 分钟视为残留并自动删除
- 后台监听和周期同步统一使用该判断
- 已同步更新：本机脚本、一键安装包脚本、项目复盘代码原文
- 手动删除残留文件并重启 `TeldriveBackup` 后，后台立即恢复同步



## 9. 总结

### 9.1 成果回顾

这次项目从最初的模糊想法到最终落地，带给我的收获比预期大得多。回头对照最初列的 5 个需求——容量近乎无限、速度够用、文件变化 5 秒内自动上传、异地保存、零持续成本——全部达成了。加密通道保护重要资料，明文通道随时手机取文件，两者互补；再加上和上一个 Git 自动同步项目配合，小文件走 Git、大文件走 Telegram，算是真正解决了我的备份焦虑。

### 9.2 AI 辅助开发的真实体会

关于 AI 辅助开发：全程代码确实是 AI 写的，但我做的事情并不只是"提需求"。需求拆解、方案选型、测试验证、问题定位、优先级裁定、锁机制设计——这些决策每一步都要我自己判断。AI 是执行力，我是架构师和测试员。这次经历让我意识到，即使不手写每一行代码，理解系统逻辑和排障思路依然是核心能力。后面有时间我一定会去深究那些锁、防抖、优先级判定的具体实现——这些才是真正属于我的东西。

整个过程中我先后尝试了多种 AI 辅助工具，从最初的方案探索到最终的代码实现，AI 大幅降低了“把想法变成可运行系统”的门槛。但工具再强，提不出正确的问题、判不准方案的优劣，AI 也帮不上忙。

### 9.3 踩坑之后的收获

这个项目比上一个 Git 流水线项目难度大得多——日志轮替、冲突管理、密钥生成、格式问题、版本冲突，每一个坑背后都涉及操作系统、网络协议、数据库和并发编程的知识。我自觉对这些学科的理解还很浅，但边做边查、反复测试，最终还是把理论上可行的方案变成了能稳定运行的系统。这种"先论证可行性 → 反复讨论方案 → 不断测试修改"的工程方法，我觉得比具体技术本身更值得记住。

### 9.4 资源与后续

整套脚本和一键安装包已经发布到 Telegram 频道，包含 2026-08-21 的稳定性修复（菜单锁冲突、机器人编码、文件统计去重），感兴趣的朋友可以自取试用：https://t.me/blogdata_hub

后续计划：给加密备份加版本保留模式、给机器人加文件搜索功能、探索用 Telegram 做家庭多设备共享存储。

### 9.5 写在最后

做这个项目的过程中我最大的感受是：服务本质就是在解决冲突——进程冲突、文件锁冲突、上传去重冲突、事件丢失与补扫的冲突。这些思想和 Linux 下解决资源竞争的思路是一脉相承的。

如果你也想搭一套自己的双备份，可以从本文的环境检查开始，逐步安装、添加目录、测试恢复，最后再交给服务自动运行。安装包下载后，先跑环境检查，再按步骤安装；遇到问题，优先看服务日志和 manifest 统计，往往比瞎猜更快。

最后提醒两件事：加密密钥丢了，已加密的数据基本等于永久丢失；自己的 token、配置和会话文件不要公开分享。备份的核心不是“上传了多少”，而是“丢了之后能恢复多少”。祝大家备份无忧。
