from __future__ import annotations

import csv
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from app.core import settings
from app.core.db import connect
from app.services.performance_testing import run_repo
from app.services.performance_testing.locust_runtime import runtime_locustfile_source


_PROCESSES: dict[str, subprocess.Popen] = {}
_STOP_REQUESTED: set[str] = set()
_PROCESS_LOCK = threading.Lock()


def build_headless_command(*, run_dir: Path, users: int, spawn_rate: float, duration_seconds: int) -> list[str]:
    csv_prefix = run_dir / "result"
    return [
        sys.executable,
        "-m",
        "locust",
        "-f",
        "locustfile.py",
        "--headless",
        "--users",
        str(users),
        "--spawn-rate",
        str(spawn_rate),
        "--run-time",
        f"{duration_seconds}s",
        "--csv",
        str(csv_prefix),
        "--csv-full-history",
        "--html",
        str(run_dir / "result.html"),
    ]


def _run_dir(project_id: str, run_id: str) -> Path:
    return settings.PROJECT_FILE_STORAGE_ROOT / project_id / "performance_testing" / "runs" / run_id


def _write_run_files(run_dir: Path, run_id: str, script_code: str, runtime_payload: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "runtime.json").write_text(
        json.dumps({"run_id": run_id, "environment": runtime_payload}, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "generated_locustfile.py").write_text(script_code, encoding="utf-8")
    (run_dir / "locustfile.py").write_text(runtime_locustfile_source(), encoding="utf-8")


def start_headless_run(
    *,
    project_id: str,
    test_id: str,
    script_id: str,
    script_code: str,
    runtime_payload: dict[str, Any],
    load_config: dict[str, Any],
    created_by: str,
) -> str:
    run_id = f"perfrun-{secrets.token_hex(8)}"
    run_dir = _run_dir(project_id, run_id)
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
    _write_run_files(run_dir, run_id, script_code, runtime_payload)
    with connect() as db:
        run_repo.create_run(
            db,
            run_id=run_id,
            project_id=project_id,
            performance_test_id=test_id,
            script_id=script_id,
            load_config=load_config,
            runtime_config=runtime_payload,
            created_by=created_by,
        )
        run_repo.append_event(db, run_id, "run_created", "info", "已创建性能测试运行", {})

    environment = dict(os.environ)
    environment["AI_TESTING_DB_PATH"] = str(settings.DB_PATH)
    command = build_headless_command(
        run_dir=run_dir,
        users=int(load_config.get("users") or 1),
        spawn_rate=float(load_config.get("spawn_rate") or 1),
        duration_seconds=int(load_config.get("measurement_duration_seconds") or 60),
    )
    stdout_file = (run_dir / "stdout.log").open("w", encoding="utf-8")
    stderr_file = (run_dir / "stderr.log").open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            command,
            cwd=run_dir,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except Exception as exc:
        stdout_file.close()
        stderr_file.close()
        with connect() as db:
            run_repo.update_run_status(db, run_id, "starting", error_code="PERFORMANCE_RUN_START_FAILED", error_message=str(exc))
            run_repo.update_run_status(db, run_id, "failed", error_code="PERFORMANCE_RUN_START_FAILED", error_message=str(exc))
        raise

    with _PROCESS_LOCK:
        _PROCESSES[run_id] = process
    with connect() as db:
        run_repo.update_run_status(db, run_id, "starting")
        run_repo.append_event(db, run_id, "worker_started", "info", "性能测试 Worker 已启动", {"pid": process.pid})
    threading.Thread(target=_monitor_run, args=(run_id, process, stdout_file, stderr_file, run_dir), daemon=True).start()
    return run_id


def parse_locust_stats_history(content: str) -> dict[str, Any] | None:
    rows = list(csv.DictReader(content.splitlines()))
    aggregate = next((row for row in reversed(rows) if row.get("Type") == "Aggregated"), None)
    if not aggregate:
        return None
    request_count = int(float(aggregate.get("Total Request Count") or aggregate.get("Request Count") or 0))
    failure_count = int(float(aggregate.get("Total Failure Count") or aggregate.get("Failure Count") or 0))
    return {
        "sampled_at": str(aggregate.get("Timestamp") or ""),
        "user_count": int(float(aggregate.get("User Count") or 0)),
        "request_count": request_count,
        "failure_count": failure_count,
        "requests_per_second": float(aggregate.get("Requests/s") or 0),
        "failure_rate": failure_count / request_count if request_count else 0,
        "average_response_time_ms": float(aggregate.get("Total Average Response Time") or aggregate.get("Average Response Time") or 0),
        "p50_response_time_ms": float(aggregate.get("50%") or 0),
        "p95_response_time_ms": float(aggregate.get("95%") or 0),
        "p99_response_time_ms": float(aggregate.get("99%") or 0),
        "source": "locust_csv_history",
    }


def _read_history_sample(run_dir: Path) -> dict[str, Any] | None:
    history_path = run_dir / "result_stats_history.csv"
    if not history_path.exists():
        return None
    try:
        return parse_locust_stats_history(history_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError):
        return None


def _persist_realtime_sample(db, run_id: str, run_dir: Path, last_sampled_at: str) -> str:
    sample = _read_history_sample(run_dir)
    if not sample or not sample["sampled_at"] or sample["sampled_at"] == last_sampled_at:
        return last_sampled_at
    run_repo.append_stats(db, run_id=run_id, sample=sample)
    return str(sample["sampled_at"])


def _collect_locust_results(db, run_id: str, run_dir: Path) -> None:
    stats_path = run_dir / "result_stats.csv"
    if stats_path.exists():
        with stats_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        aggregate = next((row for row in reversed(rows) if row.get("Type") == "Aggregated"), rows[-1] if rows else None)
        if aggregate:
            request_count = int(float(aggregate.get("Request Count") or 0))
            failure_count = int(float(aggregate.get("Failure Count") or 0))
            run_repo.append_stats(db, run_id=run_id, sample={
                "user_count": 0,
                "request_count": request_count,
                "failure_count": failure_count,
                "requests_per_second": float(aggregate.get("Requests/s") or 0),
                "failure_rate": failure_count / request_count if request_count else 0,
                "average_response_time_ms": float(aggregate.get("Average Response Time") or 0),
                "p50_response_time_ms": float(aggregate.get("50%") or 0),
                "p95_response_time_ms": float(aggregate.get("95%") or 0),
                "p99_response_time_ms": float(aggregate.get("99%") or 0),
                "source": "locust_csv",
            })
    failures_path = run_dir / "result_failures.csv"
    if failures_path.exists():
        with failures_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                run_repo.upsert_failure(
                    db,
                    run_id=run_id,
                    request_name=str(row.get("Name") or ""),
                    method=str(row.get("Method") or ""),
                    reason=str(row.get("Error") or ""),
                )
    run_repo.set_report_directory(db, run_id, str(run_dir))


def _monitor_run(
    run_id: str,
    process: subprocess.Popen,
    stdout_file,
    stderr_file,
    run_dir: Path,
) -> None:
    last_sampled_at = ""
    while process.poll() is None:
        with connect() as db:
            last_sampled_at = _persist_realtime_sample(db, run_id, run_dir, last_sampled_at)
            current = run_repo.get_run(db, run_id)
            if current and current["status"] == "starting":
                run_repo.update_run_status(db, run_id, "running")
        threading.Event().wait(1)

    return_code = process.wait()
    stdout_file.close()
    stderr_file.close()
    with _PROCESS_LOCK:
        stopped = run_id in _STOP_REQUESTED
        _PROCESSES.pop(run_id, None)
        _STOP_REQUESTED.discard(run_id)
    with connect() as db:
        _persist_realtime_sample(db, run_id, run_dir, last_sampled_at)
        _collect_locust_results(db, run_id, run_dir)
        if stopped:
            current = run_repo.get_run(db, run_id)
            if current and current["status"] in {"starting", "running"}:
                run_repo.update_run_status(db, run_id, "stopping")
            run_repo.update_run_status(db, run_id, "stopped")
            message = "性能测试已停止"
        elif return_code == 0:
            current = run_repo.get_run(db, run_id)
            if current and current["status"] == "starting":
                run_repo.update_run_status(db, run_id, "running")
            run_repo.update_run_status(db, run_id, "completed")
            message = "性能测试已完成"
        else:
            current = run_repo.get_run(db, run_id)
            if current and current["status"] in {"starting", "running"}:
                run_repo.update_run_status(
                    db,
                    run_id,
                    "failed",
                    error_code="PERFORMANCE_RUN_FAILED",
                    error_message=f"Locust 退出码: {return_code}",
                )
            message = "性能测试失败"
        run_repo.append_event(db, run_id, "run_finished", "info" if return_code == 0 else "error", message, {"return_code": return_code})


def stop_headless_run(run_id: str) -> bool:
    with _PROCESS_LOCK:
        process = _PROCESSES.get(run_id)
        if process is None:
            return False
        _STOP_REQUESTED.add(run_id)
    process.terminate()
    return True
