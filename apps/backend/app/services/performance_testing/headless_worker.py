from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
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
from app.services.performance_testing.script_renderer import runtime_module_source


_PROCESSES: dict[str, subprocess.Popen] = {}
_STOP_REQUESTED: set[str] = set()
_MONITOR_FINISHED: dict[str, threading.Event] = {}
_STOP_TIMEOUTS: dict[str, float] = {}
_PROCESS_LOCK = threading.Lock()
GRACEFUL_STOP_BUFFER_SECONDS = 5


def _control_path(run_dir: Path) -> Path:
    return run_dir / "locust-control.json"


def build_headless_command(
    *,
    run_dir: Path,
    users: int,
    spawn_rate: float,
    duration_seconds: int,
    stop_timeout_seconds: int = GRACEFUL_STOP_BUFFER_SECONDS,
) -> list[str]:
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
        "--stop-timeout",
        str(stop_timeout_seconds),
        "--csv",
        str(csv_prefix),
        "--csv-full-history",
        "--html",
        str(run_dir / "result.html"),
    ]


def _generated_plan(script_code: str) -> dict[str, Any]:
    try:
        tree = ast.parse(script_code)
    except SyntaxError:
        return {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "PLAN" for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Call) or not node.value.args:
            return {}
        try:
            payload = ast.literal_eval(node.value.args[0])
            plan = json.loads(payload)
        except (ValueError, TypeError, json.JSONDecodeError):
            return {}
        return plan if isinstance(plan, dict) else {}
    return {}


def _request_stop_budget(request: Any) -> float:
    if not isinstance(request, dict):
        return 0
    request_timeout = max(0.0, float(request.get("timeout_seconds") or 0))
    if request.get("transport") != "sse":
        return request_timeout
    sse = request.get("sse") if isinstance(request.get("sse"), dict) else {}
    return max(request_timeout, max(0.0, float(sse.get("max_stream_seconds") or 0)))


