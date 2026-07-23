from pathlib import Path

import pytest

from app.core import db as db_core
from app.core import settings
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    monkeypatch.setattr(db_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_core, "DB_PATH", tmp_path / "test.db")
    init_db()


def _seed_project_and_run() -> None:
    with connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, description, status, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("project-1", "项目一", "", "active", "u-admin"),
        )
        db.execute(
            """
            INSERT INTO api_automation_runs (
              id, project_id, task_id, status, script_ids_json, created_by
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("apirun-1", "project-1", "api_automation_run:apirun-1", "failed", "[]", "u-admin"),
        )


def test_repair_tables_and_run_lineage_columns_exist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)

    with connect() as db:
        session_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(api_repair_sessions)").fetchall()
        }
        attempt_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(api_repair_attempts)").fetchall()
        }
        run_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(api_automation_runs)").fetchall()
        }

    assert {
        "id",
        "project_id",
        "source_run_id",
        "current_run_id",
        "status",
        "current_revision",
    } <= session_columns
    assert {
        "id",
        "session_id",
        "attempt_number",
        "base_run_id",
        "base_revision",
        "status",
        "diagnosis_json",
        "validation_json",
    } <= attempt_columns
    assert {"parent_run_id", "source_repair_attempt_id"} <= run_columns


def test_repair_session_and_attempt_round_trip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_run()

    with connect() as db:
        api_automation_repo.create_repair_session(
            db,
            session_id="apirepair-1",
            project_id="project-1",
            source_run_id="apirun-1",
            current_run_id="apirun-1",
            created_by="u-admin",
        )
        api_automation_repo.create_repair_attempt(
            db,
            attempt_id="apirepairatt-1",
            session_id="apirepair-1",
            attempt_number=1,
            base_run_id="apirun-1",
            base_revision=0,
            user_context="参数错误时返回 200 和业务错误码",
        )
        api_automation_repo.update_repair_attempt(
            db,
            "apirepairatt-1",
            status="waiting_approval",
            diagnosis={"summary": "预期状态码可能错误"},
            validation={"summary": {"passed": 4, "failed": 1}},
        )
        session = api_automation_repo.find_repair_session(db, "apirepair-1")
        attempt = api_automation_repo.find_repair_attempt(db, "apirepairatt-1")
        attempts = api_automation_repo.list_repair_attempts(db, "apirepair-1")

    assert session is not None
    assert session["status"] == "active"
    assert session["current_revision"] == 0
    assert attempt is not None
    assert attempt["status"] == "waiting_approval"
    assert api_automation_repo.loads_json(attempt["diagnosis_json"], {}) == {
        "summary": "预期状态码可能错误"
    }
    assert api_automation_repo.loads_json(attempt["validation_json"], {})["summary"]["failed"] == 1
    assert [row["id"] for row in attempts] == ["apirepairatt-1"]


def test_repair_attempt_number_is_unique_within_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_run()

    with connect() as db:
        api_automation_repo.create_repair_session(
            db,
            session_id="apirepair-1",
            project_id="project-1",
            source_run_id="apirun-1",
            current_run_id="apirun-1",
            created_by="u-admin",
        )
        api_automation_repo.create_repair_attempt(
            db,
            attempt_id="apirepairatt-1",
            session_id="apirepair-1",
            attempt_number=1,
            base_run_id="apirun-1",
            base_revision=0,
        )

        with pytest.raises(Exception):
            api_automation_repo.create_repair_attempt(
                db,
                attempt_id="apirepairatt-2",
                session_id="apirepair-1",
                attempt_number=1,
                base_run_id="apirun-1",
                base_revision=0,
            )
