from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


VIEWPORT_WIDTH = 1440
VIEWPORT_HEIGHT = 900
_DISPLAY_RANGE = range(90, 190)
_sessions: dict[str, "LiveViewSession"] = {}
_sessions_lock = threading.Lock()
_startup_lock = threading.Lock()


@dataclass
class LiveViewSession:
    run_id: str
    status: str
    message: str
    token: str = ""
    display_number: int | None = None
    xvfb_process: subprocess.Popen | None = None
    ended_at: float | None = None

    @property
    def display(self) -> str:
        return f":{self.display_number}" if self.display_number is not None else ""


def start_session(run_id: str) -> LiveViewSession:
    if os.getenv("UI_LIVE_VIEW_ENABLED", "1").lower() not in {"1", "true", "yes", "on"}:
        return _record_unavailable(run_id, "实时查看功能未启用。")

    xvfb = shutil.which("Xvfb")
    ffmpeg = shutil.which("ffmpeg")
    if not xvfb or not ffmpeg:
        return _record_unavailable(run_id, "运行环境缺少 Xvfb 或 ffmpeg，无法提供实时画面。")

    with _startup_lock:
        display_number = _allocate_display()
        if display_number is None:
            return _record_unavailable(run_id, "没有可用的虚拟显示器，请稍后重试。")
        process = subprocess.Popen(
            [
                xvfb,
                f":{display_number}",
                "-screen",
                "0",
                f"{VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}x24",
                "-nolisten",
                "tcp",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        session = LiveViewSession(
            run_id=run_id,
            status="starting",
            message="正在启动浏览器画面。",
            token=secrets.token_urlsafe(32),
            display_number=display_number,
            xvfb_process=process,
        )
        with _sessions_lock:
            _prune_ended_sessions()
            _sessions[run_id] = session

    socket_path = Path(f"/tmp/.X11-unix/X{display_number}")
    for _ in range(40):
        if process.poll() is not None:
            break
        if socket_path.exists():
            session.status = "ready"
            session.message = "浏览器画面已连接。"
            return session
        time.sleep(0.05)

    _terminate(process)
    session.status = "unavailable"
    session.message = "虚拟显示器启动失败，任务将继续以无实时画面的方式执行。"
    session.token = ""
    session.xvfb_process = None
    return session


def finish_session(run_id: str) -> None:
    with _sessions_lock:
        session = _sessions.get(run_id)
    if not session:
        return
    if session.xvfb_process:
        _terminate(session.xvfb_process)
    session.xvfb_process = None
    session.token = ""
    session.status = "ended"
    session.message = "本次运行已结束，可查看录制视频。"
    session.ended_at = time.monotonic()


def get_session(run_id: str) -> LiveViewSession | None:
    with _sessions_lock:
        return _sessions.get(run_id)


def validate_stream(run_id: str, token: str) -> LiveViewSession | None:
    session = get_session(run_id)
    if not session or session.status != "ready" or not secrets.compare_digest(session.token, token):
        return None
    if not session.xvfb_process or session.xvfb_process.poll() is not None:
        return None
    return session


def stream_mjpeg(run_id: str, token: str) -> Iterator[bytes]:
    session = validate_stream(run_id, token)
    if not session:
        return
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return
    process = subprocess.Popen(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "x11grab",
            "-draw_mouse",
            "0",
            "-framerate",
            os.getenv("UI_LIVE_VIEW_FPS", "8"),
            "-video_size",
            f"{VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}",
            "-i",
            session.display,
            "-q:v",
            "5",
            "-f",
            "mpjpeg",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        while process.poll() is None and validate_stream(run_id, token):
            chunk = process.stdout.read(64 * 1024) if process.stdout else b""
            if not chunk:
                break
            yield chunk
    finally:
        _terminate(process)


def shutdown_all() -> None:
    with _sessions_lock:
        sessions = list(_sessions.values())
        _sessions.clear()
    for session in sessions:
        if session.xvfb_process:
            _terminate(session.xvfb_process)


def _allocate_display() -> int | None:
    with _sessions_lock:
        allocated = {
            session.display_number
            for session in _sessions.values()
            if session.display_number is not None and session.status in {"starting", "ready"}
        }
        for display_number in _DISPLAY_RANGE:
            if display_number not in allocated and not Path(f"/tmp/.X11-unix/X{display_number}").exists():
                return display_number
    return None


def _record_unavailable(run_id: str, message: str) -> LiveViewSession:
    session = LiveViewSession(run_id=run_id, status="unavailable", message=message)
    with _sessions_lock:
        _prune_ended_sessions()
        _sessions[run_id] = session
    return session


def _prune_ended_sessions() -> None:
    cutoff = time.monotonic() - 300
    expired = [run_id for run_id, session in _sessions.items() if session.ended_at and session.ended_at < cutoff]
    for run_id in expired:
        _sessions.pop(run_id, None)


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
        process.wait()


__all__ = [
    "VIEWPORT_HEIGHT",
    "VIEWPORT_WIDTH",
    "finish_session",
    "get_session",
    "shutdown_all",
    "start_session",
    "stream_mjpeg",
    "validate_stream",
]
