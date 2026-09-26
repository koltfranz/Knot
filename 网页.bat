@echo off
rem 结绳 Knot · 一键打开浏览器界面（本地服务 + 自动打开浏览器）
rem 说明：启动器只使用 ASCII 命令，避免批处理在不同代码页下解析中文参数出错
call "%~dp0knot.bat" serve --open
