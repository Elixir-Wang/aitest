from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from app.core import db as core_db
from app.seed.init_db import init_db
from app.services import retention_cleanup_service


def _use_temp_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(retention_cleanup_service, "LOGS_DIR", tmp_path / "logs")
    init_db()


def _insert_log(db, log_id: str, created_at: str) -> None:
    db.execute(
        """
        INSERT INTO operation_logs (
          id, log_type, module, action, object_type, object_name, source, result, created_at
        )
        VALUES (?, 'audit', 'test', 'test', 'test', '测试日志', 'system', 'success', ?)
        """,
        (log_id, created_at),
    )


def test_cleanup_deletes_expired_logs_and_runs_only_once_per_local_day(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_storage(monkeypatch, tmp_path)
    log_directory = tmp_path / "logs" / "app"
    log_directory.mkdir(parents=True)
    old_file = log_directory / "old.log"
    recent_file = log_directory / "recent.log"
    old_file.write_text("old", encoding="utf-8")
    recent_file.write_text("recent", encoding="utf-8")
    now = datetime(2026, 7, 24, 4, 0, tzinfo=timezone.utc)
    old_timestamp = now.timestamp() - 11 * 24 * 60 * 60
    recent_timestamp = now.timestamp() - 9 * 24 * 60 * 60
    os.utime(old_file, (old_timestamp, old_timestamp))
    os.utime(recent_file, (recent_timestamp, recent_timestamp))

    with core_db.connect() as db:
        _insert_log(db, "old", "2026-07-13 00:00:00")
        _insert_log(db, "recent", "2026-07-20 00:00:00")

    first = retention_cleanup_service.run_cleanup_if_due(now=now)
    with core_db.connect() as db:
        _insert_log(db, "old-after-success", "2026-07-13 00:00:00")
    second = retention_cleanup_service.run_cleanup_if_due(now=now.replace(hour=12))

    assert first.status == "succeeded"
    assert first.deleted_database_logs == 1
    assert first.deleted_log_files == 1
    assert second.status == "skipped"
    assert old_file.exists() is False
    assert recent_file.exists() is True
    with core_db.connect() as db:
        remaining_ids = {row["id"] for row in db.execute("SELECT id FROM operation_logs").fetchall()}
        state = db.execute(
            "SELECT last_success_at FROM retention_cleanup_state WHERE job_name = ?",
            (retention_cleanup_service.JOB_NAME,),
        ).fetchone()
    assert remaining_ids == {"recent", "old-after-success"}
    assert state["last_success_at"] == now.isoformat()


def test_cleanup_can_run_again_on_the_next_local_day(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_storage(monkeypatch, tmp_path)
    first_time = datetime(2026, 7, 24, 4, 0, tzinfo=timezone.utc)
    next_day = datetime(2026, 7, 25, 4, 0, tzinfo=timezone.utc)

    assert retention_cleanup_service.run_cleanup_if_due(now=first_time).status == "succeeded"
    assert retention_cleanup_service.run_cleanup_if_due(now=next_day).status == "succeeded"


def test_failed_cleanup_does_not_record_success(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(
        retention_cleanup_service.operation_log_repo,
        "cleanup_logs_before",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        retention_cleanup_service.run_cleanup_if_due(
            now=datetime(2026, 7, 24, 4, 0, tzinfo=timezone.utc)
        )

    with core_db.connect() as db:
        state = db.execute("SELECT * FROM retention_cleanup_state").fetchall()
    assert state == []


def test_scheduler_checks_again_without_running_cleanup_more_than_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timers = []

    class FakeTimer:
        def __init__(self, interval, function, args=()):
            self.interval = interval
            self.function = function
            self.args = args
            self.started = False
            self.cancelled = False
            timers.append(self)

        def start(self):
            self.started = True

        def cancel(self):
            self.cancelled = True

        def is_alive(self):
            return self.started and not self.cancelled

    monkeypatch.setattr(retention_cleanup_service.threading, "Timer", FakeTimer)
    monkeypatch.setattr(
        retention_cleanup_service,
        "run_cleanup_if_due",
        lambda: retention_cleanup_service.CleanupResult(status="skipped"),
    )
    retention_cleanup_service.shutdown_cleanup()

    assert retention_cleanup_service.schedule_cleanup(delay_seconds=30) is True
    assert timers[0].interval == 30
    timers[0].function(*timers[0].args)
    assert timers[1].interval == retention_cleanup_service.ELIGIBILITY_CHECK_INTERVAL_SECONDS

    retention_cleanup_service.shutdown_cleanup()
    assert timers[1].cancelled is True
