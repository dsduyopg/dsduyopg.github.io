---
comments: true
title: "Telegram 双备份系统实战：加密 + 明文双通道 + 机器人取文件"
date: 2026-08-18
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

我最怕的事，是电脑突然坏了。博客、课件、代码、考研资料，全都存在本地硬盘里，坏了就真的什么都没了。U 盘会丢、会坏；网盘要么容量小，要么限速，要么收费；而且都是手动上传，经常想不起来备份。

其实这个问题，我上一个项目就尝试解决过。当时我做了 Git 自动同步方案，先问了 AI 一个问题：远端仓库大小、单个仓库能存的文件数，到底有什么限制？它告诉我：Gitee 的空间限制比 GitHub 严格得多，空间小；GitHub 也不是无限的，同样有空间和单仓库大小的上限。

那时我就意识到，只靠 Git 一个小工具，解决不了所有备份问题。同步博客这种文件少、体积小的场景没什么压力，但一旦要同步课件、学习资料这类又多又大的文件，就很吃力了。Git 项目虽然也能备份，但只适合小文件。我需要探索一种新的范式，来摆脱这个困境。

我把上面的痛点整理成了明确的需求：

* **容量要大**——网盘装不下我的课件和学习资料
* **速度不能太慢**——别像某些网盘一样上传下载都限速
* **要自动**——手动上传总会忘，最好"文件一改，自动同步"
* **要异地保存**——电脑坏了、U 盘丢了，文件还在别处，能恢复
* **成本要低**——个人使用，不想年年交钱

国内网盘首先排除——要么容量小，要么要付费，要么限速。后来我想到了自己天天在用的那个 AI 机器人（bot）：它就部署在 Telegram 上，而 Telegram 的私有频道可以存放大量文件，这不正好和我的需求相符吗？容量近乎用不完，速度也够用，还能自动上传、异地保存。这就是这个项目的直接推动力。

下面我将详细介绍这个项目：从方案选型、系统架构，到一步步搭建、踩过的坑，再到整套系统的最终效果。



## 1.最终做成了什么

### 1.1如何想到的

最初我的需求是模糊的，只知道自己想要"大容量、低成本、自动化"，但具体怎么架构，脑子里还是一片空白。

转折点在做上一个项目（Git 自动同步）的时候。我问 AI：Git 能通过自动化实现本地仓库的推送，那 Telegram（简称 TG）能不能也通过脚本自动推送？当时它给的答案是"不能"——因为 Git 是通过命令行操作的，所以可以用脚本封装；而 TG 是图形界面，没有命令行入口，脚本很难直接操作。不过它给了我两个方向：

* 一个是利用 **Teldrive** 在 TG 上的 API 接口，可以通过命令直接执行

* 另一个是用 **Python（Telethon）**，通过代码直接调用 Telegram 的接口

* 这两个方向，后来正好成了我两条备份链路的雏形：**Teldrive 走加密备份，Telethon 走明文直传**——图形界面拦不住脚本，只要走对接口就行。
  
  ### 1.2最终的结果

一套 Windows 上的双备份系统：

* **加密备份**：Teldrive + PostgreSQL + rclone，文件分片加密后上传到私有频道，内容不可直接查看

* **明文直传**：Telethon 直传，文件在 Telegram 客户端里可以直接查看、下载

* **实时同步**：目录有变化，约 5~10 秒内自动上传；每小时还有全量同步兜底

* **机器人**：发命令查总目录、今日更新，回复序号就能把对应文件发到私聊

* **后台服务**：NSSM 注册三个 Windows 服务，开机自启、崩溃自动重启

* **一键安装包**：把整套系统封装成可以复制到其他电脑使用的安装包

电脑自动备份，手机也能直接传文件进频道，两边数据互通。

## 2.用到的技术

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

## 三.准备工作

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





## 四.架构

### 4.1项目架构

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

### 4.2系统架构



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

## 5.实施步骤

### 5.1.第 1 步：安装 Python



Python 官网下载 Windows 安装包，安装时**一定要勾选 "Add Python to PATH"**。

验证：

```powershell
python --version
```

能输出版本号就成功

![0c151313-21d6-4116-9322-db53f3ba6c87](./images/0c151313-21d6-4116-9322-db53f3ba6c87.png)



### 5.2.第 2 步：安装 PostgreSQL 17（原生服务，不用 Docker）

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



