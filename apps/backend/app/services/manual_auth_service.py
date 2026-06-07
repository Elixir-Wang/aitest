import os
import secrets
import subprocess
import threading
from pathlib import Path

from app.core.db import connect
from app.core.environment_auth_state import auth_state_path, auth_state_summary
from app.core.environment_credentials import load_credentials
from app.core.exceptions import api_error
from app.core.settings import PLAYWRIGHT_BROWSER_CHANNEL, PLAYWRIGHT_RUNNER_DIR
from app.repositories import environment_repo
from app.services.environment_service import _ensure_project_visible


_sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()


def start_manual_auth_session(project_id: str, environment_id: str, actor) -> dict:
    environment = _get_manual_auth_environment(project_id, environment_id, actor)
    credentials = load_credentials(project_id, environment_id)
    _close_existing_environment_sessions(environment_id)
    state_path = auth_state_path(project_id, environment_id)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    session_id = f"manual-auth-{secrets.token_hex(8)}"
    process = _launch_manual_auth_process(
        site_url=environment["site_url"],
        storage_state_path=state_path,
        browser_channel=PLAYWRIGHT_BROWSER_CHANNEL,
        credentials=credentials,
    )
    with _sessions_lock:
        _sessions[session_id] = {
            "project_id": project_id,
            "environment_id": environment_id,
            "process": process,
            "storage_state_path": state_path,
        }
    auth_state = _account_password_auth_state(project_id, environment_id)
    has_saved_credentials = credentials is not None
    return {
        "session_id": session_id,
        "status": "waiting_human",
        "auth_state_status": auth_state["status"],
        "auth_state_expires_at": auth_state["expires_at"],
        "has_saved_credentials": has_saved_credentials,
        "message": (
            "已打开登录窗口，会尝试自动填充用户名和密码，请完成登录后保存登录态。"
            if has_saved_credentials
            else "已打开登录窗口；当前环境未保存可自动填充的密码，请手动输入账号密码并完成登录后保存登录态。"
        ),
    }


