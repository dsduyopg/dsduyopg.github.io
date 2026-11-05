---
comments: true
giscusMapping: "og:title"
utterancesIssueTerm: "og:title"
title: "基于 Cloudflare R2 + 商汤大模型的类若依项目低成本改造"
slug: "zzyl-r2-sensenova-lowcost"
date: 2026-11-05
lastmod: 2026-11-05
draft: false
ShowToc: false
description: "把类若依（养老）项目从阿里云 OSS + 付费大模型，改成本机跑通 + Cloudflare R2 + 商汤日日新的低成本方案。"
tags: ["Linux", "Cloudflare R2", "商汤", "Spring Boot", "MySQL", "Redis", "低成本改造"]
---

{{< toc >}}

> **前言**
> 
> 这次的项目我拆成了 3 篇博客来写，分别侧重不同的目的。**本篇是第一篇**，目标是让类若依项目能在**本机成功运行**——把后端、前端、以及两个外部依赖（对象存储、大模型）在本地跑通。**第二篇**做服务器部署与成功运行，也就是把项目打成包、部署到服务器上跑起来。**第三篇**做服务器后期的运维管理，包括日志、DNS、Nginx 这些配套设施。
> 
> 之所以要拆开，是因为这次的项目**比较庞大**：从本地环境到服务器上线，再到后期运维，跨度大、环节多，一篇写不下，也容易把读者绕晕。所以拆成三篇，每一篇有自己的目标、自己的验收，读者可以按需选读，望知悉。

## 0. 项目内容

这是一个**类若依项目**——以**若依框架为底座**、在上面叠加了**养老业务**模块的项目。它采用**前后端分离**的方案实现：后端是 Spring Boot 多模块工程（包名 `com.zzyl`），前端是 Vue3 单页应用，两边通过接口通信，本篇主要在本机做验证。

这个项目跟普通的"纯业务"项目不一样的地方在于：它除了业务代码之外，还**依赖两个外部服务**——一个是**对象存储**（用来存放老人照片、文件、附件这类东西），一个是**大模型 API**（用来做智能分析，比如体检报告的解读）。这两个服务都不是白用的，都要**申领额度**，而额度高低直接决定了这个项目能不能"低成本"跑起来。

- **0.1 需求**：在本地把类若依项目落地并跑通——后端能启动、前端能访问、两个外部依赖配置就位。
- **0.2 技术栈**：后端基于若依框架（Spring Boot + MyBatis-Plus + MySQL + Redis），前端是 Vue3（Vite 构建）。
- **0.3 本篇做到**：本地能访问。这里有两个**刻意不做**的东西——**不做小程序**（本项目不要求）、**不深度用大模型**（大模型只做到配置就位、能连通，真正的业务调用放到后续）。

| 项目       | 内容                  |
| -------- | ------------------- |
| **任务编号** | TASK-类若依-001        |
| **任务来源** | 个人项目（基于若依框架的养老管理系统） |
| **任务类型** | 低成本改造 / 环境搭建        |
| **实施角色** | 开发者 + 运维（个人）        |
| **环境要求** | 本地开发环境 + 虚拟机        |
| **优先级**  | 成本敏感（高）             |
| **状态**   | 已完成                 |

## 1. 背景：为什么不用阿里云 OSS 和百度千帆大模型

这个项目原本定下来的方案是：**阿里云 OSS** 做对象存储，**付费大模型**（比如百度千帆）做智能分析。这两个方案本身没问题，问题在于**它们都要花钱，而且免费额度不够高**。

我为什么不想用这个原定方案？主要有两个原因。

**第一是成本，这是最根本的一条。** 阿里云 OSS 收三块费用：**存储费**（按存了多少 GB 收）、**外网流出流量费**（按访问下载的流量收，这块是按量计费，最容易失控）、**请求费**（按读写次数收）。养老项目的图片和附件本来就多，被访问下载的次数也多，**流量费这一块会越用越贵**，对个人项目来说是个不小的负担。大模型这边更直接——按 token 计费，调用越多越贵，一次体检报告分析动辄几万 token，用多了成本根本压不住。这两块加起来，是这个实验里**最大的资金阻力**。

**第二是操作，纯属折腾。** 阿里云、百度千帆这些平台，控制台流程比较繁琐，要配额度、绑卡、实名，个人做实验实在不想把时间耗在这些"开户"的流程上。

