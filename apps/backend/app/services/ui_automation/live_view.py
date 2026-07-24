from __future__ import annotations

import base64
import json
import os
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Iterator

import websocket


VIEWPORT_WIDTH = 1440
VIEWPORT_HEIGHT = 900
_sessions: dict[str, "LiveViewSession"] = {}
_sessions_lock = threading.Lock()


@dataclass
class LiveViewSession:
    run_id: str
    status: str
    message: str
    token: str = ""
    cdp_port: int | None = None
    latest_frame: bytes = b""
    frame_sequence: int = 0
    ended_at: float | None = None
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    frame_condition: threading.Condition = field(default_factory=threading.Condition, repr=False)
    watcher: threading.Thread | None = field(default=None, repr=False)


def start_session(run_id: str) -> LiveViewSession:
    if os.getenv("UI_LIVE_VIEW_ENABLED", "1").lower() not in {"1", "true", "yes", "on"}:
        return _record_session(
            LiveViewSession(run_id=run_id, status="unavailable", message="实时查看功能未启用。")
        )

    session = LiveViewSession(
        run_id=run_id,
        status="starting",
        message="正在连接浏览器画面。",
        token=secrets.token_urlsafe(32),
        cdp_port=_allocate_local_port(),
    )
    _record_session(session)
    session.watcher = threading.Thread(
        target=_capture_screencast,
        args=(session,),
        name=f"ui-live-view-{run_id}",
        daemon=True,
    )
    session.watcher.start()
    return session


def finish_session(run_id: str) -> None:
    session = get_session(run_id)
    if not session:
        return
    session.stop_event.set()
    with session.frame_condition:
        session.frame_condition.notify_all()
    if session.watcher and session.watcher is not threading.current_thread():
        session.watcher.join(timeout=2)
    session.token = ""
    session.status = "ended"
    session.message = "本次运行已结束，可查看录制视频。"
    session.ended_at = time.monotonic()


def get_session(run_id: str) -> LiveViewSession | None:
    with _sessions_lock:
        return _sessions.get(run_id)


def validate_stream(run_id: str, token: str) -> LiveViewSession | None:
    session = get_session(run_id)
    if not session or session.status not in {"starting", "ready"}:
        return None
    if not session.token or not secrets.compare_digest(session.token, token):
        return None
    if session.stop_event.is_set():
        return None
    return session


def stream_mjpeg(run_id: str, token: str) -> Iterator[bytes]:
    session = validate_stream(run_id, token)
    if not session:
        return
    delivered_sequence = 0
    while validate_stream(run_id, token):
        with session.frame_condition:
            session.frame_condition.wait_for(
                lambda: session.frame_sequence > delivered_sequence or session.stop_event.is_set(),
                timeout=2,
            )
            if session.stop_event.is_set():
                break
            frame = session.latest_frame
            delivered_sequence = session.frame_sequence
        if not frame:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            + f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
            + frame
            + b"\r\n"
        )


def shutdown_all() -> None:
    with _sessions_lock:
        sessions = list(_sessions.values())
        _sessions.clear()
    for session in sessions:
        session.stop_event.set()
        with session.frame_condition:
            session.frame_condition.notify_all()
    for session in sessions:
        if session.watcher and session.watcher is not threading.current_thread():
            session.watcher.join(timeout=2)


def _capture_screencast(session: LiveViewSession) -> None:
    deadline = time.monotonic() + 30
    while not session.stop_event.is_set() and time.monotonic() < deadline:
        debugger_url = _find_page_debugger_url(session.cdp_port)
        if not debugger_url:
            session.stop_event.wait(0.1)
            continue
        try:
            _receive_frames(session, debugger_url)
        except (OSError, ValueError, websocket.WebSocketException):
            if not session.stop_event.is_set():
                session.stop_event.wait(0.1)
        if session.latest_frame:
            deadline = time.monotonic() + 30
    if not session.stop_event.is_set() and not session.latest_frame:
        session.status = "unavailable"
        session.message = "未能连接 Chromium 实时画面，任务将继续执行并保留录像。"
        session.token = ""
        with session.frame_condition:
            session.frame_condition.notify_all()


def _find_page_debugger_url(port: int | None) -> str:
    if port is None:
        return ""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=0.5) as response:
            targets = json.load(response)
    except (OSError, ValueError, urllib.error.URLError):
        return ""
    for target in targets:
        if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
            return str(target["webSocketDebuggerUrl"])
    return ""


def _receive_frames(session: LiveViewSession, debugger_url: str) -> None:
    connection = websocket.create_connection(
        debugger_url,
        timeout=1,
        origin=f"http://127.0.0.1:{session.cdp_port}",
        suppress_origin=True,
    )
    try:
        connection.send(json.dumps({"id": 1, "method": "Page.enable"}))
        connection.send(
            json.dumps(
                {
                    "id": 2,
                    "method": "Page.startScreencast",
                    "params": {
                        "format": "jpeg",
                        "quality": int(os.getenv("UI_LIVE_VIEW_QUALITY", "70")),
                        "maxWidth": VIEWPORT_WIDTH,
                        "maxHeight": VIEWPORT_HEIGHT,
                        "everyNthFrame": 1,
                    },
                }
            )
        )
        while not session.stop_event.is_set():
            try:
                payload = json.loads(connection.recv())
            except (TimeoutError, websocket.WebSocketTimeoutException):
                continue
            if payload.get("method") != "Page.screencastFrame":
                continue
            params = payload.get("params", {})
            frame = base64.b64decode(params.get("data", ""))
            if frame:
                with session.frame_condition:
                    session.latest_frame = frame
                    session.frame_sequence += 1
                    session.status = "ready"
                    session.message = "浏览器画面已连接。"
                    session.frame_condition.notify_all()
            connection.send(
                json.dumps(
                    {
                        "id": 3,
                        "method": "Page.screencastFrameAck",
                        "params": {"sessionId": params.get("sessionId")},
                    }
                )
            )
    finally:
        connection.close()


def _allocate_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _record_session(session: LiveViewSession) -> LiveViewSession:
    with _sessions_lock:
        _prune_ended_sessions()
        _sessions[session.run_id] = session
    return session


def _prune_ended_sessions() -> None:
    cutoff = time.monotonic() - 300
    expired = [run_id for run_id, session in _sessions.items() if session.ended_at and session.ended_at < cutoff]
    for run_id in expired:
        _sessions.pop(run_id, None)


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
