$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Set-Location $RepoRoot

function Invoke-Git([string[]]$Arguments) {
    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Git 命令执行失败: git $($Arguments -join ' ')"
    }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "找不到 git，请先安装 Git 并加入 PATH。"
}

$branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or -not $branch) {
    throw "当前目录不是有效的 Git 工作区。"
}

if ($branch -ne "main") {
    throw "当前分支为 '$branch'，脚本只允许在 main 分支上同步。"
}

$status = @(git status --porcelain)
if ($LASTEXITCODE -ne 0) {
    throw "无法读取 Git 工作区状态。"
}

if ($status.Count -gt 0) {
    throw "工作区存在未提交改动，请先提交或暂存改动后再同步 main。"
}

Write-Host "拉取 origin/main 最新提交..." -ForegroundColor Cyan
Invoke-Git @("fetch", "origin", "main")
Invoke-Git @("merge", "--ff-only", "origin/main")

Write-Host "main 分支已同步到远端最新版本。" -ForegroundColor Green