**在这个背景下，我想到了 Cloudflare 的 R2。** 我之前在 Cloudflare 上用过 R2，知道它是一个**对象存储**，也有类似阿里云 OSS 的"**桶（Bucket）**"概念，存储功能很强、很稳定。但当时我**并不知道 R2 可以替代阿里云的存储方案**——是在**不断咨询 AI**、拿到充分的信息之后，我才判断出"R2 是 S3 兼容的，完全能顶替阿里云 OSS"，然后才回过头去把项目里的存储代码做了调整。这一步是"判断 → 验证 → 替换"的过程，不是一开始就想好的。

**大模型这边，我看中了商汤。** 商汤的大模型（日日新 SenseNova）**免费额度超级大**，官网上的模型基本都能免费使用。它有点像英伟达（NVIDIA）那种"白嫖"路线，只不过英伟达有**速度限制**，用起来有些折磨人；商汤这个体验还行，目前处于公测期，免费开放。

所以结论很清楚：**把"阿里云 OSS + 付费大模型"换成"Cloudflare R2 + 商汤"，成本就能压下来。** 具体能省多少，我列了下面的对比表，把两套方案的账算清楚。

### 对比表

**表一：对象存储 —— 阿里云 OSS vs Cloudflare R2**

| 项目                         | 阿里云 OSS        | Cloudflare R2                       |
| -------------------------- | -------------- | ----------------------------------- |
| 存储费                        | 约 ¥0.12 / GB·月 | $0.015 / GB·月（≈¥0.11），**前 10GB 免费** |
| 外网流出流量                     | 约 ¥0.50 / GB   | **¥0（无 egress 费）**                  |
| 请求费                        | 约 ¥0.01 / 万次   | 写 100 万次/月、读 1000 万次/月 免费           |
| 免费额度                       | 基本无            | 10GB 存储 + 100 万写 + 1000 万读          |
| **每月合计**（5GB 存储 + 20GB 流量） | **约 ¥11**      | **约 ¥0**                            |

**表二：大模型 —— 付费 API vs 商汤日日新**

| 项目       | 付费大模型（如千帆）              | 商汤日日新（SenseNova）                                    |
| -------- | ----------------------- | --------------------------------------------------- |
| 计费方式     | 约 ¥0.008~0.02 / 千 token | **公测期免费（¥0/月）**                                     |
| 可用模型     | 按模型单独计费                 | SenseNova 6.8 Flash Lite、U1 Fast 等（最多 20 个 API Key） |
| **每月合计** | 约 ¥8 ~ 20               | **¥0**                                              |

**结论**：把两处一换，**每月从约 ¥19 ~ 31 降到 ¥0，一年省 ¥230 ~ 370**。但比"省了多少钱"更重要的是——只要在免费额度内，**成本就是 0，不用精打细算调用量**。对个人项目来说，这是一种"**可持续的免费**"，而不是那种让你总觉得"超了要扣钱"的试用。

> 注：阿里云 OSS 为约值（地区不同有差），以实际控制台为准；商汤"免费"为公测期，后续可能收费。

## 2. 项目架构

本项目前后端分离，涉及 **4 个位置**：**本机**（跑前后端）、**node2**（数据，**本篇就用**）、**node1/node3**（第 2 篇部署）。

| 位置        | 角色    | 部署内容                                | 本篇用不用            |
| --------- | ----- | ----------------------------------- | ---------------- |
| **本机**    | 开发/运行 | 前端 Vue3（8001）+ 后端 Spring Boot（9000） | ✅ 用              |
| **node2** | 数据层   | **MySQL + Redis**                   | ✅ **本篇就用**（后端连它） |
| **node1** | 接入层   | Nginx（前端 `dist` + 反向代理）             | ⏳ 第 2 篇          |
| **node3** | 应用层   | Tomcat + JDK 11（后端部署）               | ⏳ 第 2 篇          |

### 2.1 前端（本机，Vue3）

- 技术栈：Vue3 + Vite + Element Plus + Axios + Vue Router。
- 运行：`npm run dev`，端口 **8001**。
- 连后端：Vite 代理把 `/dev-api/`、`/prod-api/` 转发到后端 9000。

### 2.2 后端（本机，Spring Boot 多模块）

