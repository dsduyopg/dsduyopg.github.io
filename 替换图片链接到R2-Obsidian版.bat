@echo off
setlocal enabledelayedexpansion

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install Python 3.11+ and add it to PATH.
  pause
  exit /b 1
)

set "SCRIPT=%~dp0obsidian_images_to_r2.py"
if not exist "%SCRIPT%" (
  echo Script not found: %SCRIPT%
  pause
  exit /b 1
)

echo.
echo ==========================================
echo   Obsidian note  --^>  R2 image links
echo ==========================================
echo.
echo 1. Drag your .md note into this window, press Enter
echo 2. Press Enter to auto-detect slug and attachment folder
echo 3. The -r2.md file is written next to your note
echo.

set /p MD_FILE=Note file: 
set "MD_FILE=%MD_FILE:"=%"
if "%MD_FILE%"=="" goto end
if not exist "%MD_FILE%" (
  echo File not found: %MD_FILE%
  goto end
)

echo.
set /p SLUG=Slug (Enter = use note filename): 
set /p SUBDIR=Attachment folder (Enter = auto-detect): 
set /p INPLACE=Overwrite original? type y to overwrite, Enter = write -r2.md : 

set "ARGS="
if not "%SLUG%"=="" set ARGS=!ARGS! --slug "%SLUG%"
if not "%SUBDIR%"=="" set ARGS=!ARGS! --subdir "%SUBDIR%"
if /i "%INPLACE%"=="y" set ARGS=!ARGS! --in-place

echo.
python "%SCRIPT%" --file "%MD_FILE%" !ARGS! --check

:end
echo.
pause
