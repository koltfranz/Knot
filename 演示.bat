@echo off
rem Knot demo launcher: copy the bundled demo ledger (skip if present) and open it.
call "%~dp0knot.bat" demo --open
exit /b %ERRORLEVEL%
