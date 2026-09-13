@echo off
rem ============================================================
rem  重启 Git 自动同步服务（让修改后的 DebounceMs 生效）
rem  服务名：GitAutoSync_myblog_6FFD71
rem ============================================================
chcp 65001 >nul

rem ---- 需要管理员权限，没有就自动提权 ----
net session >nul 2>&1
if errorlevel 1 (
  echo 正在请求管理员权限…
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

set "NSSM=D:\AnLink\Git自动同步工具包\04-一键部署\nssm_bin\nssm.exe"
set "SVC=GitAutoSync_myblog_6FFD71"

if not exist "%NSSM%" (
  echo [ERROR] 找不到 nssm.exe：%NSSM%
  echo         请修改本文件里的 NSSM 路径。
  pause
  exit /b 1
)

echo 重启服务 %SVC% …
"%NSSM%" restart %SVC%
echo.
echo 当前状态：
"%NSSM%" status %SVC%
echo.
echo 完成。验证方法：随便改一下 D:\my-blog 里的一个文件，
echo 然后等约 30 秒再看 git_sync.log —— 应该出现「检测到文件变化」。
pause
