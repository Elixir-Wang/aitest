"""Page exploration services.

入口：
- service: HTTP facade，提供 17 个 run/artifact 管理 API
- event_bus: 进程内事件总线（run 级别）

子模块（service 的私有实现，不直接 import）：
- browser_session: Playwright 长连接子进程封装（agent tools 层用）
- locking / page_artifact_writer / page_artifact_validator: 单 page 写、校验、锁
"""

from app.services.page_exploration import (  # noqa: F401
    event_bus,
    service as page_exploration_service,
)
