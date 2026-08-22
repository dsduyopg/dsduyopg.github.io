@echo off
rem ============================================================
rem  Clean up duplicate articles between posts and columns
rem  Usage: double-click to preview, or run from command line.
rem    python cleanup_dup_articles.py --blog D:\my-blog --yes
rem  Change BLOG_DIR below to point to your blog root.
rem ============================================================
chcp 65001 >nul
set "BLOG_DIR=D:\my-blog"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Please install Python 3 and add it to PATH.
  pause
  exit /b 1
)

if not exist "%BLOG_DIR%\content\posts" (
  echo [ERROR] Blog directory not found: %BLOG_DIR%
  echo         Please edit BLOG_DIR in this bat file.
  pause
  exit /b 1
)

echo Scanning duplicates between posts and columns (preview only)...
echo Blog dir: %BLOG_DIR%
echo.
python "%~dp0cleanup_dup_articles.py" --blog "%BLOG_DIR%"
pause
