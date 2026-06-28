import json
import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.db import connect
from app.core.environment_auth_state import auth_state_path, auth_state_summary
from app.core.environment_credentials import load_credentials
from app.core.settings import PLAYWRIGHT_BROWSER_CHANNEL, PLAYWRIGHT_RUNNER_DIR
from app.repositories import environment_repo
from app.services import captcha_solver_service
from app.services import login_form_analyzer_service
from app.services import operation_log_service

AUTO_AUTH_STATUSES = {"idle", "queued", "running", "succeeded", "failed"}
_running_environments: set[str] = set()
_running_lock = threading.Lock()


def reset_auto_auth_status(environment_id: str) -> None:
    _write_auto_auth_status(environment_id, status="idle", message="")


def should_schedule_ai_letter_auto_auth(environment: dict) -> bool:
    return (
        environment.get("login_strategy") == "account_password"
        and environment.get("captcha_strategy") == "ai_letter"
        and bool(environment.get("reuse_auth_state"))
        and bool(environment.get("has_saved_credentials"))
    )


def schedule_ai_letter_auto_auth(environment_id: str) -> None:
    with _running_lock:
        if environment_id in _running_environments:
            return
        _running_environments.add(environment_id)
    _write_auto_auth_status(
        environment_id,
        status="queued",
        message="等待自动登录",
    )
    thread = threading.Thread(
        target=_run_ai_letter_auto_auth_safe,
        args=(environment_id,),
        daemon=True,
    )
    thread.start()


def trigger_ai_letter_auto_auth(environment_id: str) -> None:
    environment = _load_environment(environment_id)
    has_saved_credentials = load_credentials(environment_id) is not None
    if not should_schedule_ai_letter_auto_auth(
        {
            **environment,
            "has_saved_credentials": has_saved_credentials,
        }
    ):
        raise ValueError("environment is not eligible for ai letter auto auth")

    # 🔧 修复：先检查登录态是否有效，避免不必要的重新登录
    auth_summary = auth_state_summary(
        environment_id=environment_id,
        login_strategy=environment["login_strategy"],
        reuse_auth_state=bool(environment.get("reuse_auth_state")),
    )

    if auth_summary["status"] == "valid":
        # 登录态有效，直接标记为成功，无需重新登录
        _write_auto_auth_status(
            environment_id,
            status="succeeded",
            message="登录态已存在且有效，无需重新登录。",
        )
        return

    schedule_ai_letter_auto_auth(environment_id)


def get_auto_auth_status(environment_id: str) -> dict:
    path = _auto_auth_status_path(environment_id)
    if not path.exists():
        return {"status": "idle", "message": "", "updated_at": None, "last_error_code": ""}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {"status": "failed", "message": "自动登录状态读取失败", "updated_at": None, "last_error_code": "STATUS_READ_FAILED"}
    status = str(payload.get("status") or "idle")
    if status not in AUTO_AUTH_STATUSES:
        status = "failed"
    return {
        "status": status,
        "message": str(payload.get("message") or ""),
        "updated_at": payload.get("updated_at"),
        "last_error_code": str(payload.get("last_error_code") or ""),
    }


def _run_ai_letter_auto_auth_safe(environment_id: str) -> None:
    try:
        _run_ai_letter_auto_auth(environment_id)
    finally:
        with _running_lock:
            _running_environments.discard(environment_id)


