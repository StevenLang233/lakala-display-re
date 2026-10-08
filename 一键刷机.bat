@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0main\demo\setup\setup.ps1" %*
set "qdisplay_result=%errorlevel%"
echo.
echo QDisplay setup exit code: %qdisplay_result%
pause
exit /b %qdisplay_result%
