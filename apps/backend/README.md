# AI Testing System Backend

FastAPI + SQLite backend for first-version auth, user permission management, and model configuration.

## Run

```bash
cd apps/backend
uv sync
uv run python -m app.server
```

The server cancels active HTTP and SSE requests immediately on `Ctrl+C`.

## Test

```bash
cd apps/backend
uv run pytest
```

Seed accounts:

| Username | Password | Role |
| --- | --- | --- |
| admin | admin | 管理员 |

# UI 自动化可视执行

UI 自动化执行器默认保持无头模式。需要录制有头浏览器执行过程时，在后端服务启动环境中设置：

```bash
UI_HEADED=1
```

执行器会同时生成 Playwright 视频证据。Linux 服务没有桌面环境时，如果系统已安装 `xvfb-run`，会自动使用 1440x900 的虚拟显示器；运行详情页会在任务完成后提供视频播放和 Trace 下载。
