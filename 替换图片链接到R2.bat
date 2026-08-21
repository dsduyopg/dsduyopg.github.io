@echo off
setlocal enabledelayedexpansion

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

set "FIRST=%~1"
if "%FIRST%"=="" goto drag_prompt
if "%FIRST:~0,2%"=="--" goto advanced

set "MD_FILE=%FIRST%"
if "%~2"=="" (
  set /p SLUG=Project slug: 
) else (
  set "SLUG=%~2"
)
if "%SLUG%"=="" (
  echo Project slug is required.
  goto end
)
python "%SCRIPT%" --file "%MD_FILE%" --slug "%SLUG%" --check
goto end

:drag_prompt
echo.
echo Replace local images with R2 URLs
echo.
echo 1. Drag the markdown file into this window
echo 2. Press Enter
echo 3. Type a short English slug, e.g. blog1
echo.
set /p MD_FILE=Markdown file: 
set /p SLUG=Project slug: 
set "MD_FILE=%MD_FILE:"=%"
if "%MD_FILE%"=="" goto drag_prompt
if "%SLUG%"=="" goto drag_prompt
python "%SCRIPT%" --file "%MD_FILE%" --slug "%SLUG%" --check
goto end

:advanced
python "%SCRIPT%" %*

:end
pause
