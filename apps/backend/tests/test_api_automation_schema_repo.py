import sqlite3
from pathlib import Path

import pytest

from app.core import settings
from app.core import db as db_core
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.schemas.api_automation import ApiTestCaseSetIn
from app.services.api_automation import service


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    monkeypatch.setattr(db_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_core, "DB_PATH", tmp_path / "test.db")
    init_db()


def _seed_project() -> None:
    with connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, description, status, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("project-1", "项目一", "", "active", "u-admin"),
        )


def _seed_project_endpoints(endpoint_ids: list[str]) -> None:
    _seed_project()
    with connect() as db:
        for index, endpoint_id in enumerate(endpoint_ids):
            api_automation_repo.upsert_endpoint(
                db,
                endpoint_id=endpoint_id,
                project_id="project-1",
                document_id=None,
                method="GET",
                path=f"/items/{index}",
                normalized_path=f"/items/{index}",
                summary=f"Item {index}",
                description="",
                tags=[],
                parameters=[],
                request_body={},
                responses={},
                auth={},
                source={},
                created_by="u-admin",
            )


def test_generation_items_and_attempts_are_persisted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoints(["apiend-1", "apiend-2"])
    with connect() as db:
        api_automation_repo.create_generation_run(
            db,
            run_id="apigen-1",
            task_id="api_automation_generation:apigen-1",
            project_id="project-1",
            api_environment_id=None,
            endpoint_ids=["apiend-1", "apiend-2"],
            source_test_case_ids=[],
            generation_goal="批量生成",
            options={},
            created_by="u-admin",
        )
        api_automation_repo.create_generation_items(db, "apigen-1", ["apiend-1", "apiend-2"])
        items = api_automation_repo.list_generation_items(db, "apigen-1")
        api_automation_repo.start_generation_item_attempt(db, items[0]["id"], "attempt-1")
        api_automation_repo.finish_generation_item_attempt(
            db,
            items[0]["id"],
            "attempt-1",
            status="completed",
            generated_case_count=3,
        )

    assert [item["endpoint_id"] for item in items] == ["apiend-1", "apiend-2"]
    with connect() as db:
        item = api_automation_repo.find_generation_item(db, items[0]["id"])
        attempts = api_automation_repo.list_generation_item_attempts(db, items[0]["id"])
    assert item["status"] == "completed"
    assert item["attempt_count"] == 1
    assert attempts[0]["id"] == "attempt-1"


def test_existing_database_adds_generation_batch_structure_without_losing_cases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    with connect() as db:
        api_automation_repo.create_generation_run(
            db,
            run_id="apigen-legacy",
            task_id="api_automation_generation:apigen-legacy",
            project_id="project-1",
            api_environment_id=None,
            endpoint_ids=[],
            source_test_case_ids=[],
            generation_goal="",
            options={},
            created_by="u-admin",
        )
        api_automation_repo.create_api_test_case(
            db,
            case_id="apitc-legacy",
            project_id="project-1",
            endpoint_id=None,
            source_test_case_id=None,
            generation_run_id="apigen-legacy",
            title="Legacy case",
            priority="P2",
            source="ai_generated",
            tags=[],
            coverage="positive",
            preconditions=[],
            request={},
            test_data={},
            expected={},
            assertions=[],
            variables={},
            data_origin={},
            data_file_path="",
            notes="",
            created_by="u-admin",
        )

    raw_db = sqlite3.connect(settings.DB_PATH)
    raw_db.executescript(
        """
        DROP TABLE IF EXISTS api_generation_item_attempts;
        DROP TABLE IF EXISTS api_generation_items;
        ALTER TABLE api_generation_runs RENAME TO api_generation_runs_current;
        CREATE TABLE api_generation_runs (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL, api_environment_id TEXT,
          task_id TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')),
          endpoint_ids_json TEXT NOT NULL DEFAULT '[]', source_test_case_ids_json TEXT NOT NULL DEFAULT '[]',
          generation_goal TEXT NOT NULL DEFAULT '', options_json TEXT NOT NULL DEFAULT '{}',
          result_summary_json TEXT NOT NULL DEFAULT '{}', error_message TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT
        );
        INSERT INTO api_generation_runs SELECT * FROM api_generation_runs_current;
        DROP TABLE api_generation_runs_current;
        ALTER TABLE api_test_cases RENAME TO api_test_cases_current;
        CREATE TABLE api_test_cases AS
          SELECT id, project_id, endpoint_id, source_test_case_id, generation_run_id,
                 title, priority, coverage, source, tags_json, preconditions_json,
                 request_json, test_data_json, expected_json, assertions_json, variables_json,
                 data_origin_json, data_file_path, notes, created_by, updated_by, created_at, updated_at
          FROM api_test_cases_current;
        DROP TABLE api_test_cases_current;
        """
    )
    raw_db.close()

    init_db()

    with connect() as db:
        tables = {
            row["name"]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'api_generation_item%'"
            )
        }
        case_columns = {row["name"] for row in db.execute("PRAGMA table_info(api_test_cases)")}
        case = db.execute("SELECT id FROM api_test_cases WHERE id = 'apitc-legacy'").fetchone()
        run_sql = db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'api_generation_runs'"
        ).fetchone()["sql"]

    assert tables == {"api_generation_items", "api_generation_item_attempts"}
    assert {"generation_item_id", "generation_attempt_id"} <= case_columns
    assert case["id"] == "apitc-legacy"
    assert "partial_success" in run_sql


