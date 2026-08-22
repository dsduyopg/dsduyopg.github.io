@echo off
rem ============================================================
rem  Move an article from content/posts into a column (专栏)
rem  Usage:
rem    - Double-click: interactive mode (choose article + column)
rem    - Drag an article folder onto this bat: move that article
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

if "%~1"=="" (
  echo ============================================
  echo  Move article to column - interactive mode
  echo ============================================
  python "%~dp0move_to_column.py" --blog "%BLOG_DIR%"
) else (
  echo Moving article: %~nx1
  python "%~dp0move_to_column.py" --blog "%BL