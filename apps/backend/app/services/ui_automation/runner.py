from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import shutil
from pathlib import Path

from . import live_view


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
    process_env = _build_environment(environment, result_path)
    process_env["UI_ARTIFACT_DIR"] = str(browser_output)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--tracing=retain-on-failure",
        "--video=on",
        f"--output={browser_output}",
        pytest_node_id,
    ]
    live_session = live_view.start_session(run_id)
    if live_session.status == "ready":
        process_env["DISPLAY"] = live_session.display
        command.insert(4, "--headed")
    elif os.getenv("UI_HEADED", "0").lower() in {"1", "true", "yes", "on"}:
        command.insert(4, "--headed")
        xvfb_run = shutil.which("xvfb-run")
        if xvfb_run and not process_env.get("DISPLAY"):
            command = [xvfb_run, "--auto-servernum", "--server-args=-screen 0 1440x900x24", *command]
    try:
        completed = subprocess.run(
            command,
            cwd=suite_path,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=process_env,
        )
    finally:
        live_view.finish_session(run_id)
    stdout_path.write_text(_redact(completed.stdout), encoding="utf-8")
    stderr_path.write_text(_redact(completed.stderr), encoding="utf-8")
    status = "passed" if completed.returncode == 0 else "failed"
    result = {
        "run_id": run_id,
        "status": status,
        "exitcode": completed.returncode,
        "pytest_node_id": pytest_node_id,
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    traces = sorted(browser_output.rglob("trace.zip"))
    screenshots = sorted(browser_output.rglob("*.png"))
    videos = sorted(browser_output.rglob("*.webm")) + sorted(browser_output.rglob("*.mp4"))
    return {
        **result,
        "result_path": str(result_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "trace_path": str(traces[0]) if traces else "",
        "screenshot_paths": [str(path) for path in screenshots],
        "video_path": str(videos[0]) if videos else "",
    }


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


__all__ = ["run_case"]
