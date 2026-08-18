@echo off
chcp 65001 >nul
set "NSSM=D:\AnLink\Git自动同步工具包\04-一键部署\nssm_bin\nssm.exe"
"%NSSM%" stop GitAutoSync_myblog_6FFD71 >nul 2>&1
"%NSSM%" remove GitAutoSync_myblog_6FFD71 confirm >nul 2>&1
"%NSSM%" install GitAutoSync_myblog_6FFD71 "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" "-NoProfile -ExecutionPolicy Bypass -File ""D:\my-blog\git_sync_realtime_GitAutoSync_myblog_6FFD71.ps1"""
"%NSSM%" set GitAutoSync_myblog_6FFD71 ObjectName LocalSystem
"%NSSM%" set GitAutoSync_myblog_6FFD71 AppDirectory "D:\my-blog"
"%NSSM%" set GitAutoSync_myblog_6FFD71 Start SERVICE_AUTO_START
"%NSSM%" set GitAutoSync_myblog_6FFD71 AppExit Default Restart
"%NSSM%" set GitAutoSync_myblog_6FFD71 AppRestartDelay 5000
"%NSSM%" set GitAutoSync_myblog_6FFD71 AppStdout "D:\my-blog\git_sync_service.log"
"%NSSM%" set GitAutoSync_myblog_6FFD71 AppStderr "D:\my-blog\git_sync_service_err.log"
"%NSSM%" set GitAutoSync_myblog_6FFD71 AppRotateFiles 1
"%NSSM%" set GitAutoSync_myblog_6FFD71 AppRotateBytes 1048576
"%NSSM%" set GitAutoSync_myblog_6FFD71 AppEnvironmentExtra GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="D:/my-blog"
"%NSSM%" start GitAutoSync_myblog_6FFD71
echo.
pause
