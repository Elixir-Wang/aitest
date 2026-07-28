$ErrorActionPreference = "Stop"

$AppsRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ProjectRoot = Split-Path -Parent $AppsRoot
$BackendRoot = Join-Path $AppsRoot "backend"
$FrontendRoot = Join-Path $AppsRoot "frontend"

function Assert-Command($Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "找不到命令 '$Name'，请先安装并加入 PATH。"
    }
}

Assert-Command "uv"
Assert-Command "npm"

Write-Host "启动后端: http://127.0.0.1:18000" -ForegroundColor Cyan
Start-Process powershell.exe -WorkingDirectory $BackendRoot -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", "uv run python -m app.server"
)

Write-Host "启动前端: http://127.0.0.1:3000" -ForegroundColor Cyan
Start-Process powershell.exe -WorkingDirectory $FrontendRoot -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", "npm run dev"
)

Write-Host "前后端启动命令已发送。" -ForegroundColor Green
