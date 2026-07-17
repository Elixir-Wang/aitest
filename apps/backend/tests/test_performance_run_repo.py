from pathlib import Path

import pytest

from app.core import db as db_core
from app.core import settings
from app.core.db import connect
from app.seed.init_db import init_db
from app.services.performance_testing import run_repo


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_core, "DB_PATH", tmp_path / "test.db")
    init_db()


def _seed_run_dependencies() -> None:
    with connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, description, status, created_by)
            VALUES (?, ?, '', 'active', 'u-admin')
            """,
            ("project-1", "项目-1"),
        )
        db.execute(
            """
            INSERT INTO performance_tests (
              id, project_id, name, target_type, endpoint_id, api_environment_id, created_by
            ) VALUES (?, ?, ?, 'endpoint', NULL, NULL, ?)
            """,
            ("perftest-1", "project-1", "性能测试-1", "u-admin"),
        )
        db.execute(
            """
            INSERT INTO performance_test_scripts (
              id, performance_test_id, project_id, version, generation_source,
              template_version, input_hash, code, validation_status
            ) VALUES (?, ?, ?, 1, 'default_plan', 'v1', 'hash', 'code', 'confirmed')
            """,
            ("perfscript-1", "perftest-1", "project-1"),
        )


def test_run_repository_persists_status_stats_failures_and_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run_dependencies()

    with connect() as db:
        run_repo.create_run(
            db,
            run_id="perfrun-1",
            project_id="project-1",
            performance_test_id="perftest-1",
            script_id="perfscript-1",
            load_config={"users": 10},
            runtime_config={"api_base_url": "https://example.test"},
            created_by="u-admin",
        )
        run_repo.update_run_status(db, "perfrun-1", "starting")
        run_repo.update_run_status(db, "perfrun-1", "running")
        run_repo.append_stats(
            db,
            run_id="perfrun-1",
            sample={"user_count": 10, "requests_per_second": 4.5, "failure_rate": 0.1},
        )
        run_repo.upsert_failure(
            db,
            run_id="perfrun-1",
            request_name="GET /items",
            method="GET",
            reason="500 Server Error",
            status_code=500,
        )
        run_repo.upsert_exception(
            db,
            run_id="perfrun-1",
            request_name="GET /items",
            exception_type="TimeoutError",
            message="request timed out",
        )
        run_repo.append_event(db, "perfrun-1", "stats_updated", "info", "统计已更新", {})

        run = run_repo.get_run(db, "perfrun-1")
        stats = run_repo.list_stats(db, "perfrun-1")
        failures = run_repo.list_failures(db, "perfrun-1")
        exceptions = run_repo.list_exceptions(db, "perfrun-1")
        events = run_repo.list_events(db, "perfrun-1")

    assert run["status"] == "running"
    assert stats[0]["requests_per_second"] == 4.5
    assert failures[0]["count"] == 1
    assert exceptions[0]["count"] == 1
    assert events[0]["event_type"] == "stats_updated"


def test_run_repository_rejects_illegal_status_transition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run_dependencies()

    with connect() as db:
        run_repo.create_run(
            db,
            run_id="perfrun-1",
            project_id="project-1",
            performance_test_id="perftest-1",
            script_id="perfscript-1",
            load_config={},
            runtime_config={},
            created_by="u-admin",
        )
        with pytest.raises(ValueError, match="非法的性能测试运行状态迁移"):
            run_repo.update_run_status(db, "perfrun-1", "completed")
