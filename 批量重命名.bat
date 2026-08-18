@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not "%~1"=="" (
  python rename_md.py "%~1"
) else (
  python rename_md.py
)
pause