- 技术栈：Spring Boot 2.5.15 + Java 11 + MyBatis-Plus + MySQL + Redis。
- 多模块：`zzyl-admin`（启动，`com.zzyl.RuoYiApplication`，端口 9000）、`zzyl-framework`、`zzyl-system`、`zzyl-nursing-platform`、`zzyl-common`、`zzyl-oss`（**本篇换 R2**）、`zzyl-quartz`、`zzyl-generator`。
- 本篇状态：后端在**本机跑**（9000），连 **node2** 上的 MySQL / Redis。

### 2.3 数据服务（**node2：MySQL + Redis**，本篇就用）

- **MySQL 8**：存业务数据，库 `ry-zzyl`，地址 `192.168.88.171:3306`。
- **Redis**：缓存 / 验证码，地址 `192.168.88.171:6379`（密码 `123456`）。
- 本项目之所以**不是纯本机**：后端虽然跑在本机，但**数据库和缓存在 node2 上**，本机通过 IP 连过去。

### 2.4 本篇线路图（本机 + node2）

```
浏览器
  → 前端 Vite（本机 8001）
  → 代理 /dev-api
  → 后端 Spring Boot（本机 9000）
      ├→ node2：MySQL（192.168.88.171:3306，库 ry-zzyl）
      ├→ node2：Redis（192.168.88.171:6379）
      ├→ Cloudflare R2（S3 接口）
      └→ 商汤大模型（SenseNova API）
```

### 2.5 第 2 篇完整拓扑（本机不再参与，全上服务器）

```
用户 → node1（Nginx/DNS）→ 反代 → node3（Tomcat 跑后端）→ node2（MySQL/Redis）
```

| 节点    | 部署                      | 阶段                                  |
| ----- | ----------------------- | ----------------------------------- |
| node1 | Nginx（前端 dist + 反代）、DNS | 第 2 篇                               |
| node2 | MySQL、Redis、NTP、日志服务    | **本篇已用 MySQL/Redis**，第 2 篇再加 NTP/日志 |
| node3 | Tomcat + JDK 11（后端）     | 第 2 篇                               |

---

## 3. 实施过程

> **说明**：这里针对本实验做详细安排，按"几个关键步骤 + 每步遇到的问题"来写。这个阶段的**主要任务是后端**，前端任务量不大。

### 3.1 JDK 安装 + 环境变量

后端是 Java 11 的项目，**JDK 必须用 11 版本**，版本不对后面一堆依赖对不上、项目跑不顺畅。装好之后要配 **`JAVA_HOME`** 和 **`PATH`**，让 Windows 全局都能加载到 Java。

![JDK 11 安装界面](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/750892ba-23e8-40b2-b97b-5fe03e73e391.png)

这里我踩了个坑：配环境变量时，**`bin` 最多只能放在 PATH 的第二层**。我一开始把 `bin` 塞得很深，双击配置后 **PATH 没有正常展开**——本质是系统没能正确读取、加载这个程序。后来我在命令行直接输入 `java`，发现它能正常输出，说明环境其实已经生效，这一步就算搞定了。

![双击后 PATH 没有正常展开](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/photo_2026-11-05_17-24-51.jpg)

![PATH 环境变量配置](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/db85feb4-dba8-48a4-85a2-f4d7a9f7a713.png)

> 提醒：环境变量改完，**每一项都要点"确定"**，漏一个就会配置失效。

### 3.2 IDEA 安装 + 挂载后端项目

安装完成后的界面如下。

![IDEA 安装完成界面](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/e9d72301-f7ff-4a4e-bf41-bdf68d07bd8d.png)

这一步不复杂。装好 **IDEA 2026 专业版**，把后端项目**解压到没有中文、没有空格的目录**（建议在 IDEA 安装目录下建一个 `workspace` 目录，把项目解压进去，保持只有一层 `zzyl` 目录）。

![后端项目解压到无中文目录](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/56174e6c-7d91-4d29-8923-8f12c751dd25.png)

然后用 IDEA 打开。

![用 IDEA 打开后端项目](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/f8f3ba21-6400-47a9-8a6f-dcf1d8ed573e.png)

### 3.3 Maven 配置（仓库 / 镜像 / 编码 / JDK）

项目是 Maven 构建的，所以先装 Maven：

