@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Please install Python 3.11+ and add it to PATH.
  pause
  exit /b 1
)

set "SCRIPT=%~dp0replace_images_to_r2.py"
if not exist "%SCRIPT%" (
  echo Script not found: %SCRIPT%
  pause
  exit /b 1
)

if "%~1"=="" goto interactive

python "%SCRIPT%" %*
goto end

:interactive
echo.
echo 图片链接替换到 R2
echo.
set /p MD_PATH=请拖入 md 文件: 
set /p SLUG=请输入项目 slug: 
set "MD_PATH=%MD_PATH:"=%"
if "%MD_PATH%"=="" goto interactive
if "%SLUG%"=="" goto interactive
echo.
set /p INPLACE=直接覆盖原文件? (y/n): 
if /i "%INPLACE%"=="y" (
  python "%SCRIPT%" --file "%MD_PATH%" --slug "%SLUG%" --in-place --check
) else (
  python "%SCRIPT%" --file "%MD_PATH%" --slug "%SLUG%" --check
)

:end
pause
