$ErrorActionPreference = "Stop"

$AppsRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $AppsRoot
$BackendRoot = Join-Path $AppsRoot "backend"
$FrontendRoot = Join-Path $AppsRoot "frontend"
$BackendPattern = [regex]::Escape($BackendRoot)
$FrontendPattern = [regex]::Escape($FrontendRoot)

function Get-DescendantProcessIds([int]$ParentId) {
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId")
    $result = @()
    foreach ($child in $children) {
        $result += $child.ProcessId
        $result += Get-DescendantProcessIds $child.ProcessId
    }
    return $result
}

function Stop-ProcessTree([int]$ProcessId) {
    $ids = @(Get-DescendantProcessIds $ProcessId) + $ProcessId
    foreach ($id in ($ids | Sort-Object -Descending -Unique)) {
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
}

function Stop-PortOwner([int]$Port) {
    $connections = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    foreach ($connection in $connections) {
        Stop-ProcessTree $connection.OwningProcess
    }
}

Write-Host "清理端口 3000 和 18000..." -ForegroundColor Yellow
Stop-PortOwner 3000
Stop-PortOwner 18000

$processes = @(Get-CimInstance Win32_Process | Where-Object {
    ($_.CommandLine -and $_.CommandLine -match $BackendPattern -and $_.CommandLine -match "app\.server|uvicorn") -or
    ($_.CommandLine -and $_.CommandLine -match $FrontendPattern -and $_.CommandLine -match "next")
})
foreach ($process in $processes) {
    Stop-ProcessTree $process.ProcessId
}

Start-Sleep -Milliseconds 500
Write-Host "旧服务已清理，重新启动..." -ForegroundColor Green
& (Join-Path $PSScriptRoot "start-windows.ps1")
