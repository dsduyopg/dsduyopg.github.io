@echo off
cd /d D:\my-blog
start "" "C:\ProgramData\chocolatey\lib\hugo\tools\hugo.exe" server --port 1313 --bind 127.0.0.1
