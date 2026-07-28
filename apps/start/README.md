# 一键启动脚本

项目服务端口：

- 前端：`3000`
- 后端：`18000`

## Windows

双击以下文件即可启动：

- `start-windows.cmd`

或在 PowerShell 中执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start-windows.ps1
```

双击以下文件即可重启并清理旧服务：

- `restart-windows.cmd`

或在 PowerShell 中执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\restart-windows.ps1
```

## 同步远端 main

双击以下文件即可拉取 `origin/main` 最新代码：

- `pull-main-windows.cmd`

或在 PowerShell 中执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\pull-main-windows.ps1
```

脚本仅允许在 `main` 分支、工作区无未提交改动时执行，并使用 fast-forward-only 合并，避免覆盖本地代码或产生意外合并提交。

也可以右键使用 PowerShell 运行脚本。脚本会分别打开前端和后端窗口。

## macOS

首次执行：

```bash
chmod +x start-macos.sh restart-macos.sh
./start-macos.sh
```

之后可以双击 `start-macos.command` 启动。

重启并清理旧服务：

```bash
./restart-macos.sh
```

也可以双击 `restart-macos.command` 重启。

macOS 脚本将日志写入 `apps/start/logs/`。双击使用时，可将 `.sh` 文件改名为 `.command`，或通过终端执行。
