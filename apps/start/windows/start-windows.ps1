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

$NextCache = Join-Path $FrontendRoot ".next"
if (Test-Path -LiteralPath $NextCache) {
    $ResolvedFrontendRoot = (Resolve-Path -LiteralPath $FrontendRoot).Path.TrimEnd("\", "/")
    $ResolvedNextCache = (Resolve-Path -LiteralPath $NextCache).Path
    if ((Split-Path -Parent $ResolvedNextCache) -ne $ResolvedFrontendRoot -or
        (Split-Path -Leaf $ResolvedNextCache) -ne ".next") {
        throw "拒绝清理非预期目录: $ResolvedNextCache"
    }

    Write-Host "清理前端 Next.js 缓存: $ResolvedNextCache" -ForegroundColor Yellow
    Remove-Item -LiteralPath $ResolvedNextCache -Recurse -Force
}

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