1. **下载解压**：把 Maven 解压到**没有中文和空格**的目录；
2. **配环境变量**：`MAVEN_HOME` 指向 Maven 目录，`PATH` 里加上 `%MAVEN_HOME%\bin`，命令行 `mvn -v` 能出版本号就装好了；
3. **改本地仓库**：默认本地仓库在 C 盘用户目录，占空间又不好管。在 `settings.xml` 里把 `localRepository` 改到别的盘；
4. **配阿里云镜像**：默认中央仓库在国外，下载慢、容易超时。加阿里云镜像：

```xml
<mirrors>
    <mirror>
        <id>aliyunmaven</id>
        <mirrorOf>*</mirrorOf>
        <name>阿里云公共仓库</name>
        <url>https://maven.aliyun.com/repository/public</url>
    </mirror>
</mirrors>
```

5. **IDEA 里再调三处**：① Maven 路径和 `settings.xml` 指向刚配的；② 编码改成 **UTF-8**；③ 项目 JDK 调成 **11**；最后**刷新 Maven**。刷新后**没有红色波浪线报错**，说明依赖都下来了。
   
![Maven 配置完成、依赖已下载](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/65868821-3090-4633-99ef-a867d3d62980.png)

![Maven 本地仓库与镜像设置](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/7e6ec8cb-5de2-4a3a-8fe5-3c6dd19a8f0c.png)

![settings.xml 阿里云镜像配置](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/601eefbe-bf87-42d0-a2c2-904c0f3a049a.png)

![IDEA 中项目 JDK 设为 11](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/a572a525-9008-4b06-8bf9-3bd3b86b5708.png)

### 3.4 MySQL8：安装 / 初始密码 / 远程连接 / 导入数据 / 改配置

**重点：MySQL 装在 node2 上，项目在本机，要远程连**，所以不止"装完"，中间有三关——授权、防火墙、项目配置。

**① 在 node2 装 MySQL8**

```bash
dnf install -y https://dev.mysql.com/get/mysql80-community-release-el9-1.noarch.rpm
dnf repolist enabled | grep mysql
dnf install -y mysql-community-server --nogpgcheck
systemctl start mysqld && systemctl enable mysqld
```

**② 初始密码 + 改密码**

初始 root 密码是随机的，去日志里抢救：

```bash
grep password /var/log/mysqld.log
mysql_secure_installation
```

![MySQL 初始 root 密码](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/35dca768-f33e-4933-baa8-072581926914.png)

![MySQL 修改 root 密码](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/1c18088d-debc-4ff3-995e-113d994e4aad.png)

**③ 远程授权（关键，不授本机连不上）**

默认 root 只能本机连，要授权远程：

```sql
CREATE USER 'root'@'%' IDENTIFIED BY 'Aa123456.';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
```

> 坑：只建了 `'root'@'localhost'`，本机远程连就报 **Access denied**，必须 `'root'@'%'`。

![MySQL 授权 root 远程访问](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/eb2fc2cb-da1c-48ec-99ac-261cb817b8c8.png)

**④ 防火墙开 3306**

```bash
firewall-cmd --zone=public --add-port=3306/tcp --permanent
firewall-cmd --reload
firewall-cmd --list-all
```

![防火墙开放 3306 端口](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/0b88abe7-7c2c-400a-94aa-9fb0832db855.png)

**⑤ 在 IDEA 里配置数据库连接**

在 IDEA 的 **Database** 工具里新建 MySQL 连接，地址填 node2 的 `192.168.88.171:3306`、库名 `ry-zzyl`、账号 `root`、密码 `Aa123456.`，点 **Test Connection** 能连上即可。

![IDEA Database 新建连接](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/a897d51c-23d3-4cdd-8060-7721ed756b8c.png)

![数据库连接测试成功](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/678b391c-4519-4709-93e0-a3b3f57d1969.png)

![node2 MySQL 连接成功](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/5b58c2f4-7495-4e37-bc64-697ae2f9358e.png)

测试没问题，可以正常连接到我自己的数据库。

然后运行脚本，导入数据库。

![运行脚本导入数据库](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/ff4c3c46-99b9-4ca0-a382-0e1db3874bec.png)

然后查看数据库，发现有 40 张表，说明数据库导入成功。

