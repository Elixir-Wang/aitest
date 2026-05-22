"""
日志框架配置。

目录结构（apps/backend/logs/）：
    app/YYYY-MM-DD.log     — INFO+  通用应用日志
    error/YYYY-MM-DD.log   — WARNING+  错误日志，快速定位问题
    access/YYYY-MM-DD.log  — 每个 HTTP 请求的进出记录
    agent/YYYY-MM-DD.log   — AI Agent 执行全程记录

轮转策略：每天 00:00 轮转，保留 30 天，旧文件 zip 压缩，异步写入不阻塞主线程。
trace_id 通过 contextvars 在同一请求的所有日志行中自动注入。
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from pathlib import Path

from loguru import logger

# ── 路径 ──────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[2]
LOGS_DIR = ROOT_DIR / "logs"

# ── trace_id 上下文变量（async 安全） ─────────────────────────────────────────
_trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")


def set_trace_id(trace_id: str) -> None:
    _trace_id_ctx.set(trace_id)


def get_trace_id() -> str:
    return _trace_id_ctx.get()


# ── 日志格式 ──────────────────────────────────────────────────────────────────
_CONSOLE_FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level:<8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<yellow>{extra[trace_id]}</yellow> | "
    "{message}"
)

_FILE_FMT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level:<8} | "
    "{name}:{function}:{line} | "
    "{extra[trace_id]} | "
    "{message}"
)

_ACCESS_FMT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{extra[trace_id]} | "
    "{message}"
)

# agent 频道专用 logger 实例（通过 bind 携带 channel 标识）
agent_logger = logger.bind(channel="agent")


def setup_logging(level: str = "INFO") -> None:
    """初始化所有日志处理器，应在应用启动时调用一次。"""
    _create_log_dirs()

    # loguru 全局默认 extra（当请求上下文中无 trace_id 时使用 "-"）
    logger.configure(extra={"trace_id": "-"})

    # 移除 loguru 默认 stderr handler
    logger.remove()

    # 控制台（DEBUG+，开发友好的彩色格式）
    logger.add(
        sys.stdout,
        format=_CONSOLE_FMT,
        level="DEBUG",
        colorize=True,
        backtrace=True,
        diagnose=True,
        filter=_inject_trace_id,
    )

    # 通用应用日志（INFO+）
    logger.add(
        str(LOGS_DIR / "app" / "{time:YYYY-MM-DD}.log"),
        format=_FILE_FMT,
        level=level,
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=False,
        enqueue=True,
        filter=lambda r: _inject_trace_id(r) and r["extra"].get("channel") != "agent",
    )

    # 错误日志（WARNING+，与 app 日志互补，专门用于排查问题）
    logger.add(
        str(LOGS_DIR / "error" / "{time:YYYY-MM-DD}.log"),
        format=_FILE_FMT,
        level="WARNING",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=False,
        enqueue=True,
        filter=_inject_trace_id,
    )

    # HTTP 访问日志（INFO+，只记录带 channel=access 的消息）
    logger.add(
        str(LOGS_DIR / "access" / "{time:YYYY-MM-DD}.log"),
        format=_ACCESS_FMT,
        level="INFO",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,
        filter=lambda r: _inject_trace_id(r) and r["extra"].get("channel") == "access",
    )

    # AI Agent 执行日志（DEBUG+，只记录带 channel=agent 的消息）
    logger.add(
        str(LOGS_DIR / "agent" / "{time:YYYY-MM-DD}.log"),
        format=_FILE_FMT,
        level="DEBUG",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=False,
        enqueue=True,
        filter=lambda r: _inject_trace_id(r) and r["extra"].get("channel") == "agent",
    )

    # 将 uvicorn / stdlib logging 路由到 loguru
    _intercept_stdlib_logging()


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _create_log_dirs() -> None:
    for sub in ("app", "error", "access", "agent"):
        (LOGS_DIR / sub).mkdir(parents=True, exist_ok=True)


def _inject_trace_id(record: dict) -> bool:
    """filter 函数：将当前请求的 trace_id 注入每条日志记录的 extra。"""
    record["extra"]["trace_id"] = _trace_id_ctx.get()
    return True


class _StdlibInterceptHandler(logging.Handler):
    """将标准库 logging 日志转发给 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno  # type: ignore[assignment]

        # 找到真实调用栈帧（跳过 logging 内部帧）
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _intercept_stdlib_logging() -> None:
    """接管 uvicorn、fastapi 等组件的标准库日志，统一输出到 loguru。"""
    handler = _StdlibInterceptHandler()
    logging.basicConfig(handlers=[handler], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "httpx"):
        log = logging.getLogger(name)
        log.handlers = [handler]
        log.propagate = False