def test_upsert_endpoint_uses_method_and_normalized_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    with connect() as db:
        document_id = api_automation_repo.create_document(
            db,
            document_id="apidoc-1",
            project_id="project-1",
            name="Petstore",
            source_type="file",
            source_url="",
            file_path="documents/apidoc-1/openapi.yaml",
            version="3.0.3",
            endpoint_count=0,
            created_by="u-admin",
        )
        first = api_automation_repo.upsert_endpoint(
            db,
            endpoint_id="apiend-1",
            project_id="project-1",
            document_id=document_id,
            method="GET",
            path="/pets/{petId}",
            normalized_path="/pets/{petId}",
            summary="Get pet",
            description="",
            tags=["pet"],
            parameters=[],
            request_body={},
            responses={"200": {"description": "ok"}},
            auth={},
            source={"operationId": "getPet"},
            created_by="u-admin",
        )
        second = api_automation_repo.upsert_endpoint(
            db,
            endpoint_id="apiend-2",
            project_id="project-1",
            document_id=document_id,
            method="GET",
            path="/pets/{petId}",
            normalized_path="/pets/{petId}",
            summary="Get pet v2",
            description="updated",
            tags=["pet"],
            parameters=[],
            request_body={},
            responses={"404": {"description": "missing"}},
            auth={},
            source={"operationId": "getPetV2"},
            created_by="u-admin",
        )
        rows = api_automation_repo.list_endpoints(db, "project-1")

    assert first == second
    assert len(rows) == 1
    assert rows[0]["summary"] == "Get pet v2"
    assert api_automation_repo.loads_json(rows[0]["responses_json"], {}) == {"404": {"description": "missing"}}


def test_generation_case_script_and_run_records(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    with connect() as db:
        generation_id = api_automation_repo.create_generation_run(
            db,
            run_id="apigen-1",
            task_id="api_automation_generation:apigen-1",
            project_id="project-1",
            api_environment_id=None,
            endpoint_ids=["apiend-1"],
            source_test_case_ids=[],
            generation_goal="覆盖登录",
            options={"generate_code": True},
            created_by="u-admin",
        )
        case_id = api_automation_repo.create_api_test_case(
            db,
            case_id="apitc-1",
            project_id="project-1",
            endpoint_id=None,
            source_test_case_id=None,
            generation_run_id=generation_id,
            title="登录成功",
            priority="P1",
            source="ai_generated",
            tags=["login"],
            coverage="positive",
            preconditions=["用户账号存在"],
            request={"method": "POST", "path": "/login"},
            test_data={"username": {"value": "demo", "source": "openapi_example", "required": True}},
            expected={"status_code": 200},
            assertions=[{"type": "status_code", "expected": 200}],
            variables={},
            data_origin={"body.username": "ai_generated"},
            data_file_path="data/test_login.json",
            notes="",
            created_by="u-admin",
        )
        script_id = api_automation_repo.create_script(
            db,
            script_id="apiscript-1",
            project_id="project-1",
            endpoint_id=None,
            api_test_case_id=case_id,
            test_case_id=None,
            generation_run_id=generation_id,
            name="test_login",
            status="ready",
            suite_path="generated/apisuite-1",
            test_file_path="generated/apisuite-1/tests/test_login.py",
            data_file_path="generated/apisuite-1/data/test_login.json",
            notes="",
            created_by="u-admin",
        )
        run_id = api_automation_repo.create_api_run(
            db,
            run_id="apirun-1",
            task_id="api_automation_run:apirun-1",
            project_id="project-1",
            api_environment_id=None,
            script_ids=[script_id],
            command_summary="uv run pytest tests",
            created_by="u-admin",
        )

        cases = api_automation_repo.list_api_test_cases(db, "project-1")
        script = api_automation_repo.find_script(db, script_id)
        run = api_automation_repo.find_api_run(db, run_id)

    assert cases[0]["id"] == case_id
    assert cases[0]["coverage"] == "positive"
    assert api_automation_repo.loads_json(cases[0]["preconditions_json"], []) == ["用户账号存在"]
    assert api_automation_repo.loads_json(cases[0]["test_data_json"], {})["username"]["value"] == "demo"
    assert api_automation_repo.loads_json(cases[0]["data_origin_json"], {})["body.username"] == "ai_generated"
    assert script["api_test_case_id"] == case_id
    assert api_automation_repo.loads_json(run["script_ids_json"], []) == [script_id]


def test_update_api_test_case_set_changes_name_and_notes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    actor = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}

    created = service.create_api_test_case_set(
        "project-1",
        ApiTestCaseSetIn(name="旧接口集", notes="旧备注"),
        actor,
    )

    updated = service.update_api_test_case_set(
        "project-1",
        created["id"],
        ApiTestCaseSetIn(name="新接口集", notes="新备注"),
        actor,
    )

    assert updated["id"] == created["id"]
    assert updated["name"] == "新接口集"
    assert updated["notes"] == "新备注"
    assert updated["updated_at"] >= created["updated_at"]
