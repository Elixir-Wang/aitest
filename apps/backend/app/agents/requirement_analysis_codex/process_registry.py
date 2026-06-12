from __future__ import annotations

import os
import signal
import subprocess
import threading

from app.core.db import connect
from app.repositories import requirement_analysis_run_repo

_lock = threading.Lock()
_processes: dict[str, subprocess.Popen] = {}


def register(run_id: str, process: subprocess.Popen) -> None:
    with _lock:
        _processes[run_id] = process


def unregister(run_id: str) -> None:
    with _lock:
        _processes.pop(run_id, None)


def kill_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def terminate(run_id: str) -> bool:
    with _lock:
        process = _processes.get(run_id)
    if process is None or process.poll() is not None:
        return False
    kill_process_tree(process)
    return True


def cancel_requested(run_id: str) -> bool:
    if not run_id:
        return False
    with connect() as db:
        run = requirement_analysis_run_repo.find_run(db, run_id)
    return bool(run and run["status"] == "stopping")
