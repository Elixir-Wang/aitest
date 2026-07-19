import json
import secrets
from sqlite3 import Connection, Row
from typing import Any


RUN_STATUS_TRANSITIONS = {
    "created": {"starting", "cancelled", "failed"},
    "starting": {"running", "stopping", "failed", "cancelled"},
    "running": {"stopping", "completed", "failed"},
    "stopping": {"stopped", "failed"},
    "completed": set(),
    "stopped": set(),
    "failed": set(),
    "cancelled": set(),
}


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def create_run(
    db: Connection,
    *,
    run_id: str,
    project_id: str,
    performance_test_id: str,
    script_id: str,
    load_config: dict[str, Any],
    runtime_config: dict[str, Any],
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO performance_test_runs (
          id, project_id, performance_test_id, script_id, status,
          load_config_json, runtime_config_json, created_by
        ) VALUES (?, ?, ?, ?, 'created', ?, ?, ?)
        """,
        (
            run_id,
            project_id,
            performance_test_id,
            script_id,
            _dumps(load_config),
            _dumps(runtime_config),
            created_by,
        ),
    )


def get_run(db: Connection, run_id: str) -> Row | None:
    return db.execute("SELECT * FROM performance_test_runs WHERE id = ?", (run_id,)).fetchone()


def list_runs(db: Connection, project_id: str, performance_test_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT * FROM performance_test_runs
        WHERE project_id = ? AND performance_test_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (project_id, performance_test_id),
    ).fetchall()


def recover_stale_runs(db: Connection, timeout_minutes: int = 5) -> int:
    rows = db.execute(
        """
        SELECT id FROM performance_test_runs
        WHERE status IN ('starting', 'running')
          AND updated_at < datetime('now', ?)
        """,
        (f"-{timeout_minutes} minutes",),
    ).fetchall()
    for row in rows:
        update_run_status(
            db,
            row["id"],
            "failed",
            error_code="PERFORMANCE_RUN_TIMEOUT",
            error_message="Worker 超过心跳窗口未更新运行状态。",
        )
        append_event(db, row["id"], "worker_timeout", "error", "Worker 心跳超时，运行已恢复为失败", {})
    return len(rows)


def touch_run(db: Connection, run_id: str) -> None:
    db.execute(
        "UPDATE performance_test_runs SET updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status IN ('starting', 'running')",
        (run_id,),
    )


def update_run_status(
    db: Connection,
    run_id: str,
    status: str,
    *,
    error_code: str = "",
    error_message: str = "",
    trace_id: str = "",
) -> None:
    row = get_run(db, run_id)
    if row is None:
        raise KeyError(f"性能测试运行不存在: {run_id}")
    if status not in RUN_STATUS_TRANSITIONS.get(row["status"], set()):
        raise ValueError(f"非法的性能测试运行状态迁移: {row['status']} -> {status}")

    started_at = "CURRENT_TIMESTAMP" if status == "running" else "started_at"
    finished_at = "CURRENT_TIMESTAMP" if status in {"completed", "stopped", "failed", "cancelled"} else "finished_at"
    db.execute(
        f"""
        UPDATE performance_test_runs
        SET status = ?, error_code = ?, error_message = ?, trace_id = ?,
            started_at = {started_at}, finished_at = {finished_at}, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, error_code, error_message, trace_id, run_id),
    )


def append_stats(db: Connection, *, run_id: str, sample: dict[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO performance_test_run_stats (
          id, run_id, user_count, request_count, failure_count,
          requests_per_second, failure_rate, average_response_time_ms,
          p50_response_time_ms, p95_response_time_ms, p99_response_time_ms,
          stats_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"perfstat-{secrets.token_hex(8)}",
            run_id,
            int(sample.get("user_count") or 0),
            int(sample.get("request_count") or 0),
            int(sample.get("failure_count") or 0),
            float(sample.get("requests_per_second") or 0),
            float(sample.get("failure_rate") or 0),
            float(sample.get("average_response_time_ms") or 0),
            float(sample.get("p50_response_time_ms") or 0),
            float(sample.get("p95_response_time_ms") or 0),
            float(sample.get("p99_response_time_ms") or 0),
            _dumps(sample),
        ),
    )
    db.execute(
        "UPDATE performance_test_runs SET latest_summary_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (_dumps(sample), run_id),
    )


def set_report_directory(db: Connection, run_id: str, report_directory: str) -> None:
    db.execute(
        "UPDATE performance_test_runs SET report_directory = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (report_directory, run_id),
    )


def reset_stats(db: Connection, run_id: str) -> None:
    db.execute("DELETE FROM performance_test_run_stats WHERE run_id = ?", (run_id,))
    db.execute("DELETE FROM performance_test_run_failures WHERE run_id = ?", (run_id,))
    db.execute("DELETE FROM performance_test_run_exceptions WHERE run_id = ?", (run_id,))
    db.execute(
        "UPDATE performance_test_runs SET latest_summary_json = '{}', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (run_id,),
    )


def list_stats(db: Connection, run_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM performance_test_run_stats WHERE run_id = ? ORDER BY sampled_at, id",
        (run_id,),
    ).fetchall()


def upsert_failure(
    db: Connection,
    *,
    run_id: str,
    request_name: str,
    method: str,
    reason: str,
    status_code: int | None = None,
    response_excerpt: str = "",
) -> None:
    db.execute(
        """
        INSERT INTO performance_test_run_failures (
          id, run_id, request_name, method, reason, sample_status_code, sample_response_excerpt
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, request_name, method, reason) DO UPDATE SET
          count = count + 1,
          last_occurred_at = CURRENT_TIMESTAMP,
          sample_status_code = COALESCE(performance_test_run_failures.sample_status_code, excluded.sample_status_code),
          sample_response_excerpt = CASE WHEN performance_test_run_failures.sample_response_excerpt = ''
            THEN excluded.sample_response_excerpt ELSE performance_test_run_failures.sample_response_excerpt END
        """,
        (f"perffailure-{secrets.token_hex(8)}", run_id, request_name, method, reason, status_code, response_excerpt[:1000]),
    )


def list_failures(db: Connection, run_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM performance_test_run_failures WHERE run_id = ? ORDER BY count DESC, last_occurred_at DESC",
        (run_id,),
    ).fetchall()


def upsert_exception(
    db: Connection,
    *,
    run_id: str,
    request_name: str,
    exception_type: str,
    message: str,
) -> None:
    db.execute(
        """
        INSERT INTO performance_test_run_exceptions (
          id, run_id, request_name, exception_type, message
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(run_id, request_name, exception_type, message) DO UPDATE SET
          count = count + 1,
          last_occurred_at = CURRENT_TIMESTAMP
        """,
        (f"perfexception-{secrets.token_hex(8)}", run_id, request_name, exception_type, message[:2000]),
    )


def list_exceptions(db: Connection, run_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM performance_test_run_exceptions WHERE run_id = ? ORDER BY count DESC, last_occurred_at DESC",
        (run_id,),
    ).fetchall()


def append_event(
    db: Connection,
    run_id: str,
    event_type: str,
    level: str,
    message: str,
    payload: dict[str, Any],
    trace_id: str = "",
) -> None:
    db.execute(
        """
        INSERT INTO performance_test_run_events (
          id, run_id, event_type, level, message, payload_json, trace_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (f"perfevent-{secrets.token_hex(8)}", run_id, event_type, level, message, _dumps(payload), trace_id),
    )


def list_events(db: Connection, run_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM performance_test_run_events WHERE run_id = ? ORDER BY created_at, id",
        (run_id,),
    ).fetchall()