![导入后共 40 张表](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/5baa02a8-ff8b-4eb6-9662-c8f75d0ac06e.png)

**⑥ 改项目配置（让本机连 node2）**

改 `application-druid.yml` 的数据源，IP 换成 **node2 地址**（不是 localhost）：

```yaml
url: jdbc:mysql://192.168.88.171:3306/ry-zzyl?...
username: root
password: Aa123456.
```

> 坑：地址还写 `localhost`，连的就是本机，不是 node2，启动直接连接失败。

![修改数据源指向 node2](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/479a88cc-7b13-44ae-8e4e-3d717ad6f647.png)

原来的数据库地址也要一并改成 node2 的地址。

### 3.5 Redis：安装 / 配置 / 启动 / 测试 / 改项目地址

Redis 同理，**装在 node2，本机远程连**，麻烦在 **改 node2 上的 `redis.conf`**。

**① 在 node2 装 Redis**

```bash
dnf install redis -y
```

**② 改 node2 上的 redis.conf（最容易漏）**

默认 Redis 只允许本机连，要改两处：

```bash
vim /etc/redis/redis.conf
```

- `bind` 改成 **`bind * -::*`**（允许任意地址连）；
- 打开 `requirepass` 设成 **`requirepass 123456`**（项目配置有密码，必须设）。

![修改 redis.conf 的 bind 与密码](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/3a70b790-7972-46ca-a261-1a2e0ef9bc0d.png)

**③ 启动 + 测试**

```bash
systemctl start redis && systemctl enable redis
redis-cli -a 123456        # 或进客户端后 auth 123456
```

![Redis 启动与测试](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/5d675829-e388-47fa-a567-6b5cae2597e0.png)

**④ 防火墙开 6379**

```bash
firewall-cmd --add-port=6379/tcp --add-port=6379/udp --permanent
firewall-cmd --reload
```

![防火墙开放 6379 端口](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/4dc94a62-515b-48f5-a67a-f8727aa2f6c2.png)

**⑤ 改项目配置（让本机连 node2 的 Redis）**

改 `application.yml` 的 redis 段：

```yaml
spring:
  redis:
    host: 192.168.88.171
    port: 6379
    password: 123456
```

> 常见坑：`bind` 没改（连超时）、`requirepass` 没设（认证失败）、6379 没放行（超时）、地址还是 `localhost`（连错机器）。

![项目 Redis 连接配置](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/d9888e52-267d-47d7-82f3-35090076469c.png)

### 3.6 接入 Cloudflare R2（替代阿里云 OSS）

原方案是阿里云 OSS，我换成 **Cloudflare R2**（S3 兼容），省钱关键就在这。

**① 在 Cloudflare 注册，进 R2 建 bucket**；

![Cloudflare 创建 R2 桶](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/b23c8f3d-f199-4215-9098-0f9b59b6527f.png)

![R2 桶创建完成](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/3e74026a-4ca2-4f9a-a424-22e942168e39.png)

**② 拿 endpoint 和 accessKey/secretKey**；

![R2 endpoint 与访问密钥](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/29e0d03c-3be9-4359-a469-ddda149c660b.png)

创建完成后会生成一个密钥，里面就有我们要的信息。

![R2 访问密钥生成](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/3a1f38ed-8f69-427a-aaa9-21ade73aace6.png)

![R2 secretKey 信息](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/dcb4627c-2642-46a9-871c-baec100b38cc.png)

**③ 项目里把阿里云 OSS SDK 换成 S3Client**——因为 R2 是 **S3 兼容**的，用 AWS 的 `S3Client` 就能直连，阿里云 SDK 连不了 R2。这是关键决策，也导致了后面 AWS SDK 版本冲突的坑。

配置：

```yaml
r2:
  endpoint: https://<账号>.r2.cloudflarestorage.com
  accessKey: <R2 accessKey>
  secretKey: <R2 secretKey>
  bucket: <bucket 名>
```

### 3.7 接入商汤大模型

注册**商汤日日新 SenseNova**，拿 **API Key**，配进项目。**这是必配项**——不配，项目启动/调用会报错。

```yaml
model:
  apiKey: <商汤 API Key>
  model: SenseNova-6.8-Flash-Lite
```

> 本篇只做到"配置就位、能连通"，真正的业务调用（体检报告分析）放后面，不做深度使用。

