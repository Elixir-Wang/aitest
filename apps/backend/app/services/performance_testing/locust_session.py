"""In-memory Locust session registry.

Runs are not persisted to the database. Each Locust process is registered in a
project-scoped JSON file so the reverse proxy can locate the loopback port by
run_id. Entries are pruned on read whenever their PID is no longer alive.
"""

from __future__ import annotations

import json
import secrets
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from app.core import settings
from app.core.exceptions import api_error
from app.services.performance_testing.runner import (
    allocate_loopback_port,
    launch_locust_web_process,
    terminate_process,
)


_LOCK = threading.Lock()


@dataclass(frozen=True)
class LocustSession:
    run_id: str
    process_id: int
    port: int
    base_path: str
    run_dir: Path


def _session_file(project_id: str) -> Path:
    root = settings.PROJECT_FILE_STORAGE_ROOT / project_id / "performance_testing"
    root.mkdir(parents=True, exist_ok=True)
    return root / "active_sessions.json"


def _load_sessions(project_id: str) -> dict[str, dict[str, Any]]:
    path = _session_file(project_id)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items() if isinstance(value, dict)}


def _prune_dead(sessions: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    alive: dict[str, dict[str, Any]] = {}
    for key, value in sessions.items():
        pid = int(value.get("process_id") or 0)
        if pid and psutil.pid_exists(pid):
            alive[key] = value
        elif pid:
            run_dir_raw = str(value.get("run_dir") or "")
            if run_dir_raw:
                shutil.rmtree(run_dir_raw, ignore_errors=True)
    return alive


def _persist(project_id: str, sessions: dict[str, dict[str, Any]]) -> None:
    path = _session_file(project_id)
    path.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_dir(project_id: str, run_id: str) -> Path:
    return settings.PROJECT_FILE_STORAGE_ROOT / project_id / "performance_testing" / "runs" / run_id


def start_session(
    project_id: str,
    test_id: str,
    script_id: str,
    *,
    script_code: str,
    runtime_payload: dict[str, Any],
) -> LocustSession:
    run_id = f"perfrun-{secrets.token_hex(8)}"
    run_dir = _run_dir(project_id, run_id)

    # 清理可能存在的残留目录，确保干净启动
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        (run_dir / "runtime.json").write_text(
            json.dumps({"run_id": run_id, "environment": runtime_payload}, ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "generated_locustfile.py").write_text(script_code, encoding="utf-8")
        (run_dir / "locustfile.py").write_text(_runtime_locustfile_source(), encoding="utf-8")

        port = allocate_loopback_port()
        base_path = f"/api/v1/projects/{project_id}/performance-test-runs/{run_id}/locust-ui"
        process_id = launch_locust_web_process(run_dir, port=port, base_path=base_path)
        snapshot = {
            "run_id": run_id,
            "project_id": project_id,
            "test_id": test_id,
            "script_id": script_id,
        }
        (run_dir / "snapshot.json").write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        # 启动失败时清理残留文件
        shutil.rmtree(run_dir, ignore_errors=True)
        raise api_error(500, "LOCUST_SESSION_START_FAILED", f"Locust 会话启动失败: {exc}") from exc

    session = LocustSession(
        run_id=run_id,
        process_id=process_id,
        port=port,
        base_path=base_path,
        run_dir=run_dir,
    )
    with _LOCK:
        sessions = _prune_dead(_load_sessions(project_id))
        sessions[run_id] = {
            "process_id": process_id,
            "port": port,
            "base_path": base_path,
            "run_dir": str(run_dir),
            "test_id": test_id,
            "script_id": script_id,
        }
        _persist(project_id, sessions)
    return session


def require_session(project_id: str, run_id: str) -> LocustSession:
    with _LOCK:
        sessions = _prune_dead(_load_sessions(project_id))
        if run_id not in sessions:
            _persist(project_id, sessions)
            raise api_error(404, "PERFORMANCE_RUN_NOT_FOUND", "Locust 会话不存在或已结束。")
        raw = sessions[run_id]
        _persist(project_id, sessions)
        return LocustSession(
            run_id=run_id,
            process_id=int(raw["process_id"]),
            port=int(raw["port"]),
            base_path=str(raw["base_path"]),
            run_dir=Path(str(raw["run_dir"])),
        )


def build_proxy_target(session: LocustSession, path: str) -> str:
    suffix = path.lstrip("/")
    base = session.base_path.rstrip("/")
    return f"http://127.0.0.1:{session.port}{base}{'/' + suffix if suffix else ''}"


def stop_session(project_id: str, run_id: str) -> None:
    with _LOCK:
        sessions = _prune_dead(_load_sessions(project_id))
        raw = sessions.pop(run_id, None)
        _persist(project_id, sessions)
    if not raw:
        return
    pid = int(raw.get("process_id") or 0)
    if pid:
        try:
            terminate_process(pid)
        except (OSError, ProcessLookupError):
            pass
    run_dir_raw = str(raw.get("run_dir") or "")
    if run_dir_raw:
        shutil.rmtree(run_dir_raw, ignore_errors=True)


def _runtime_locustfile_source() -> str:
    return '''import json
from pathlib import Path

from generated_locustfile import *


RUNTIME = json.loads(Path(__file__).with_name("runtime.json").read_text(encoding="utf-8"))
PLAN["request"]["headers"] = {
    **dict(RUNTIME["environment"].get("headers") or {}),
    **dict(PLAN["request"].get("headers") or {}),
}
PerformanceUser.host = RUNTIME["environment"]["api_base_url"]
'''
