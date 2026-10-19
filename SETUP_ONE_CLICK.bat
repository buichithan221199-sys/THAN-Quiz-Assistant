@echo off
setlocal
cd /d "%~dp0"
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
if errorlevel 1 (
 echo.
 echo Installation failed. Please send a screenshot of the error.
 pause
 exit /b 1
)
echo.
echo Installation completed. You can launch THAN Quiz Assistant from Desktop.
pause
