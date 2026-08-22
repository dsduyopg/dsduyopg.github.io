@echo off
chcp 65001 >nul
cd /d %~dp0
echo 正在统计 posts 与专栏的重复文章(仅预览,不会删除)...
echo 如需直接删除,请在命令行运行: python "清理专栏重复文章.py" --yes
echo.
python "%~dp0清理专栏重复文章.py"
pause
