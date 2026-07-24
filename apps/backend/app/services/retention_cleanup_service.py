from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

from app.core.db import connect
from app.core.settings import LOGS_DIR
from app.repositories import operation_log_repo

JOB_NAME = "system-log-retention"
MAX_RETENTION_DAYS = 10
DEFAULT_STARTUP_DELAY_SECONDS = 30.0
RETRY_DELAY_SECONDS = 60.0
ELIGIBILITY_CHECK_INTERVAL_SECONDS = 60.0 * 60.0
MAX_ATTEMPTS = 3
DELETE_BATCH_SIZE = 1000
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
LOG_SUBDIRECTORIES = ("app", "error", "access", "agent")

_timer_lock = threading.Lock()
_timer: threading.Timer | None = None
_shutting_down = False


@dataclass(frozen=True)
class CleanupResult:
    status: str
    deleted_database_logs: int = 0
    deleted_log_files: int = 0


def schedule_cleanup(*, delay_seconds: float = DEFAULT_STARTUP_DELAY_SECONDS) -> bool:
    global _shutting_down
    with _timer_lock:
        _shutting_down = False
        if _timer is not None and _timer.is_alive():
            return False
        _start_timer_locked(delay_seconds, attempt=1)
        return True


def shutdown_cleanup() -> None:
    global _shutting_down, _timer
    with _timer_lock:
        _shutting_down = True
        if _timer is not None:
            _timer.cancel()
        _timer = None


def run_cleanup_if_due(*, now: datetime | None = None) -> CleanupResult:
    current_time = _as_utc(now or datetime.now(timezone.utc))
    current_local_date = current_time.astimezone(LOCAL_TIMEZONE).date()

    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        state = db.execute(
            "SELECT last_success_at FROM retention_cleanup_state WHERE job_name = ?",
            (JOB_NAME,),
        ).fetchone()
        if state and _local_date(state["last_success_at"]) == current_local_date:
            return CleanupResult(status="skipped")

        policy = operation_log_repo.get_retention_policy(db)
        retention_days = min(MAX_RETENTION_DAYS, max(1, int(policy["retention_days"])))
        cutoff = current_time - timedelta(days=retention_days)
        deleted_log_files = _delete_expired_log_files(cutoff)
        deleted_database_logs = _delete_database_logs(db, cutoff)
        success_at = current_time.isoformat()
        db.execute(
            """
            INSERT INTO retention_cleanup_state (job_name, last_success_at, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(job_name) DO UPDATE SET
              last_success_at = excluded.last_success_at,
              updated_at = CURRENT_TIMESTAMP
            """,
            (JOB_NAME, success_at),
        )

    logger.info(
        "Retention cleanup succeeded: database_logs={}, log_files={}, retention_days={}",
        deleted_database_logs,
        deleted_log_files,
        retention_days,
    )
    return CleanupResult(
        status="succeeded",
        deleted_database_logs=deleted_database_logs,
        deleted_log_files=deleted_log_files,
    )


def _delete_database_logs(db, cutoff: datetime) -> int:
    before_time = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    deleted_total = 0
    while True:
        deleted = operation_log_repo.cleanup_logs_before(
            db,
            before_time=before_time,
            batch_size=DELETE_BATCH_SIZE,
        )
        deleted_total += deleted
        if deleted < DELETE_BATCH_SIZE:
            return deleted_total


def _delete_expired_log_files(cutoff: datetime) -> int:
    deleted = 0
    cutoff_timestamp = cutoff.timestamp()
    for subdirectory in LOG_SUBDIRECTORIES:
        log_directory = LOGS_DIR / subdirectory
        if not log_directory.is_dir():
            continue
        for path in log_directory.iterdir():
            try:
                expired = _is_expired_file(path, cutoff_timestamp)
            except FileNotFoundError:
                continue
            if not expired:
                continue
            try:
                path.unlink()
                deleted += 1
            except FileNotFoundError:
                continue
    return deleted


def _is_expired_file(path: Path, cutoff_timestamp: float) -> bool:
    return path.is_file() and path.stat().st_mtime < cutoff_timestamp


def _run_scheduled_cleanup(attempt: int) -> None:
    global _timer
    next_delay = ELIGIBILITY_CHECK_INTERVAL_SECONDS
    next_attempt = 1
    try:
        run_cleanup_if_due()
    except Exception:
        logger.exception("Retention cleanup attempt {} failed", attempt)
        if attempt < MAX_ATTEMPTS:
            next_delay = RETRY_DELAY_SECONDS
            next_attempt = attempt + 1
    with _timer_lock:
        if _shutting_down:
            _timer = None
            return
        _start_timer_locked(next_delay, attempt=next_attempt)


def _start_timer_locked(delay_seconds: float, *, attempt: int) -> None:
    global _timer
    _timer = threading.Timer(delay_seconds, _run_scheduled_cleanup, args=(attempt,))
    _timer.name = "retention-cleanup"
    _timer.daemon = True
    _timer.start()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _local_date(value: str) -> date | None:
    try:
        return _as_utc(datetime.fromisoformat(value)).astimezone(LOCAL_TIMEZONE).date()
    except ValueError:
        return None
