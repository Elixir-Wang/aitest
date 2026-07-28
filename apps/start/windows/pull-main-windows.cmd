@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0pull-main-windows.ps1"
if errorlevel 1 (
    echo.
    echo 同步失败，请根据上面的提示处理。
    pause
    exit /b 1
)

pause