def _run_ai_letter_auto_auth(environment_id: str) -> None:
    environment = _load_environment(environment_id)
    if not should_schedule_ai_letter_auto_auth(
        {
            **environment,
            "has_saved_credentials": load_credentials(environment_id) is not None,
        }
    ):
        _write_auto_auth_status(environment_id, status="idle", message="")
        return

    credentials = load_credentials(environment_id)
    if credentials is None:
        _write_auto_auth_status(
            environment_id,
            status="failed",
            message="未找到可自动登录的账号密码。",
            last_error_code="MISSING_CREDENTIALS",
        )
        _record_auto_auth_event(
            environment_id,
            result="failed",
            summary="环境自动登录失败：未找到可自动登录的账号密码",
            failure_reason="MISSING_CREDENTIALS",
        )
        return

    state_path = auth_state_path(environment_id)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    _write_auto_auth_status(
        environment_id,
        status="running",
        message="正在通过 Playwright 自动登录",
    )

    process = _launch_ai_letter_login_process(
        site_url=environment["site_url"],
        storage_state_path=state_path,
        login_plan_path=_login_plan_path(environment_id),
        browser_channel=PLAYWRIGHT_BROWSER_CHANNEL,
        credentials=credentials,
    )
    events_path = state_path.parent / "auto-login-events.jsonl"
    if events_path.exists():
        events_path.unlink()

    try:
        if process.stdin is None or process.stdout is None:
            raise RuntimeError("AUTO_AUTH_PROCESS_UNAVAILABLE")

        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            kind = str(event.get("kind") or "")
            _append_auto_login_event(events_path, event)
            if kind == "login_plan_loaded":
                _write_auto_auth_status(
                    environment_id,
                    status="running",
                    message="正在复用已保存的登录计划",
                )
                continue

            if kind == "login_plan_invalid":
                _write_auto_auth_status(
                    environment_id,
                    status="running",
                    message="已保存登录计划失效，正在重新分析登录页",
                )
                continue

            if kind == "login_page_observed":
                page_image_path = Path(str(event.get("page_image_path") or ""))
                elements_path = Path(str(event.get("elements_path") or ""))
                _write_auto_auth_status(
                    environment_id,
                    status="running",
                    message="正在分析登录页元素",
                )
                try:
                    elements = json.loads(elements_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                    elements = []
                try:
                    plan = login_form_analyzer_service.analyze_login_form(page_image_path, elements)
                except login_form_analyzer_service.LoginFormAnalyzerError:
                    plan = {"type": "login_form_plan", "strategy": "heuristic"}
                else:
                    plan = {"type": "login_form_plan", **plan}
                process.stdin.write(json.dumps(plan, ensure_ascii=False) + "\n")
                process.stdin.flush()
                continue

            if kind == "captcha_challenge":
                attempt = int(event.get("attempt") or 1)
                image_path = Path(str(event.get("image_path") or ""))
                expected_length = _safe_expected_captcha_length(event.get("expected_length"))
                _write_auto_auth_status(
                    environment_id,
                    status="running",
                    message=f"正在识别验证码（第 {attempt}/3 次）",
                )
                try:
                    answer = captcha_solver_service.solve_letter_captcha(image_path, expected_length=expected_length)
                except captcha_solver_service.CaptchaSolverError as exc:
                    message = str(exc)
                    _write_auto_auth_status(
                        environment_id,
                        status="failed",
                        message=message,
                        last_error_code="CAPTCHA_SOLVE_FAILED",
                    )
                    _record_auto_auth_event(
                        environment_id,
                        result="failed",
                        summary="环境自动登录失败：验证码识别失败",
                        failure_reason="CAPTCHA_SOLVE_FAILED",
                        detail=message,
                    )
                    process.stdin.write(json.dumps({"type": "abort"}, ensure_ascii=False) + "\n")
                    process.stdin.flush()
                    return

                process.stdin.write(
                    json.dumps({"type": "captcha_answer", "attempt": attempt, "value": answer}, ensure_ascii=False) + "\n"
                )
                process.stdin.flush()
                _append_auto_login_event(
                    events_path,
                    {
                        "kind": "captcha_answer_sent",
                        "attempt": attempt,
                        "image_path": str(image_path),
                        "answer": answer,
                        "expected_length": expected_length,
                    },
                )
                continue

            if kind == "login_succeeded":
                if _storage_state_is_valid(environment_id, state_path):
                    _write_auto_auth_status(
                        environment_id,
                        status="succeeded",
                        message="登录态已自动保存。",
                    )
                    _record_auto_auth_event(
                        environment_id,
                        result="success",
                        summary="环境自动登录成功，登录态已保存",
                    )
                    # 🔧 修复：更新环境的 updated_at 时间
                    _update_environment_timestamp(environment_id)
                    return
                message = "自动登录已完成，但保存出的登录态不可复用。"
                _write_auto_auth_status(
                    environment_id,
                    status="failed",
                    message=message,
                    last_error_code="AUTH_STATE_INVALID",
                )
                _record_auto_auth_event(
                    environment_id,
                    result="failed",
                    summary="环境自动登录失败：登录态不可复用",
                    failure_reason="AUTH_STATE_INVALID",
                    detail=message,
                )
                return

            if kind == "login_plan_saved":
                continue

            if kind == "login_failed":
                reason = str(event.get("reason") or "login_failed")
                message = _failure_message_for_reason(reason)
                _write_auto_auth_status(
                    environment_id,
                    status="failed",
                    message=message,
                    last_error_code=reason.upper(),
                )
                _record_auto_auth_event(
                    environment_id,
                    result="failed",
                    summary="环境自动登录失败",
                    failure_reason=reason.upper(),
                    detail=message,
                )
                return

        return_code = process.wait(timeout=180)
        if return_code == 0 and _storage_state_is_valid(environment_id, state_path):
            _write_auto_auth_status(
                environment_id,
                status="succeeded",
                message="登录态已自动保存。",
            )
            _record_auto_auth_event(
                environment_id,
                result="success",
                summary="环境自动登录成功，登录态已保存",
            )
            # 🔧 修复：更新环境的 updated_at 时间
            _update_environment_timestamp(environment_id)
            return

        message = "自动登录失败，请检查账号密码或站点探索模型配置。"
        _write_auto_auth_status(
            environment_id,
            status="failed",
            message=message,
            last_error_code="AUTO_LOGIN_FAILED",
        )
        _record_auto_auth_event(
            environment_id,
            result="failed",
            summary="环境自动登录失败",
            failure_reason="AUTO_LOGIN_FAILED",
            detail=message,
        )
    except Exception as exc:
        message = "自动登录执行异常，请稍后重试。"
        _write_auto_auth_status(
            environment_id,
            status="failed",
            message=message,
            last_error_code="AUTO_LOGIN_EXCEPTION",
        )
        _record_auto_auth_event(
            environment_id,
            result="failed",
            summary="环境自动登录异常",
            failure_reason="AUTO_LOGIN_EXCEPTION",
            detail=str(exc)[:300],
        )
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def _launch_ai_letter_login_process(
    *,
    site_url: str,
    storage_state_path: Path,
    login_plan_path: Path,
    browser_channel: str,
    credentials: dict,
):
    script_path = PLAYWRIGHT_RUNNER_DIR / "ai-letter-login.mjs"
    env = {
        **os.environ,
        "AI_TESTING_LOGIN_USERNAME": credentials["username"],
        "AI_TESTING_LOGIN_PASSWORD": credentials["password"],
        "AI_TESTING_CAPTCHA_MAX_ATTEMPTS": "3",
        "AI_TESTING_LOGIN_PLAN_PATH": str(login_plan_path),
    }
    return subprocess.Popen(
        ["node", str(script_path), site_url, str(storage_state_path), browser_channel, str(login_plan_path)],
        cwd=PLAYWRIGHT_RUNNER_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        env=env,
    )


def _load_environment(environment_id: str) -> dict:
    with connect() as db:
        environment = environment_repo.find_by_id(db, environment_id)
        if not environment:
            raise ValueError("environment not found")
        return {
            "site_url": environment["site_url"],
            "login_strategy": environment["login_strategy"],
            "captcha_strategy": environment["captcha_strategy"],
            "reuse_auth_state": bool(environment["reuse_auth_state"]),
        }


def _auto_auth_status_path(environment_id: str) -> Path:
    return auth_state_path(environment_id).parent / "auto-login-status.json"


def _append_auto_login_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **event,
    }
    path.write_text("", encoding="utf-8") if not path.exists() else None
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _login_plan_path(environment_id: str) -> Path:
    return auth_state_path(environment_id).parent / "login-plan.json"


