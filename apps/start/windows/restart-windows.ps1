$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "stop-windows.ps1")
Write-Host "重新启动服务..." -ForegroundColor Green
& (Join-Path $PSScriptRoot "start-windows.ps1")
