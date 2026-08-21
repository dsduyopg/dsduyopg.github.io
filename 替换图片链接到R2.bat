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
set "R2_BASE=https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev"
set /p R2_BASE=R2 base URL (Enter for default): 
set /p OUT_PATH=Output path, Enter for auto: 
if defined OUT_PATH set "OUT_PATH=%OUT_PATH:"=%"
if not defined OUT_PATH (
  python "%SCRIPT%" --file "%MD_FILE%" --slug "%SLUG%" --base "%R2_BASE%" --check
) else (
  python "%SCRIPT%" --file "%MD_FILE%" --slug "%SLUG%" --base "%R2_BASE%" --output "%OUT_PATH%" --check
)
goto end

:drag_prompt
echo.
echo Replace local images with R2 URLs
echo.
echo 1. Drag the markdown file into this window
echo 2. Press Enter
echo 3. Type a short English slug, e.g. blog1
echo 4. Paste the R2 base URL, or press Enter for default
echo 5. Optional output path, or press Enter for auto
echo.
set /p MD_FILE=Markdown file: 
set /p SLUG=Project slug: 
set "MD_FILE=%MD_FILE:"=%"
if "%MD_FILE%"=="" goto drag_prompt
if "%SLUG%"=="" goto drag_prompt
set "R2_BASE=https://pub-aee2c40b7d9a4adca3ba6ad7e73a693e.r2.dev"
set /p R2_BASE=R2 base URL (Enter for default): 
set /p OUT_PATH=Output path, Enter for auto: 
if defined OUT_PATH set "OUT_PATH=%OUT_PATH:"=%"
if not defined OUT_PATH (
  python "%SCRIPT%" --file "%MD_FILE%" --slug "%SLUG%" --base "%R2_BASE%" --check
) else (
  python "%SCRIPT%" --file "%MD_FILE%" --slug "%SLUG%" --base "%R2_BASE%" --output "%OUT_PATH%" --check
)
goto end

:advanced
python "%SCRIPT%" %*

:end
pause