def save_manual_auth_session(project_id: str, environment_id: str, session_id: str, actor) -> dict:
    _get_manual_auth_environment(project_id, environment_id, actor)
    session = _pop_session(session_id, project_id, environment_id)
    process = session["process"]
    if process.poll() is not None:
        return _ended_session_summary(project_id, environment_id, session_id)
    stdin = getattr(process, "stdin", None)
    if stdin is None:
        _terminate_process(process)
        raise api_error(500, "MANUAL_AUTH_SESSION_UNAVAILABLE", "人工登录会话不可用，请重新打开登录窗口。")
    try:
        stdin.write("save\n")
        stdin.flush()
        process.wait(timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        _terminate_process(process)
        raise api_error(500, "MANUAL_AUTH_SAVE_FAILED", "保存登录态失败，请重新完成人工登录。") from exc
    if process.returncode != 0:
        raise api_error(500, "MANUAL_AUTH_SAVE_FAILED", "保存登录态失败，请确认已完成登录后重试。")
    auth_state = _account_password_auth_state(project_id, environment_id)
    return {
        "session_id": session_id,
        "status": "saved",
        "auth_state_status": auth_state["status"],
        "auth_state_expires_at": auth_state["expires_at"],
        "has_saved_credentials": _has_saved_credentials(project_id, environment_id),
        "message": "登录态已保存。",
    }


def cancel_manual_auth_session(project_id: str, environment_id: str, session_id: str, actor) -> dict:
    _get_manual_auth_environment(project_id, environment_id, actor)
    session = _pop_session(session_id, project_id, environment_id)
    if session["process"].poll() is not None:
        return _ended_session_summary(project_id, environment_id, session_id)
    _terminate_process(session["process"])
    auth_state = _account_password_auth_state(project_id, environment_id)
    return {
        "session_id": session_id,
        "status": "cancelled",
        "auth_state_status": auth_state["status"],
        "auth_state_expires_at": auth_state["expires_at"],
        "has_saved_credentials": _has_saved_credentials(project_id, environment_id),
        "message": "人工登录会话已取消。",
    }


def get_manual_auth_session_status(project_id: str, environment_id: str, session_id: str, actor) -> dict:
    _get_manual_auth_environment(project_id, environment_id, actor)
    with _sessions_lock:
        session = _sessions.get(session_id)
        if not session or session["project_id"] != project_id or session["environment_id"] != environment_id:
            session = None
        elif session["process"].poll() is not None:
            _sessions.pop(session_id, None)
            return _ended_session_summary(project_id, environment_id, session_id, auto_save_possible=True)
        else:
            auth_state = _account_password_auth_state(project_id, environment_id)
            return {
                "session_id": session_id,
                "status": "waiting_human",
                "auth_state_status": auth_state["status"],
                "auth_state_expires_at": auth_state["expires_at"],
                "has_saved_credentials": _has_saved_credentials(project_id, environment_id),
                "message": "已打开登录窗口，请在浏览器中完成登录后保存登录态。",
            }
    return _ended_session_summary(project_id, environment_id, session_id)


def _get_manual_auth_environment(project_id: str, environment_id: str, actor):
    with connect() as db:
        environment = environment_repo.find_by_id(db, environment_id)
        if not environment or environment["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "环境不存在。")
        _ensure_project_visible(environment, actor)
    if environment["login_strategy"] != "account_password" or environment["captcha_strategy"] != "manual":
        raise api_error(400, "MANUAL_AUTH_NOT_ENABLED", "仅账号密码模式下的人工登录验证码策略可以打开登录窗口。")
    if not bool(environment["reuse_auth_state"]):
        raise api_error(400, "MANUAL_AUTH_NOT_ENABLED", "人工登录必须开启复用登录态。")
    return environment


def _close_existing_environment_sessions(environment_id: str) -> None:
    with _sessions_lock:
        session_ids = [
            session_id
            for session_id, session in _sessions.items()
            if session["environment_id"] == environment_id
        ]
        sessions = [_sessions.pop(session_id) for session_id in session_ids]
    for session in sessions:
        _terminate_process(session["process"])


def _pop_session(session_id: str, project_id: str, environment_id: str) -> dict:
    with _sessions_lock:
        session = _sessions.pop(session_id, None)
    if not session or session["project_id"] != project_id or session["environment_id"] != environment_id:
        raise api_error(404, "MANUAL_AUTH_SESSION_NOT_FOUND", "人工登录会话不存在或已结束。")
    return session


def _launch_manual_auth_process(
    *,
    site_url: str,
    storage_state_path: Path,
    browser_channel: str,
    credentials: dict | None = None,
):
    script_path = PLAYWRIGHT_RUNNER_DIR / "manual-auth-session.mjs"
    env = {**os.environ}
    if credentials:
        env["AI_TESTING_LOGIN_USERNAME"] = credentials["username"]
        env["AI_TESTING_LOGIN_PASSWORD"] = credentials["password"]
    else:
        env.pop("AI_TESTING_LOGIN_USERNAME", None)
        env.pop("AI_TESTING_LOGIN_PASSWORD", None)
    return subprocess.Popen(
        ["node", str(script_path), site_url, str(storage_state_path), browser_channel],
        cwd=PLAYWRIGHT_RUNNER_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
    )


def _account_password_auth_state(project_id: str, environment_id: str) -> dict:
    return auth_state_summary(
        project_id=project_id,
        environment_id=environment_id,
        login_strategy="account_password",
        reuse_auth_state=True,
    )


def _ended_session_summary(
    project_id: str,
    environment_id: str,
    session_id: str,
    *,
    auto_save_possible: bool = False,
) -> dict:
    auth_state = _account_password_auth_state(project_id, environment_id)
    if auto_save_possible and auth_state["status"] in {"valid", "unknown_expiry"}:
        return {
            "session_id": session_id,
            "status": "auto_saved",
            "auth_state_status": auth_state["status"],
            "auth_state_expires_at": auth_state["expires_at"],
            "has_saved_credentials": _has_saved_credentials(project_id, environment_id),
            "message": "检测到登录成功，登录态已自动保存。",
        }
    return {
        "session_id": session_id,
        "status": "ended",
        "auth_state_status": auth_state["status"],
        "auth_state_expires_at": auth_state["expires_at"],
        "has_saved_credentials": _has_saved_credentials(project_id, environment_id),
        "message": "登录窗口已关闭，请重新打开登录窗口。",
    }


def _has_saved_credentials(project_id: str, environment_id: str) -> bool:
    return load_credentials(project_id, environment_id) is not None


def _terminate_process(process) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
        process.wait()
