# 一键启动脚本

项目服务端口：

- 前端：`3000`
- 后端：`18000`

目录结构：

- `macos/`：macOS 启动、停止和重启脚本
- `windows/`：Windows 启动、停止、重启和同步脚本

## Windows

双击以下文件即可启动：

- `windows/start-windows.ps1`

或在 PowerShell 中执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\start-windows.ps1
```

双击以下文件即可重启并清理旧服务：

- `windows/restart-windows.ps1`

或在 PowerShell 中执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\restart-windows.ps1
```

停止前后端服务：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\stop-windows.ps1
```

## 同步远端 main

双击以下文件即可拉取 `origin/main` 最新代码：

- `windows/pull-main-windows.cmd`

或在 PowerShell 中执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\pull-main-windows.ps1
```

脚本仅允许在 `main` 分支、工作区无未提交改动时执行，并使用 fast-forward-only 合并，避免覆盖本地代码或产生意外合并提交。

也可以右键使用 PowerShell 运行脚本。脚本会分别打开前端和后端窗口。

## macOS

首次执行：

```bash
chmod +x macos/start-macos.sh macos/stop-macos.sh macos/restart-macos.sh
./macos/start-macos.sh
```

停止前后端服务：

```bash
./macos/stop-macos.sh
```

重启并清理旧服务：

```bash
./macos/restart-macos.sh
```

macOS 脚本将日志写入 `apps/start/macos/logs/`。