![商汤 SenseNova API Key 配置](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/d3860ecc-3b8b-4907-a845-6b01790837b4.png)

### 3.8 前端：Node + VSCode + `npm install` + `npm run dev`

前端在**本机 Windows** 跑。

**① 装 Node.js**：双击 msi 安装（双击没反应就在该目录开 CMD，执行 `msiexec /i node-v18.20.3-x64.msi`）；
**② 装 VSCode**：双击安装，可加中文插件；
**③ 挂载前端项目**：解压到无中文无空格目录，用 VSCode 打开；
**④ 装依赖 + 改配置 + 启动**：

```bash
npm install --registry=https://registry.npmmirror.com
# 改 vite.config.js：把 mock 地址改为后端服务地址（9000）
npm run dev
```

访问 `http://localhost:8001/`。前端通过 **Vite 代理**把 `/dev-api/` 转发到后端 9000。

### 3.9 启动后端，验证 R2 / 商汤配置不报错

回到 IDEA，跑启动类 `com.zzyl.RuoYiApplication`，看控制台：

- 没有 `NoSuchBeanDefinitionException`（R2 的 S3Client 配好了）；
- 没有连 `192.168.88.171:3306` / `:6379` 的超时报错（MySQL/Redis 通了）；
- 启动完成，`/captchaImage`、`/login` 接口能访问。

到这里，**本机跑通 + R2/商汤配置就位**，本篇目标达成。

---

## 4. 测试（验收清单）

这一节是**验收**：对照 0.3 说的"本篇做到本机能访问"，逐项确认。不是走个过场，每一项都要能跑出结果。

### 4.1 后端启动成功、接口可访问

启动 `com.zzyl.RuoYiApplication`，日志里出现 `Started RuoYiApplication`、**没有异常栈**，就说明后端起来了（端口 9000）。

然后验证接口：浏览器/Postman 访问 `http://localhost:9000/captchaImage`，能返回验证码的 JSON（`{"code":200,"img":...}`）就说明接口通。再测 `/login`，用 `admin` 账号能登录、拿到 token，就说明**后端 + MySQL 都通了**（登录要查用户表）。

### 4.2 前端页面正常

`npm run dev` 起前端（8001），打开 `http://localhost:8001/`：

- 能看到**登录页**（不是白屏、不是报错）；
- 登录后能进**后台管理首页**，左侧菜单、列表页能正常渲染；
- 点开"预约信息"这类列表，能**请求到后端数据**（说明代理 9000 通了）。

![前端后台管理首页](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/11572c70-e3f9-4b6b-83b8-11414d136e70.png)

![前端列表页数据正常](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/025e1a26-0094-4cf5-8254-0b828f2ed8ff.png)

### 4.3 R2 上传 / 下载成功（替代 OSS 生效）

这是本次改造的**核心验收点**。在项目里触发一次文件上传（比如头像/附件），确认：

- 文件真的进了 **R2 的 bucket**（去 Cloudflare 控制台能看到文件）；
- 下载/预览能正常取回（说明 `S3Client` 的 `putObject`/`getObject` 都通了）；
- **不报** `NoSuchBeanDefinitionException`（OSS Bean 问题已解决）。
  
![R2 上传下载验证成功](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/fa31d2ab-7f9c-41ac-ac77-940b58a2e00c.png)

### 4.4 商汤 API 配置就位

启动**不报** API 相关异常、配置能读到 Key，就算"就位"。这里**如实说明**：本篇只验证**配置连通**，**没做深度业务调用**（体检报告分析没接）。不要把它写成"已实现智能分析"——那是后面的事。从这张图可以看到，商汤的免费额度非常可观。

![商汤免费额度](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/80a8022d-a6d2-4e6d-9cd9-3ac17da7c651.png)

![商汤可用模型列表](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/52586217-65c3-4c7a-a42c-6bbf7507db40.png)

而且商汤提供的模型也比较丰富，其中体验最好的是他们自家的 6.8 模型。

### 4.5 成本核算（省了多少）

按第 1.5 节的对比表，**本项目在免费额度内**：

| 项       | 原方案              | 本方案        |
| ------- | ---------------- | ---------- |
| 存储（R2）  | 阿里云 OSS ≈ ¥11/月  | **¥0**     |
| 大模型（商汤） | 付费 API ≈ ¥8~20/月 | **¥0**（公测） |
| **合计**  | **≈ ¥19~31/月**   | **¥0**     |

