@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
where hugo >nul 2>nul
if %errorlevel%==0 goto :run
set "HUGO=C:\Users\62901\AppData\Local\Microsoft\WinGet\Packages\Hugo.Hugo.Extended_Microsoft.Winget.Source_8wekyb3d8bbwe\hugo.exe"
if exist "%HUGO%" goto :run_path
echo Hugo not found. Install it with: winget install Hugo.Hugo.Extended
pause
exit /b 1
:run_path
"%HUGO%" server --baseURL http://localhost:1313/
exit /b 0
:run
hugo server --baseURL http://localhost:1313/
