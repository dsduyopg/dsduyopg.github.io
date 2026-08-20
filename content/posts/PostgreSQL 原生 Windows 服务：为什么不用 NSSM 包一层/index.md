---
comments: true
title: "PostgreSQL 原生 Windows 服务：为什么不用 NSSM 包一层？"
date: 2026-08-20
draft: false
ShowToc: false
tags: ["Windows", "PostgreSQL", "NSSM"]
---
{{< toc >}}

>

**摘要**：很多人会用 NSSM 把程序包装成 Windows 服务，但 PostgreSQL 天生就是原生 Windows 服务，直接用 `Set-Service` / `Start-Service` 管理即可，完全不需要也不应该套一层 NSSM。本文讲清楚两者的定位区别、为什么给 PostgreSQL 套 NSSM 是负优化，以及正确的管理姿势。


**核心结论（TL;DR）**：NSSM 是给"不能自己当服务"的普通程序（脚本、exe）用的；PostgreSQL 安装时就注册成了原生服务，能优雅关库、能被 SCM 直接管理。用 NSSM 包数据库反而会多一层中转、增加非正常退出导致数据恢复的风险。正确做法就是一行 `Set-Service` + `Start-Service`。

## 1. 引子：我遇到的问题

我在博客里写过一篇《Windows 上让 Git 自动同步：NSSM 服务 + 实时监听实战》，里面用 NSSM 把"监听推送 + 定时拉取"的脚本注册成了 Windows 服务，实现了开机自启、崩溃自愈。

后来装 PostgreSQL 时，习惯性地想到了 NSSM：是不是也要把它包成服务？

答案是不用。**PostgreSQL 和我的 Git 同步脚本完全是两种东西**，这篇就把区别讲清楚。

## 2. 什么是 Windows 原生服务

Windows 服务（Service）不是"一个常驻程序"这么简单，它有一套完整的协议：

- 由**服务控制管理器（SCM）**统一管理，开机按依赖关系启动、关机时通知停止
- 向 SCM 汇报状态、进程 PID
- 响应 START / STOP / 查询等控制指令
- 服务失败时可以配置重启策略

判断一个程序是不是"原生服务"，就看它是否**自己实现了这套协议**、是否注册进了 SCM。

## 3. PostgreSQL 安装时就已经是原生服务

PostgreSQL 的 Windows 安装包在安装过程中，就会通过它自带的机制把服务注册好，服务名通常是：

```
postgresql-x64-17
```

注册完之后，Windows 的"服务"管理器里就能看到它，`sc query postgresql-x64-17`、`Get-Service` 都能直接查询和管理。也就是说，**从装完那一刻起，它就已经是标准的原生服务了**，什么都不用再做。

## 4. NSSM 是给谁用的

NSSM（Non-Sucking Service Manager）的定位是**包装器**：把一个本身不具备服务能力的普通程序包装成服务。

典型场景：

- Python / Node 脚本（比如我的 Git 自动同步脚本）
- 没有服务参数的自写 exe
- bat / cmd 批处理

这些程序没有注册机制、不懂 SCM 协议，NSSM 帮它们补上这一层：开机自启、崩溃重启、日志输出、退出码处理。

## 5. 对比：原生服务 vs NSSM 包一层

| 对比项 | 原生服务（PostgreSQL 现状） | NSSM 包一层 |
| --- | --- | --- |
| 关闭流程 | SCM 直接通知 postmaster 优雅关库：停连接、刷脏页、安全落盘 | NSSM 中转，容易退化成"直接杀进程" |
| 状态反馈 | 服务状态、PID 一目了然 | 多一层包装，排查问题多一步 |
| 可靠性 | PostgreSQL 官方自带的注册机制，最稳 | 数据库这种关键服务没必要冒这个险 |
| 管理方式 | `sc` / 服务管理器 / `pg_ctl` 都能直接管 | 被 NSSM 接管，先要绕过它 |
| 开机自启 | 安装时默认就是 Automatic | 由 NSSM 自己实现，绕了一圈 |

## 6. 用 NSSM 包 PostgreSQL 的风险

最大的风险在**关闭流程**。

PostgreSQL 原生服务在收到 SCM 的停止指令时，会走优雅关库流程：通知 postmaster，停止接收新连接，等待事务完成，刷脏页，然后安全落盘退出。

而 NSSM 包装的进程本质上是"没有优雅停机协议"的，它停止服务的方式是发送关闭信号或者杀掉进程树。如果数据库在这种状态下被强杀，下次启动就要走 **recovery（恢复）流程**，数据量大了启动会明显变慢，最坏情况下还可能有数据丢失风险。

所以：**能原生当服务的，就别套 NSSM**。

## 7. 正确的管理姿势

PostgreSQL 已经原生注册好了，直接两行命令：

```powershell
# 设置开机自启（安装时默认就是 Automatic，没改过可以不写）
Set-Service -Name postgresql-x64-17 -StartupType Automatic

# 立即启动
Start-Service postgresql-x64-17
```

日常管理：

```powershell
# 停止
Stop-Service postgresql-x64-17

# 查看状态
Get-Service postgresql-x64-17

# 命令行查询
sc query postgresql-x64-17
```

以后写进博客、记笔记，都是这一套，不用 NSSM。

## 8. 什么时候才该用 NSSM

回到开头那句话：**NSSM 用来救"当不了服务的程序"**。

判断标准很简单：

- 程序自己能不能注册成服务、能不能响应 SCM？能 → 原生管理
- 程序只是个普通脚本 / exe，什么服务能力都没有？→ 才考虑 NSSM

我的 Git 自动同步脚本属于后者，所以用了 NSSM；PostgreSQL 属于前者，所以直接原生管理。

## 9. 总结

| 结论 | 说明 |
| --- | --- |
| PostgreSQL 是原生 Windows 服务 | 安装时已注册好，直接 `Set-Service` / `Start-Service` 管理 |
| 不需要 NSSM | 套一层反而多中转，增加非正常关库风险 |
| NSSM 只用于普通程序 | 脚本、无服务能力的 exe 才需要包装 |
| 正确做法 | `Set-Service -StartupType Automatic` + `Start-Service`，两行搞定 |