> 验收结论：**本地跑通 + 存储/大模型两块成本压到 ¥0，改造目标达成。**

---

## 5. 问题与解决

### 5.1 启动报 `NoSuchBeanDefinitionException`（OSS Bean）→ 改 `S3Client`

**现象**：启动后端，直接报错退出：

```
org.springframework.beans.factory.NoSuchBeanDefinitionException:
No qualifying bean of type 'com.aliyun.oss.OSS' available ...
```

**原因**：这个项目底层**写死了用阿里云 OSS**——代码里注入的是阿里云的 `OSS`/`OSSClient` Bean，我把它换成 **Cloudflare R2** 后，R2 根本没有阿里云 OSS 的 Bean，Spring 注入不到，启动就报 `NoSuchBeanDefinitionException`。

**解决**：R2 是 **S3 兼容**的（走**亚马逊 S3 协议**），所以不能用阿里云 OSS SDK，得改用 **AWS 的 `S3Client`**。原代码里 OSS 的注入、上传、下载、删除全都要改：

| 原（阿里云 OSS）                    | 改（S3 / R2）                   |
| ----------------------------- | ---------------------------- |
| `OSS ossClient` 注入            | `S3Client s3Client`          |
| `ossClient.putObject(...)`    | `s3Client.putObject(...)`    |
| `ossClient.getObject(...)`    | `s3Client.getObject(...)`    |
| `ossClient.deleteObject(...)` | `s3Client.deleteObject(...)` |

这一步改造量不小（项目底层写死了 OSS），我**是借助 Codex 把原来的代码改过来的**，改完才能用 R2。**这是本篇成本改造最关键的一处**：不是改个配置就完事，是要把存储层的 SDK 换掉。

### 5.2 登录不通（proxy `8080 → 9000`）

**现象**：前端能打开，但一点登录就失败——请求 404 / 连不上 / 跨域，登录不进去。

![登录请求失败（代理端口问题）](https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev/blog_images/%E4%B8%AD%E5%B7%9E%E5%85%BB%E8%80%81%E5%8D%95%E4%BD%93%E9%A1%B9%E7%9B%AE%E7%AC%AC%E4%B8%80%E6%AC%A1%E7%AC%94%E8%AE%B0/pictures/30a0fc1f-f951-4734-8c94-a3da6e242a14.png)

**原因**：前端 **Vite 代理**配的是 **8080**，但**后端实际跑在 9000**。请求被代理发到 8080，那里根本没有后端，自然打不通，其实我早把这里改成了 9000，但改完没保存，所以一直卡在登录验证这一步。

**解决**：知道问题之后，我就把改动的文件保存了一下，此时刷新网页发现可以正常验证了。改 `vite.config.js` 的 proxy：

```js
proxy: {
  '/dev-api': {
    target: 'http://localhost:9000',   // 从 8080 改成 9000
    changeOrigin: true,
    rewrite: (p) => p.replace(/^\/dev-api/, '')
  }
}
```

改完**重启前端**，登录就通了。

### 5.3 Maven 依赖下载报错

**现象**：IDEA 刷新 Maven / `mvn` 打包时，依赖下载失败，报超时、`Could not resolve dependencies`、`Could not transfer artifact` 之类。

**原因**：Maven 默认走**中央仓库（国外）**，网络慢、经常超时，依赖下载不下来。

**解决**：

1. **配阿里云镜像**（改 `settings.xml`）：

```xml
<mirrors>
    <mirror>
        <id>aliyunmaven</id>
        <mirrorOf>*</mirrorOf>
        <name>阿里云公共仓库</name>
        <url>https://maven.aliyun.com/repository/public</url>
    </mirror>
</mirrors>
```

2. 如果之前下了一半留了 `.lastUpdated` 残留，**删掉本地仓库里对应的 `.lastUpdated` 文件**再重新刷新，否则 Maven 会一直读缓存里的"失败"记录。

3. 前端 `npm` 同理，用国内源：

```bash
npm install --registry=https://registry.npmmirror.com
```

### 5.4 AWS SDK 版本冲突 / `readAllBytes` IOException

**现象**：改 S3Client 之后，编译/启动又冒出新问题：