def graceful_stop_timeout_seconds(script_code: str) -> int:
    plan = _generated_plan(script_code)
    if plan.get("target_type") == "scenario":
        task_budget = 0.0
        for step in plan.get("steps") if isinstance(plan.get("steps"), list) else []:
            if not isinstance(step, dict):
                continue
            if step.get("step_type") == "wait":
                control = step.get("control_config") if isinstance(step.get("control_config"), dict) else {}
                task_budget += max(0.0, float(control.get("duration_ms") or 0)) / 1000
            else:
                task_budget += _request_stop_budget(step.get("request"))
    else:
        task_budget = _request_stop_budget(plan.get("request"))
    return max(GRACEFUL_STOP_BUFFER_SECONDS, math.ceil(task_budget + GRACEFUL_STOP_BUFFER_SECONDS))


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
    (run_dir / "scenario_runtime.py").write_text(runtime_module_source(), encoding="utf-8")
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
    script_code = (run_dir / "generated_locustfile.py").read_text(encoding="utf-8")
    stop_timeout_seconds = graceful_stop_timeout_seconds(script_code)
    command = build_headless_command(
        run_dir=run_dir,
        users=users,
        spawn_rate=spawn_rate,
        duration_seconds=duration_seconds,
        stop_timeout_seconds=stop_timeout_seconds,
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
        _STOP_TIMEOUTS[run_id] = stop_timeout_seconds
    with connect() as db:
        run_repo.update_run_status(db, run_id, "starting")
        run_repo.append_event(db, run_id, "worker_started", "info", "性能测试 Worker 已启动", {"pid": process.pid})
    monitor.start()
    return True


def parse_locust_stats_history(content: str, *, request_type: str | None = None) -> dict[str, Any] | None:
    samples = parse_locust_stats_history_samples(content, request_type=request_type)
    return samples[-1] if samples else None


def parse_locust_stats_history_samples(content: str, *, request_type: str | None = None) -> list[dict[str, Any]]:
    rows = csv.DictReader(content.splitlines())
    return [
        _locust_history_sample(row)
        for row in rows
        if _is_summary_row(row, request_type)
    ]


def parse_locust_stats_csv(
    content: str,
    *,
    user_count: int = 0,
    request_type: str | None = None,
    final_stats: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Parse the current aggregate row from Locust's non-history CSV output."""
    rows = list(csv.DictReader(content.splitlines()))
    aggregate = next(
        (row for row in reversed(rows) if _is_summary_row(row, request_type)),
        None,
    )
    if not aggregate:
        return None
    request_count = int(float(aggregate.get("Total Request Count") or aggregate.get("Request Count") or 0))
    failure_count = int(float(aggregate.get("Total Failure Count") or aggregate.get("Failure Count") or 0))
    if request_type is not None:
        final_entry = next(
            (
                entry
                for entry in (final_stats or {}).get("entries", [])
                if entry.get("request_type") == request_type
            ),
            None,
        )
        if final_entry:
            request_count = int(final_entry.get("request_count") or 0)
            failure_count = int(final_entry.get("failure_count") or 0)
    return {
        "sampled_at": "",
        "user_count": user_count,
        "request_count": request_count,
        "failure_count": failure_count,
        "requests_per_second": float(aggregate.get("Requests/s") or 0),
        "failures_per_second": float(aggregate.get("Failures/s") or 0),
        "failure_rate": failure_count / request_count if request_count else 0,
        "average_response_time_ms": float(aggregate.get("Average Response Time") or 0),
        "p50_response_time_ms": _locust_float(aggregate.get("50%") or aggregate.get("Median Response Time")),
        "p95_response_time_ms": _locust_float(aggregate.get("95%")),
        "p99_response_time_ms": _locust_float(aggregate.get("99%")),
        "source": "locust_csv_live",
    }


def read_realtime_sample(
    run_dir: Path,
    *,
    configured_users: int = 0,
    request_type: str | None = None,
) -> dict[str, Any] | None:
    """Read the newest aggregate metrics, tolerating Locust while flushing CSV files."""
    stats_path = run_dir / "result_stats.csv"
    if not stats_path.exists():
        return None
    try:
        sampled_at = str(stats_path.stat().st_mtime)
        sample = parse_locust_stats_csv(
            stats_path.read_text(encoding="utf-8-sig"),
            user_count=configured_users,
            request_type=request_type,
            final_stats=read_locust_final_stats(run_dir),
        )
        history_sample = _read_history_sample(run_dir, request_type=request_type)
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if sample is None:
        return None
    if history_sample:
        sample["user_count"] = history_sample["user_count"]
    sample["sampled_at"] = sampled_at
    return sample


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


def _is_summary_row(row: dict[str, str | None], request_type: str | None) -> bool:
    if request_type is not None:
        return row.get("Type") == request_type
    return row.get("Type") == "Aggregated" or row.get("Name") == "Aggregated"


def _locust_float(value: object) -> float:
    if value in (None, "", "N/A"):
        return 0.0
    return float(value)


def read_locust_final_stats(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "locust-final-stats.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_history_sample(run_dir: Path, *, request_type: str | None = None) -> dict[str, Any] | None:
    history_path = run_dir / "result_stats_history.csv"
    if not history_path.exists():
        return None
    try:
        return parse_locust_stats_history(
            history_path.read_text(encoding="utf-8-sig"),
            request_type=request_type,
        )
    except (OSError, UnicodeDecodeError):
        return None


def _persist_realtime_sample(
    db,
    run_id: str,
    run_dir: Path,
    last_sampled_at: str,
    last_file_mtime_ns: int = 0,
) -> tuple[str, int]:
    history_path = run_dir / "result_stats_history.csv"
    try:
        file_mtime_ns = history_path.stat().st_mtime_ns
    except OSError:
        return last_sampled_at, last_file_mtime_ns
    if file_mtime_ns == last_file_mtime_ns:
        return last_sampled_at, last_file_mtime_ns
    sample = _read_history_sample(run_dir)
    if not sample or not sample["sampled_at"] or sample["sampled_at"] == last_sampled_at:
        return last_sampled_at, file_mtime_ns
    run_repo.append_stats(db, run_id=run_id, sample=sample)
    return str(sample["sampled_at"]), file_mtime_ns


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
    test = db.execute(
        "SELECT target_type FROM performance_tests WHERE id = ?",
        (run["performance_test_id"],),
    ).fetchone() if run else None
    request_type = "SCENARIO" if test and test["target_type"] == "scenario" else None
    stats_path = run_dir / "result_stats.csv"
    if stats_path.exists():
        with stats_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        aggregate = next(
            (row for row in reversed(rows) if _is_summary_row(row, request_type)),
            rows[-1] if rows else None,
        )
        if aggregate:
            request_count = int(float(aggregate.get("Request Count") or 0))
            failure_count = int(float(aggregate.get("Failure Count") or 0))
            final_entry = next(
                (
                    entry
                    for entry in read_locust_final_stats(run_dir).get("entries", [])
                    if entry.get("request_type") == request_type
                ),
                None,
            )
            if final_entry:
                request_count = int(final_entry.get("request_count") or 0)
                failure_count = int(final_entry.get("failure_count") or 0)
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


def summarize_sse_measurements(path: Path, *, max_attempts: int | None = None) -> dict[str, Any]:
    """Return independent SSE timing aggregates without touching Locust HTTP stats."""
    buckets: dict[str, dict[str, Any]] = {}
    attempts = 0
    meta_path = path.with_name("sse-measurements.meta.json")
    truncated = False
    if meta_path.is_file():
        try:
            truncated = bool(json.loads(meta_path.read_text(encoding="utf-8")).get("truncated"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            truncated = True
    if not path.exists():
        return {
            "schema_version": "v1",
            "attempt_count": 0,
            "truncated": truncated,
            "checksum": "",
            "failure_reasons": {},
            "metrics": [],
        }
    failure_reasons: dict[str, int] = {}
    parse_error_count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            measurement = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(measurement, dict):
            continue
        if max_attempts is not None and attempts >= max(0, max_attempts):
            break
        attempts += 1
        parse_error_count += int(measurement.get("parse_error_count") or 0)
        values = dict(measurement.get("metrics")) if isinstance(measurement.get("metrics"), dict) else {}
        derived_values = measurement.get("derived_metrics") if isinstance(measurement.get("derived_metrics"), dict) else {}
        for metric_id, value in derived_values.items():
            normalized_id = str(metric_id).removesuffix("_ms")
            values[f"derived:{normalized_id}"] = value
        missing = {str(item) for item in measurement.get("missing_metric_ids", []) if isinstance(item, str)}
        failed = bool(measurement.get("failure_reason"))
        if failed:
            reason = str(measurement.get("failure_reason") or "unknown")
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        for metric_id in set(values) | missing:
            bucket = buckets.setdefault(metric_id, {"metric_id": metric_id, "values": [], "missing_count": 0, "failure_count": 0})
            if metric_id in missing:
                bucket["missing_count"] += 1
            if failed:
                bucket["failure_count"] += 1
            value = values.get(metric_id)
            if isinstance(value, (int, float)):
                bucket["values"].append(float(value))

    metrics = []
    for bucket in sorted(buckets.values(), key=lambda item: item["metric_id"]):
        values = sorted(bucket.pop("values"))
        missing_count = bucket["missing_count"]
        metrics.append(
            {
                "metric_id": bucket["metric_id"],
                "attempt_count": attempts,
                "matched_count": len(values),
                "missing_count": missing_count,
                "failure_count": bucket["failure_count"],
                "average_ms": round(sum(values) / len(values), 4) if values else None,
                "min_ms": round(values[0], 4) if values else None,
                "max_ms": round(values[-1], 4) if values else None,
                "p50_ms": _percentile(values, 0.5),
                "p95_ms": _percentile(values, 0.95),
                "p99_ms": _percentile(values, 0.99),
            }
        )
    return {
        "schema_version": "v1",
        "attempt_count": attempts,
        "truncated": truncated,
        "checksum": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        "failure_reasons": failure_reasons,
        "parse_error_count": parse_error_count,
        "timeout_count": failure_reasons.get("sse_stream_timeout", 0),
        "end_rule_not_matched_count": failure_reasons.get("sse_end_rule_not_matched", 0),
        "metrics": metrics,
    }


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    index = max(0, min(len(values) - 1, int((len(values) - 1) * quantile)))
    return round(values[index], 4)


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
    last_history_mtime_ns = 0
    automatic_analysis: tuple[str, str, str] | None = None
    while process.poll() is None:
        with connect() as db:
            last_sampled_at, last_history_mtime_ns = _persist_realtime_sample(
                db, run_id, run_dir, last_sampled_at, last_history_mtime_ns
            )
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
        _STOP_TIMEOUTS.pop(run_id, None)
    with connect() as db:
        _persist_realtime_sample(db, run_id, run_dir, last_sampled_at, last_history_mtime_ns)
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
            automatic_analysis = (
                str(current["project_id"]),
                str(current["id"]),
                str(current["created_by"]),
            )
            _prune_run_history(db, current["project_id"], current["performance_test_id"])
    if automatic_analysis:
        _schedule_automatic_analysis(*automatic_analysis)


def _schedule_automatic_analysis(project_id: str, run_id: str, created_by: str) -> str:
    from app.services.performance_testing.analysis_service import schedule_automatic_analysis

    return schedule_automatic_analysis(project_id, run_id, created_by)


def stop_headless_run(run_id: str) -> bool:
    with _PROCESS_LOCK:
        process = _PROCESSES.get(run_id)
        if process is None:
            return False
        _STOP_REQUESTED.add(run_id)
        stop_timeout = _STOP_TIMEOUTS.get(run_id, GRACEFUL_STOP_BUFFER_SECONDS)
    with connect() as db:
        current = run_repo.get_run(db, run_id)
        if current and current["status"] in {"starting", "running"}:
            run_repo.update_run_status(db, run_id, "stopping")
    process.terminate()
    threading.Thread(
        target=_force_kill_after_grace,
        args=(process, stop_timeout + GRACEFUL_STOP_BUFFER_SECONDS),
        daemon=True,
    ).start()
    return True


def _force_kill_after_grace(process: subprocess.Popen, timeout: float) -> None:
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()


def stop_headless_run_and_wait(run_id: str, *, timeout: float | None = None) -> bool:
    with _PROCESS_LOCK:
        finished = _MONITOR_FINISHED.get(run_id)
        stop_timeout = _STOP_TIMEOUTS.get(run_id, GRACEFUL_STOP_BUFFER_SECONDS)
    stop_headless_run(run_id)
    if finished is None:
        return True
    return finished.wait(timeout if timeout is not None else stop_timeout + GRACEFUL_STOP_BUFFER_SECONDS)


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
