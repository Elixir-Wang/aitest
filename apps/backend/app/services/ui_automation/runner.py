from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import shutil
import threading
import time
from pathlib import Path

from . import execution_events, live_view


_PROCESSES: dict[str, subprocess.Popen[str]] = {}
_STOP_REQUESTED: set[str] = set()
_PROCESS_LOCK = threading.Lock()


SENSITIVE_RE = re.compile(
    r"(?i)(authorization:\s*bearer\s+|token=|password=|cookie:\s*)([^\s]+)"
)


def run_case(
    *,
    run_id: str,
    suite_path: Path,
    run_dir: Path,
    pytest_node_id: str,
    environment: dict,
    parameter_names: list[str] | None = None,
    timeout: int = 600,
) -> dict:
    suite_path = suite_path.resolve()
    run_dir = run_dir.resolve()
    suite_path.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    browser_output = run_dir / "browser"
    browser_output.mkdir(parents=True, exist_ok=True)

    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    result_path = run_dir / "result.json"
    events_path = run_dir / "events.jsonl"
    detail_path = run_dir / "result-detail.json"
    step_artifact_dir = run_dir / "step-artifacts"
    process_env = _build_environment(environment, result_path)
    process_env["UI_ARTIFACT_DIR"] = str(browser_output)
    process_env["UI_RUN_ID"] = run_id
    process_env["UI_RUN_DIR"] = str(run_dir)
    process_env["UI_RUN_EVENT_PATH"] = str(events_path)
    process_env["UI_RUN_ARTIFACT_DIR"] = str(step_artifact_dir)
    process_env["UI_BUSINESS_PARAMETERS"] = json.dumps(parameter_names or [], ensure_ascii=False)
    process_env["UI_RUNNER_PARENT_PID"] = str(os.getpid())
    process_env["UI_VIEWPORT_WIDTH"] = str(live_view.VIEWPORT_WIDTH)
    process_env["UI_VIEWPORT_HEIGHT"] = str(live_view.VIEWPORT_HEIGHT)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "app.services.ui_automation.live_pytest_plugin",
        f"--output={browser_output}",
        pytest_node_id,
    ]
    live_session = live_view.start_session(run_id)
    backend_root = str(Path(__file__).resolve().parents[3])
    existing_pythonpath = process_env.get("PYTHONPATH", "")
    process_env["PYTHONPATH"] = os.pathsep.join(filter(None, [backend_root, existing_pythonpath]))
    if live_session.cdp_port is not None:
        process_env["UI_LIVE_CDP_PORT"] = str(live_session.cdp_port)
    if os.getenv("UI_HEADED", "0").lower() in {"1", "true", "yes", "on"}:
        command.insert(-1, "--headed")
        xvfb_run = shutil.which("xvfb-run")
        if xvfb_run and not process_env.get("DISPLAY"):
            screen = f"{live_view.VIEWPORT_WIDTH}x{live_view.VIEWPORT_HEIGHT}x24"
            command = [xvfb_run, "--auto-servernum", f"--server-args=-screen 0 {screen}", *command]
    process: subprocess.Popen[str] | None = None
    timed_out = False
    try:
        process = subprocess.Popen(
            command,
            cwd=suite_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=process_env,
            start_new_session=os.name != "nt",
        )
        with _PROCESS_LOCK:
            _PROCESSES[run_id] = process
            stop_requested = run_id in _STOP_REQUESTED
        if stop_requested:
            _terminate_process(process)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_process(process, force=True)
            stdout, stderr = process.communicate()
    finally:
        with _PROCESS_LOCK:
            _PROCESSES.pop(run_id, None)
            stop_requested = run_id in _STOP_REQUESTED
            _STOP_REQUESTED.discard(run_id)
        live_view.finish_session(run_id)
    stdout_path.write_text(_redact(stdout), encoding="utf-8")
    stderr_path.write_text(_redact(stderr), encoding="utf-8")
    status = "cancelled" if stop_requested else "passed" if process.returncode == 0 else "failed"
    result = {
        "run_id": run_id,
        "status": status,
        "exitcode": process.returncode,
        "pytest_node_id": pytest_node_id,
    }
    if timed_out:
        result["error_message"] = f"UI 自动化执行超过 {timeout} 秒，已终止。"
    detail = execution_events.build_detail(events_path, run_id=run_id, run_status=status)
    result["detail_available"] = detail["detail_available"]
    result["detail_summary"] = detail["summary"]
    if events_path.exists():
        execution_events.write_detail(detail_path, detail)
        result["detail_path"] = str(detail_path)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    screenshots = sorted(browser_output.rglob("*.png"))
    return {
        **result,
        "result_path": str(result_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "screenshot_paths": [str(path) for path in screenshots],
        "events_path": str(events_path) if events_path.exists() else "",
        "detail_path": str(detail_path) if detail_path.exists() else "",
    }


def request_stop(run_id: str) -> bool:
    with _PROCESS_LOCK:
        _STOP_REQUESTED.add(run_id)
        process = _PROCESSES.get(run_id)
    if process is not None and process.poll() is None:
        _terminate_process(process)
        threading.Thread(target=_force_kill_after_grace, args=(process,), daemon=True).start()
    return process is not None


def clear_stop_request(run_id: str) -> None:
    with _PROCESS_LOCK:
        _STOP_REQUESTED.discard(run_id)


def shutdown_all(*, grace_seconds: float = 3) -> None:
    """Stop every pytest process owned by this backend process."""
    with _PROCESS_LOCK:
        processes = list(_PROCESSES.items())
        _STOP_REQUESTED.update(run_id for run_id, _ in processes)

    for _, process in processes:
        _terminate_process(process)

    deadline = time.monotonic() + max(grace_seconds, 0)
    for _, process in processes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            break

    for _, process in processes:
        if process.poll() is None:
            _terminate_process(process, force=True)


def _terminate_process(process: subprocess.Popen[str], *, force: bool = False) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name != "nt":
            os.killpg(os.getpgid(process.pid), signal.SIGKILL if force else signal.SIGTERM)
        elif force:
            process.kill()
        else:
            process.terminate()
    except (OSError, ProcessLookupError):
        if process.poll() is None:
            process.kill() if force else process.terminate()


def _force_kill_after_grace(process: subprocess.Popen[str]) -> None:
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        _terminate_process(process, force=True)


def _build_environment(environment: dict, result_path: Path) -> dict[str, str]:
    process_env = dict(os.environ)
    process_env.pop("VIRTUAL_ENV", None)
    process_env["UI_BASE_URL"] = str(environment.get("site_url", "")).rstrip("/")
    process_env["UI_RESULT_PATH"] = str(result_path)
    storage_state = str(environment.get("storage_state_path", "")).strip()
    if storage_state:
        process_env["UI_STORAGE_STATE"] = storage_state
    return process_env


def _redact(value: str) -> str:
    return SENSITIVE_RE.sub(lambda match: f"{match.group(1)}***", value or "")


__all__ = ["clear_stop_request", "request_stop", "run_case", "shutdown_all"]