- **版本冲突**：`NoSuchMethodError` / `ClassNotFoundException`，或者同一个类被两个版本加载；
- **`readAllBytes` 报 IOException**：读取文件（流）时抛 `java.io.IOException`。

**原因**：

- **版本冲突**：项目里原本就有旧的 AWS SDK 依赖（或和 Spring 框架里的依赖打架），我又引入了 `S3Client` 用的新版本，同一套 SDK 出现**两个版本**，运行时加载错版本就报 `NoSuchMethodError`。
- **`readAllBytes`**：读取方式不兼容——流已经被读过 / 没按正确方式读，或者用了 Java 版本不支持的写法，就抛 `IOException`。

**解决**：

1. **统一 AWS SDK 版本**：在父工程 `pom.xml` 的 `dependencyManagement` 里**锁死一个版本**（比如统一用 `software.amazon.awssdk` 的某一版），把冲突的旧版本依赖排除掉（`<exclusions>`），让全项目只用同一个版本。

2. **改 `readAllBytes` 的读法**：不用有问题的 `readAllBytes`，改成兼容写法——用 `Files.readAllBytes(Paths.get(path))`，或用 `BufferedReader` 逐行/逐块读，确保流按正确方式读、读前流的指针位置正确，`IOException` 就消失了。

> 这两个坑本质都是"换 SDK 带来的连锁反应"：**存储从阿里云 OSS 换到 S3(R2)，不是只改调用方法，还要处理依赖版本和文件读写方式的兼容问题**。

---

### 5.5 小结：这四节的主线

| 问题                                  | 根因                        | 解决                                            |
| ----------------------------------- | ------------------------- | --------------------------------------------- |
| 5.1 `NoSuchBeanDefinitionException` | 代码写死阿里云 OSS Bean，R2 没有    | **借 Codex 把 OSS SDK 换成 S3Client**（R2 走 S3 协议） |
| 5.2 登录不通                            | 前端代理 8080，后端在 9000        | 代理指向 **9000**                                 |
| 5.3 依赖下载报错                          | 默认中央仓库慢/超时                | **阿里云镜像** + 清 `.lastUpdated`                  |
| 5.4 SDK 冲突 / IOException            | 换 S3Client 引入版本冲突 + 读法不兼容 | **锁 SDK 版本** + **改 readAllBytes 读法**          |

这四节串起来就是一句话：**把存储从"阿里云 OSS"换成"R2（S3 协议）"不是改配置，是把存储层 SDK 换掉**——改代码（5.1）→ 顺带出依赖版本问题（5.4）→ 再撞上前端代理和 Maven 网络问题（5.2/5.3）。

## 6. 总结：本地跑通了，下一步上生产

本篇做完了两件事：**一是把类若依项目在本机跑通**（后端 9000、前端 8001、MySQL/Redis 连 node2），**二是把最烧钱的两块成本压到了 ¥0**——存储从阿里云 OSS 换成 **Cloudflare R2**，大模型从付费 API 换成 **商汤日日新**，都在免费额度内，一分钱不花。

踩的坑不少，但都解决了：**OSS Bean 注入失败**（改 S3Client）、**登录代理 8080→9000**、**Maven 依赖下载报错**（配阿里云镜像）、**AWS SDK 版本冲突 + readAllBytes IOException**。这些坑我发现一条规律——**它们几乎都是"把存储从阿里云 OSS 换成 R2（S3 协议）"带出来的连锁反应**：不是改个配置就完事，是真要动 SDK、动依赖、动文件读写。好在有 Codex 帮忙，能比较高效地改掉这些原始代码。说到底，这个实验本身并不复杂，我只是把原来要用阿里云的存储方案，换成了免费额度巨大的 Cloudflare（CF），同时用了提供免费方案的 AI 模型商汤——这大概是我这次实验比较亮眼的地方。其他的我也还在慢慢摸索。感兴趣的话，我已经把这套用 AI 改好的代码打包成 JAR 推到了 GitHub，大家可以下载到本地使用。

https://github.com/dsduyopg/itcast_data_linux/releases/download/R2%E7%9A%84%E6%94%B9%E9%80%A0%E8%8B%A5%E4%BE%9D%E9%A1%B9%E7%9B%AE/zzyl-admin.jar
