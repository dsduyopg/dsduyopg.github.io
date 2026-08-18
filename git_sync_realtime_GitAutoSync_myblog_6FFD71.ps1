# ============================================================
# Git 实时自动同步脚本 - 自动生成
# 路径: D:\my-blog  ->  ssh://git@ssh.github.com:443/dsduyopg/dsduyopg.github.io.git (origin/main)
# ============================================================

$ErrorActionPreference = 'Continue'

$RepoPath      = 'D:\my-blog'
$Branch        = 'main'
$Remote        = 'origin'
$LogFile       = Join-Path $RepoPath 'git_sync.log'
$DebounceMs    = 3000
$RetryTimes    = 3
$RetryWaitSec  = 5

if (-not (Test-Path $RepoPath)) {
    Write-Host "错误：目录不存在 $RepoPath"
    exit 1
}
Set-Location $RepoPath

function Write-Log {
    param([string]$Msg)
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Msg
    $line | Out-File -FilePath $LogFile -Append -Encoding utf8
    Write-Host $line
}

Write-Log '============================================'
Write-Log 'Git 实时同步脚本启动'

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Log '错误：未找到 git 命令，请先安装 Git'
    exit 1
}
if (-not (Test-Path (Join-Path $RepoPath '.git'))) {
    Write-Log '错误：该目录不是 git 仓库'
    exit 1
}
$hasRemote = (git -C $RepoPath remote) -match "^$Remote$"
if (-not $hasRemote) {
    Write-Log "错误：未配置远程仓库 $Remote`n请先执行: git remote add $Remote <仓库地址>"
    exit 1
}

function Should-Ignore {
    param([string]$FullPath)
    if ($FullPath -like "$RepoPath\.git*") { return $true }
    if ($FullPath -like "$RepoPath\git_sync*") { return $true }
    return $false
}

function Sync-Now {
    try {
        $addOut = git -C $RepoPath add -A 2>&1
        if ($LASTEXITCODE -ne 0) { Write-Log "git add 失败：$addOut"; return }
        $status = git -C $RepoPath status --porcelain
        if ([string]::IsNullOrWhiteSpace($status)) { Write-Log '无实际文件变动，跳过提交'; return }
        $msg = "auto-sync: {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        $commitOut = git -C $RepoPath commit -m $msg 2>&1
        if ($LASTEXITCODE -ne 0) { Write-Log "git commit 失败：$commitOut"; return }
        Write-Log "已提交：$msg"
        for ($i = 1; $i -le $RetryTimes; $i++) {
            $pushOut = git -C $RepoPath push $Remote $Branch 2>&1
            if ($LASTEXITCODE -eq 0) { Write-Log "推送成功 -> $Remote/$Branch"; return }
            Write-Log "推送失败(第 $i/$RetryTimes 次)：$pushOut"
            Start-Sleep -Seconds $RetryWaitSec
        }
        Write-Log '推送失败，超过重试次数，将在下次变化时重试'
    } catch {
        Write-Log "同步出错：$_"
    }
}

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path                  = $RepoPath
$watcher.IncludeSubdirectories = $true
$watcher.NotifyFilter          = [System.IO.NotifyFilters]::LastWrite -bor `
                                 [System.IO.NotifyFilters]::FileName -bor `
                                 [System.IO.NotifyFilters]::DirectoryName -bor `
                                 [System.IO.NotifyFilters]::Size
$watcher.EnableRaisingEvents   = $true

$null = Register-ObjectEvent $watcher Created -SourceIdentifier Sync.Created
$null = Register-ObjectEvent $watcher Changed -SourceIdentifier Sync.Changed
$null = Register-ObjectEvent $watcher Renamed -SourceIdentifier Sync.Renamed
$null = Register-ObjectEvent $watcher Deleted -SourceIdentifier Sync.Deleted

Write-Log '启动时执行一次完整同步...'
Sync-Now
Write-Log "开始实时监听目录：$RepoPath（按 Ctrl+C 停止）"

while ($true) {
    $e = Wait-Event -Timeout 1
    if ($null -eq $e) { continue }
    $evArgs = $e.SourceEventArgs
    if ($null -ne $evArgs -and (Should-Ignore $evArgs.FullPath)) {
        Remove-Event -EventIdentifier $e.EventIdentifier
        continue
    }
    Remove-Event -EventIdentifier $e.EventIdentifier
    Start-Sleep -Milliseconds $DebounceMs
    while ($null -ne ($tmp = Wait-Event -Timeout 0)) {
        Remove-Event -EventIdentifier $tmp.EventIdentifier
    }
    Write-Log '检测到文件变化，开始同步...'
    Sync-Now
}