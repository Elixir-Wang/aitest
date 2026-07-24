from __future__ import annotations

import csv
import json
import os
import re
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
_MONITOR_FINISHED: dict[str, threading.Event] = {}
_PROCESS_LOCK = threading.Lock()


def _control_path(run_dir: Path) -> Path:
    return run_dir / "locust-control.json"


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


def _prune_run_history(db, project_id: str, performance_test_id: str) -> None:
    for run_id in run_repo.prune_run_history(db, project_id, performance_test_id, limit=10):
        shutil.rmtree(_run_dir(project_id, run_id), ignore_errors=True)


def _write_run_files(run_dir: Path, run_id: str, script_code: str, runtime_payload: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "runtime.json").write_text(
        json.dumps({"run_id": run_id, "environment": runtime_payload}, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "generated_locustfile.py").write_text(script_code, encoding="utf-8")
    (run_dir / "locustfile.py").write_text(runtime_locustfile_source(), encoding="utf-8")


def create_run_session(
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
        _prune_run_history(db, project_id, test_id)

    return run_id


def start_headless_run(run_id: str, options: dict[str, Any] | None = None) -> bool:
    with connect() as db:
        run = run_repo.get_run(db, run_id)
    if run is None:
        raise KeyError(f"性能测试运行不存在: {run_id}")
    if run["status"] != "created":
        raise ValueError(f"只有 created 状态的运行可以启动: {run['status']}")
    run_dir = _run_dir(run["project_id"], run_id)
    runtime_path = run_dir / "runtime.json"
    if not (run_dir / "generated_locustfile.py").is_file() or not runtime_path.is_file():
        raise FileNotFoundError(f"性能测试运行产物不存在: {run_id}")
    environment = dict(os.environ)
    environment["AI_TESTING_DB_PATH"] = str(settings.DB_PATH)
    load_config = json.loads(run["load_config_json"] or "{}")
    options = options or {}
    users = int(options.get("users") or load_config.get("users") or 1)
    spawn_rate = float(options.get("spawn_rate") or load_config.get("spawn_rate") or 1)
    duration_seconds = int(options.get("run_time") or load_config.get("measurement_duration_seconds") or 60)
    if users < 1 or spawn_rate <= 0 or duration_seconds < 1:
        raise ValueError("users、spawn_rate 和 run_time 必须为正数。")
    host = str(options.get("host") or "").strip()
    if host:
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        runtime["environment"]["api_base_url"] = host
        runtime_path.write_text(json.dumps(runtime, ensure_ascii=False), encoding="utf-8")
    command = build_headless_command(
        run_dir=run_dir,
        users=users,
        spawn_rate=spawn_rate,
        duration_seconds=duration_seconds,
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
            _prune_run_history(db, run["project_id"], run["performance_test_id"])
        raise

    monitor_finished = threading.Event()
    monitor = threading.Thread(
        target=_monitor_run_guarded,
        args=(run_id, process, stdout_file, stderr_file, run_dir, monitor_finished),
        daemon=True,
    )
    with _PROCESS_LOCK:
        _PROCESSES[run_id] = process
        _MONITOR_FINISHED[run_id] = monitor_finished
    with connect() as db:
        run_repo.update_run_status(db, run_id, "starting")
        run_repo.append_event(db, run_id, "worker_started", "info", "性能测试 Worker 已启动", {"pid": process.pid})
    monitor.start()
    return True


def parse_locust_stats_history(content: str) -> dict[str, Any] | None:
    samples = parse_locust_stats_history_samples(content)
    return samples[-1] if samples else None


def parse_locust_stats_history_samples(content: str) -> list[dict[str, Any]]:
    rows = csv.DictReader(content.splitlines())
    return [
        _locust_history_sample(row)
        for row in rows
        if row.get("Type") == "Aggregated" or row.get("Name") == "Aggregated"
    ]


def _locust_history_sample(aggregate: dict[str, str | None]) -> dict[str, Any]:
    request_count = int(float(aggregate.get("Total Request Count") or aggregate.get("Request Count") or 0))
    failure_count = int(float(aggregate.get("Total Failure Count") or aggregate.get("Failure Count") or 0))
    return {
        "sampled_at": str(aggregate.get("Timestamp") or ""),
        "user_count": int(float(aggregate.get("User Count") or 0)),
        "request_count": request_count,
        "failure_count": failure_count,
        "requests_per_second": float(aggregate.get("Requests/s") or 0),
        "failures_per_second": float(aggregate.get("Failures/s") or 0),
        "failure_rate": failure_count / request_count if request_count else 0,
        "average_response_time_ms": float(aggregate.get("Total Average Response Time") or aggregate.get("Average Response Time") or 0),
        "p50_response_time_ms": _locust_float(aggregate.get("50%")),
        "p95_response_time_ms": _locust_float(aggregate.get("95%")),
        "p99_response_time_ms": _locust_float(aggregate.get("99%")),
        "source": "locust_csv_history",
    }


def _locust_float(value: object) -> float:
    if value in (None, "", "N/A"):
        return 0.0
    return float(value)


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


def _normalize_failure_reason(reason: str) -> str:
    match = re.fullmatch(r"CatchResponseError\((['\"])(.*)\1\)", reason.strip())
    return match.group(2) if match else reason.strip()


def _failure_status_code(reason: str) -> int | None:
    match = re.search(r"status code:\s*(\d{3})", reason)
    return int(match.group(1)) if match else None


def _collect_locust_results(db, run_id: str, run_dir: Path) -> None:
    run = run_repo.get_run(db, run_id)
    load_config = json.loads(run["load_config_json"] or "{}") if run else {}
    configured_users = int(load_config.get("users") or 0)
    stats_path = run_dir / "result_stats.csv"
    if stats_path.exists():
        with stats_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        aggregate = next((row for row in reversed(rows) if row.get("Type") == "Aggregated"), rows[-1] if rows else None)
        if aggregate:
            request_count = int(float(aggregate.get("Request Count") or 0))
            failure_count = int(float(aggregate.get("Failure Count") or 0))
            run_repo.append_stats(db, run_id=run_id, sample={
                "user_count": configured_users,
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
    run_repo.clear_failure_details(db, run_id)
    locust_events = _read_locust_events(run_dir / "locust-events.jsonl")
    imported_failures = False
    failures_path = run_dir / "result_failures.csv"
    if failures_path.exists():
        with failures_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                imported_failures = True
                reason = _normalize_failure_reason(str(row.get("Error") or ""))
                event = _matching_failure_event(
                    locust_events,
                    method=str(row.get("Method") or ""),
                    name=str(row.get("Name") or ""),
                    reason=reason,
                )
                status_code = _failure_status_code(reason)
                if status_code is None and event and event.get("status_code"):
                    status_code = int(event["status_code"])
                run_repo.upsert_failure(
                    db,
                    run_id=run_id,
                    request_name=str(row.get("Name") or ""),
                    method=str(row.get("Method") or ""),
                    reason=reason,
                    count=int(float(row.get("Occurrences") or 1)),
                    status_code=status_code,
                    response_excerpt=str(event.get("response_excerpt") or "") if event else "",
                )
    imported_exceptions = False
    exceptions_path = run_dir / "result_exceptions.csv"
    if exceptions_path.exists():
        with exceptions_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                imported_exceptions = True
                message = str(row.get("Message") or "")
                run_repo.upsert_exception(
                    db,
                    run_id=run_id,
                    request_name="",
                    exception_type=message.partition(":")[0] or "Exception",
                    message=message,
                    count=int(float(row.get("Count") or 1)),
                )
    if locust_events:
        for event in locust_events:
            if event.get("kind") == "failure" and not imported_failures:
                run_repo.upsert_failure(
                    db,
                    run_id=run_id,
                    request_name=str(event.get("name") or ""),
                    method=str(event.get("request_type") or ""),
                    reason=_normalize_failure_reason(str(event.get("reason") or "HTTP failure")),
                    status_code=int(event["status_code"]) if event.get("status_code") else None,
                    response_excerpt=str(event.get("response_excerpt") or ""),
                )
            elif event.get("kind") == "exception" and not imported_exceptions:
                run_repo.upsert_exception(
                    db,
                    run_id=run_id,
                    request_name=str(event.get("name") or ""),
                    exception_type=str(event.get("exception_type") or "Exception"),
                    message=str(event.get("message") or "")[:2000],
                )
    run_repo.set_report_directory(db, run_id, str(run_dir))


def _read_locust_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _matching_failure_event(
    events: list[dict[str, Any]],
    *,
    method: str,
    name: str,
    reason: str,
) -> dict[str, Any] | None:
    exact = next(
        (
            event
            for event in events
            if event.get("kind") == "failure"
            and str(event.get("request_type") or "") == method
            and str(event.get("name") or "") == name
            and _normalize_failure_reason(str(event.get("reason") or "")) == reason
        ),
        None,
    )
    if exact:
        return exact
    return next(
        (
            event
            for event in events
            if event.get("kind") == "failure"
            and str(event.get("request_type") or "") == method
            and str(event.get("name") or "") == name
        ),
        None,
    )


def _monitor_run_guarded(
    run_id: str,
    process: subprocess.Popen,
    stdout_file,
    stderr_file,
    run_dir: Path,
    finished: threading.Event,
) -> None:
    try:
        _monitor_run(run_id, process, stdout_file, stderr_file, run_dir)
    finally:
        finished.set()
        with _PROCESS_LOCK:
            if _MONITOR_FINISHED.get(run_id) is finished:
                _MONITOR_FINISHED.pop(run_id, None)


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
            if current and current["status"] in {"starting", "running"}:
                run_repo.touch_run(db, run_id)
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
        current = run_repo.get_run(db, run_id)
        if current:
            _prune_run_history(db, current["project_id"], current["performance_test_id"])


def stop_headless_run(run_id: str) -> bool:
    with _PROCESS_LOCK:
        process = _PROCESSES.get(run_id)
        if process is None:
            return False
        _STOP_REQUESTED.add(run_id)
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
    return True


def stop_headless_run_and_wait(run_id: str, *, timeout: float = 15.0) -> bool:
    with _PROCESS_LOCK:
        finished = _MONITOR_FINISHED.get(run_id)
    stop_headless_run(run_id)
    if finished is None:
        return True
    return finished.wait(timeout)


def reset_headless_stats(run_id: str) -> bool:
    with connect() as db:
        run = run_repo.get_run(db, run_id)
    if run is None:
        raise KeyError(f"性能测试运行不存在: {run_id}")
    run_dir = _run_dir(run["project_id"], run_id)
    with _PROCESS_LOCK:
        process = _PROCESSES.get(run_id)
    if process is not None and process.poll() is None:
        _control_path(run_dir).write_text(
            json.dumps({"id": secrets.token_hex(8), "action": "reset_stats"}),
            encoding="utf-8",
        )
        events_path = run_dir / "locust-events.jsonl"
        events_path.write_text("", encoding="utf-8")
        return True
    for name in ("result_stats.csv", "result_stats_history.csv", "result_failures.csv", "result_exceptions.csv", "result.html"):
        try:
            (run_dir / name).unlink()
        except FileNotFoundError:
            pass
    return False
