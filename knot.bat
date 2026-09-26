@echo off
rem Knot one-click launcher: prepares the environment, then runs the CLI.
rem No arguments -> interactive menu (double-click friendly).
chcp 65001 >nul
cd /d "%~dp0"
setlocal

set "PY=python"
where python >nul 2>nul
if errorlevel 1 set "PY=py -3"
where %PY% >nul 2>nul
if errorlevel 1 goto nopython

if exist ".venv\Scripts\python.exe" goto run
goto bootstrap

:bootstrap
echo [Knot] First run: creating venv and installing (needs network once)...
%PY% -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -e .
if errorlevel 1 goto failed
goto run

:run
if "%~1"=="" goto menu
".venv\Scripts\python.exe" -m knot %*
exit /b %ERRORLEVEL%

:menu
".venv\Scripts\python.exe" -m knot menu
set "CODE=%ERRORLEVEL%"
echo.
pause
exit /b %CODE%

:nopython
echo [Knot] Python 3.11+ not found. Download: https://www.python.org/downloads/
pause
exit /b 2

:failed
echo [Knot] Setup failed. Check your network connection or Python version.
pause
exit /b 2