def _write_auto_auth_status(
    environment_id: str,
    *,
    status: str,
    message: str,
    last_error_code: str = "",
) -> None:
    path = _auto_auth_status_path(environment_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_error_code": last_error_code,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _storage_state_is_valid(environment_id: str, state_path: Path) -> bool:
    if not state_path.exists():
        return False
    summary = auth_state_summary(
        environment_id=environment_id,
        login_strategy="account_password",
        reuse_auth_state=True,
    )
    return summary["status"] == "valid"


def _failure_message_for_reason(reason: str) -> str:
    mapping = {
        "login_page_not_ready": "登录页未加载完成或页面为空，请稍后重试。",
        "captcha_not_found": "未找到验证码区域，请确认登录页结构。",
        "captcha_answer_missing": "验证码答案缺失，自动登录已中断。",
        "captcha_exhausted": "验证码识别或登录失败，已用尽 3 次重试。",
    }
    return mapping.get(reason, "自动登录失败，请检查账号密码或站点探索模型配置。")


def _safe_expected_captcha_length(value: object) -> int | None:
    try:
        length = int(value)
    except (TypeError, ValueError):
        return None
    return length if 0 < length <= 12 else None


def _record_auto_auth_event(
    environment_id: str,
    *,
    result: str,
    summary: str,
    failure_reason: str = "",
    detail: str = "",
) -> None:
    environment_name = environment_id
    with connect() as db:
        environment = environment_repo.find_by_id(db, environment_id)
        if environment:
            environment_name = environment["name"]
    after = {"environment_id": environment_id, "captcha_strategy": "ai_letter"}
    if detail:
        after["detail"] = detail
    if result == "failed":
        operation_log_service.record_task_event(
            module="environment",
            action="auto_auth_login",
            object_type="exploration_environment",
            object_id=environment_id,
            object_name=environment_name,
            project_id="",
            actor_id="system",
            actor_name="系统",
            result="failed",
            failure_reason=failure_reason or summary,
            summary=summary,
            after=after,
            source="system",
        )
        return
    operation_log_service.record_success(
        log_type="task",
        module="environment",
        action="auto_auth_login",
        object_type="exploration_environment",
        object_id=environment_id,
        object_name=environment_name,
        project_id="",
        actor_id="system",
        actor_name="系统",
        summary=summary,
        after=after,
        source="system",
    )


def _update_environment_timestamp(environment_id: str) -> None:
    """更新环境的 updated_at 时间戳，用于登录成功后刷新列表时间"""
    try:
        with connect() as db:
            environment_repo.update(
                db,
                environment_id,
                assignments=["updated_at = CURRENT_TIMESTAMP"],
                values=[],
            )
            db.commit()
    except Exception:
        # 更新时间戳失败不影响登录流程
        pass