### 5.3.第 3 步：安装 Teldrive

Teldrive 是核心服务，负责把文件分片、加密、上传到 Telegram。把 `teldrive.exe` 放到 `%USERPROFILE%\.installer\bin\`，配置文件 `config.toml` 放到 `%USERPROFILE%\.teldrive\`（里面是占位符）：

```toml
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

必须改的 3 处
--------

| 行                             | 现在                  | 改成         | 为什么                 |
| ----------------------------- | ------------------- | ---------- | ------------------- |
| `data-source`                 | `DB_PASSWORD``5432` | 真实密码`5433` | 占位符密码 + 你实际端口是 5433 |
| `[jwt] secret`                | `"JWT_SECRET"`      | 随机长字符串     | 占位符，不换别人能伪造登录       |
| `[tg.uploads] encryption-key` | `"ENCRYPTION_KEY"`  | 随机密钥       | 占位符，加密通道靠它          |

建议改的 1 处
--------

| 行                     | 现在        | 建议改成        | 为什么                   |
| --------------------- | --------- | ----------- | --------------------- |
| `[jwt] allowed-users` | `[]`（不限制） | `["你的用户名"]` | 防止别人登录你的 Teldrive 蹭存储 |

不用动的行
-----

* `prepare-stmt = true` —— 保持开启即可

* `[db.pool]` 整个块 —— 25/10m/25 对单机够用，不用调

* `max-idle-connections` / `max-lifetime` / `max-open-connections` —— 同上

> 注意[jwt] secret和[tg.uploads] encryption-key这两行，密钥可以自己写，但是要注意密钥不能太短，太简单，长度要求32B,我们可以使用powershell自动生成密钥，以下是生成密钥的命令

```bash
$b = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [System.BitConverter]::ToString($b).Replace("-","")
```

![d8bcb257-407a-4e10-9813-332f1dac646a](./images/d8bcb257-407a-4e10-9813-332f1dac646a.png)

修改完配置文件，我们使用以下命令查看是否成功运行

```
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

```

![1893ba45-8516-4df2-96a6-e532633d72df](./images/1893ba45-8516-4df2-96a6-e532633d72df.png)

我通过使用以上命令发现成功的，可以正常使用teldrive服务



![4a57b6a7-d830-4a26-b4fc-24aca048b3ca](./images/4a57b6a7-d830-4a26-b4fc-24aca048b3ca.png)



这个是我已经在teldrive登录好的。

### 5.4.第 4 步：安装 Teldrive 专用 rclone（最关键的一步）

普通官方 rclone 不支持 `teldrive:` 后端，必须用 `github.com/tgdrive/rclone` 的 Teldrive 专用版。装完**必须验证后端**：

```powershell
& "$env:USERPROFILE\.installer\bin\rclone.exe" help backends
```

输出里必须能看到：

```text
> teldrive     Tel Drive
```

![f1c3f573-b486-43e8-ba97-54fda7477d2a](./images/f1c3f573-b486-43e8-ba97-54fda7477d2a.png)

到这一步，也没有问题，发现是可以显示teldrive     Tel Drive这两个服务的，其中，我刚开始安装这个服务的时候，用的并非是专用版本的是普通的，发现本地文件无法同步到远端了，后面的部分我会为大家详细介绍我遇到的这个问题。

### 5.5.第 5 步：安装 NSSM

NSSM 用来把脚本注册成 Windows 服务：

```powershell
nssm version
```

![d963c79d-57cf-40e4-b5fb-d5f1c1eefa2c](./images/d963c79d-57cf-40e4-b5fb-d5f1c1eefa2c.png)

### 5.6.第 6 步：安装 Python 依赖

```powershell
python -m pip install --upgrade telethon requests pillow
```

![5eeab885-0f95-4614-b1dc-ce63bbd72f7e](./images/5eeab885-0f95-4614-b1dc-ce63bbd72f7e.png)



### 5.7.第 7 步：创建 Telegram 私有频道

手机 Telegram 里创建两个频道（**必须是私有**）：一个加密频道，一个明文频道。把机器人添加进明文频道并设为管理员。

**本次，我就创建了private_database  linux_data私有频道，和一个机器人**



### 5.8.第 8 步：登录 Teldrive 并填 Token

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



### 5.9.第 9 步：注册三个 Windows 服务

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








