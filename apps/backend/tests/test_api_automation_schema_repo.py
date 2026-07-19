import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core import storage
from app.core import settings
from app.core import db as db_core
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.schemas.api_automation import ApiAutomationGenerateIn, ApiRunCreateIn, ApiTestCaseSetIn, ApiTestCaseSetOut
from app.seed.seeds import _ensure_api_generation_batch_structure
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


def test_generation_request_limits_endpoint_ids_to_100() -> None:
    assert len(ApiAutomationGenerateIn(endpoint_ids=[f"apiend-{index}" for index in range(100)]).endpoint_ids) == 100

    with pytest.raises(ValidationError):
        ApiAutomationGenerateIn(endpoint_ids=[f"apiend-{index}" for index in range(101)])


def test_scenario_step_schema_contains_type_and_control_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)

    with connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(api_scenario_steps)").fetchall()}

    assert {"step_type", "control_config_json"} <= columns


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


def test_generation_items_reject_duplicate_run_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoints(["apiend-1"])
    with connect() as db:
        api_automation_repo.create_generation_run(
            db,
            run_id="apigen-1",
            task_id="api_automation_generation:apigen-1",
            project_id="project-1",
            api_environment_id=None,
            endpoint_ids=["apiend-1"],
            source_test_case_ids=[],
            generation_goal="",
            options={},
            created_by="u-admin",
        )
        api_automation_repo.create_generation_items(db, "apigen-1", ["apiend-1"])

        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO api_generation_items (id, generation_run_id, endpoint_id) VALUES (?, ?, ?)",
                ("apigenitem-duplicate", "apigen-1", "apiend-1"),
            )


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
        api_automation_repo.create_api_test_case_set(
            db,
            set_id="apiset-legacy",
            project_id="project-1",
            name="Legacy set",
            notes="",
            created_by="u-admin",
        )
        db.execute(
            "UPDATE api_test_case_sets SET latest_generation_run_id = ? WHERE id = ?",
            ("apigen-legacy", "apiset-legacy"),
        )
        api_automation_repo.create_script(
            db,
            script_id="apiscript-legacy",
            project_id="project-1",
            endpoint_id=None,
            api_test_case_id="apitc-legacy",
            test_case_id=None,
            generation_run_id="apigen-legacy",
            name="legacy_script",
            status="ready",
            suite_path="generated/legacy",
            test_file_path="generated/legacy/test_legacy.py",
            data_file_path="",
            notes="",
            created_by="u-admin",
        )

    raw_db = sqlite3.connect(settings.DB_PATH)
    raw_db.executescript(
        """
        PRAGMA legacy_alter_table = ON;
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
        CREATE TABLE api_test_cases_legacy (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          endpoint_id TEXT,
          source_test_case_id TEXT,
          generation_run_id TEXT,
          title TEXT NOT NULL,
          priority TEXT NOT NULL DEFAULT 'P2',
          coverage TEXT NOT NULL DEFAULT 'positive',
          source TEXT NOT NULL CHECK(source IN ('ai_generated', 'manual', 'approved_test_case')) DEFAULT 'ai_generated',
          tags_json TEXT NOT NULL DEFAULT '[]',
          preconditions_json TEXT NOT NULL DEFAULT '[]',
          request_json TEXT NOT NULL DEFAULT '{}',
          test_data_json TEXT NOT NULL DEFAULT '{}',
          expected_json TEXT NOT NULL DEFAULT '{}',
          assertions_json TEXT NOT NULL DEFAULT '[]',
          variables_json TEXT NOT NULL DEFAULT '{}',
          data_origin_json TEXT NOT NULL DEFAULT '{}',
          data_file_path TEXT NOT NULL DEFAULT '',
          notes TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          updated_by TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE SET NULL,
          FOREIGN KEY(source_test_case_id) REFERENCES test_cases(id) ON DELETE SET NULL,
          FOREIGN KEY(generation_run_id) REFERENCES api_generation_runs(id) ON DELETE SET NULL
        );
        INSERT INTO api_test_cases_legacy (
          id, project_id, endpoint_id, source_test_case_id, generation_run_id,
          title, priority, coverage, source, tags_json, preconditions_json,
          request_json, test_data_json, expected_json, assertions_json, variables_json,
          data_origin_json, data_file_path, notes, created_by, updated_by, created_at, updated_at
        )
            SELECT
              id, project_id, endpoint_id, source_test_case_id, generation_run_id,
              title, priority, coverage, source, '[]', preconditions_json,
          request_json, test_data_json, expected_json, assertions_json, variables_json,
          data_origin_json, data_file_path, notes, created_by, updated_by, created_at, updated_at
        FROM api_test_cases;
        DROP TABLE api_test_cases;
        ALTER TABLE api_test_cases_legacy RENAME TO api_test_cases;
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
        case = db.execute(
            "SELECT id, generation_run_id, test_point_key, oracle_status "
            "FROM api_test_cases WHERE id = 'apitc-legacy'"
        ).fetchone()
        case_set = db.execute(
            "SELECT latest_generation_run_id FROM api_test_case_sets WHERE id = 'apiset-legacy'"
        ).fetchone()
        script = db.execute(
            "SELECT generation_run_id FROM api_test_scripts WHERE id = 'apiscript-legacy'"
        ).fetchone()
        foreign_key_violations = db.execute("PRAGMA foreign_key_check").fetchall()
        run_sql = db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'api_generation_runs'"
        ).fetchone()["sql"]

    assert tables == {"api_generation_items", "api_generation_item_attempts"}
    assert {"generation_item_id", "generation_attempt_id", "test_point_key", "oracle_status"} <= case_columns
    assert "tags_json" not in case_columns
    assert case["id"] == "apitc-legacy"
    assert case["generation_run_id"] == "apigen-legacy"
    assert case["test_point_key"] == "legacy.apitc-legacy"
    assert case["oracle_status"] == "confirmed"
    assert case_set["latest_generation_run_id"] == "apigen-legacy"
    assert script["generation_run_id"] == "apigen-legacy"
    assert foreign_key_violations == []
    assert "partial_success" in run_sql


def test_generation_batch_migration_rejects_foreign_key_violations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    raw_db = sqlite3.connect(settings.DB_PATH)
    raw_db.row_factory = sqlite3.Row
    raw_db.execute("PRAGMA foreign_keys = OFF")
    raw_db.execute(
        "INSERT INTO api_test_case_sets "
        "(id, project_id, name, latest_generation_run_id, created_by) VALUES (?, ?, ?, ?, ?)",
        ("apiset-invalid", "missing-project", "Invalid", "missing-run", "u-admin"),
    )
    raw_db.commit()
    raw_db.execute("PRAGMA foreign_keys = ON")

    with pytest.raises(RuntimeError, match="Foreign key violations remain"):
        _ensure_api_generation_batch_structure(raw_db)

    raw_db.close()


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
            execution_snapshot={
                "environment": {"id": "api-env-1", "name": "测试环境", "api_base_url": "https://api.example.com"},
                "scripts": [{"id": script_id, "name": "test_login", "case_count": 1}],
                "script_count": 1,
                "case_count": 1,
            },
        )

        cases = api_automation_repo.list_api_test_cases(db, "project-1")
        script = api_automation_repo.find_script(db, script_id)
        run = api_automation_repo.find_api_run(db, run_id)
        runs, total = api_automation_repo.list_api_runs(db, "project-1", page=1, page_size=20, keyword="test_login")

    assert cases[0]["id"] == case_id
    assert cases[0]["coverage"] == "positive"
    assert api_automation_repo.loads_json(cases[0]["preconditions_json"], []) == ["用户账号存在"]
    assert api_automation_repo.loads_json(cases[0]["test_data_json"], {})["username"]["value"] == "demo"
    assert api_automation_repo.loads_json(cases[0]["data_origin_json"], {})["body.username"] == "ai_generated"
    assert script["api_test_case_id"] == case_id
    assert api_automation_repo.loads_json(run["script_ids_json"], []) == [script_id]
    assert api_automation_repo.loads_json(run["execution_snapshot_json"], {})["case_count"] == 1
    assert total == 1
    assert [item["id"] for item in runs] == [run_id]


def test_api_run_schema_supports_observed_status_and_observation_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)

    with connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(api_automation_runs)")}
        table_sql = db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'api_automation_runs'"
        ).fetchone()["sql"]

    assert "observation_result_path" in columns
    assert "observed" in table_sql


def test_api_run_snapshot_and_legacy_history_include_environment_and_endpoint_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoints(["apiend-1"])
    with connect() as db:
        db.execute(
            """
            INSERT INTO api_test_environments (id, project_id, name, api_base_url, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("apienv-1", "project-1", "集成测试环境", "https://api.example.com", "u-admin"),
        )
        db.execute(
            """
            INSERT INTO api_test_scripts (
              id, project_id, endpoint_id, name, status, suite_path, test_file_path, case_count, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "apiscript-1",
                "project-1",
                "apiend-1",
                "test_items",
                "ready",
                "generated/apisuite-1",
                "generated/apisuite-1/tests/test_items.py",
                3,
                "u-admin",
            ),
        )

    with connect() as db:
        actor = db.execute(
            "SELECT ? AS id, ? AS role, ? AS nickname, ? AS username, ? AS project_scope",
            ("u-admin", "admin", "管理员", "admin", "全部项目"),
        ).fetchone()
    created = service.create_api_run(
        "project-1",
        ApiRunCreateIn(script_ids=["apiscript-1"], api_environment_id="apienv-1"),
        actor,
    )

    assert created["execution_snapshot"]["environment"]["name"] == "集成测试环境"
    assert created["execution_snapshot"]["endpoint_count"] == 1
    assert created["execution_snapshot"]["scripts"][0]["endpoint_id"] == "apiend-1"

    with connect() as db:
        db.execute(
            "UPDATE api_automation_runs SET execution_snapshot_json = '{}' WHERE id = ?",
            (created["id"],),
        )

    legacy = service.list_api_runs("project-1", actor)["items"][0]
    assert legacy["execution_snapshot"]["environment"]["name"] == "集成测试环境"
    assert legacy["execution_snapshot"]["endpoint_count"] == 1
    assert legacy["execution_snapshot"]["case_count"] == 3

    with connect() as db:
        db.execute("DELETE FROM api_test_scripts WHERE id = ?", ("apiscript-1",))

    legacy_after_script_deleted = service.list_api_runs("project-1", actor)["items"][0]
    assert legacy_after_script_deleted["execution_snapshot"]["endpoint_count"] == 1


def test_delete_api_run_removes_record_and_artifacts_and_rejects_active_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    _seed_project()
    actor = {
        "id": "u-admin",
        "role": "admin",
        "nickname": "管理员",
        "username": "admin",
        "project_scope": "全部项目",
    }
    with connect() as db:
        api_automation_repo.create_api_run(
            db,
            run_id="apirun-finished",
            task_id="api_automation_run:apirun-finished",
            project_id="project-1",
            api_environment_id=None,
            script_ids=[],
            command_summary="uv run pytest",
            created_by="u-admin",
            status="failed",
        )
        api_automation_repo.create_api_run(
            db,
            run_id="apirun-active",
            task_id="api_automation_run:apirun-active",
            project_id="project-1",
            api_environment_id=None,
            script_ids=[],
            command_summary="uv run pytest",
            created_by="u-admin",
            status="running",
        )

    run_dir = tmp_path / "projects" / "project-1" / "api_automation" / "runs" / "apirun-finished"
    run_dir.mkdir(parents=True)
    (run_dir / "stdout.log").write_text("completed", encoding="utf-8")

    service.delete_api_run("project-1", "apirun-finished", actor)

    with connect() as db:
        assert api_automation_repo.find_api_run(db, "apirun-finished") is None
    assert not run_dir.exists()

    with pytest.raises(HTTPException) as exc_info:
        service.delete_api_run("project-1", "apirun-active", actor)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "API_RUN_ACTIVE"
    with connect() as db:
        assert api_automation_repo.find_api_run(db, "apirun-active") is not None


def test_update_api_test_case_set_changes_name_and_notes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    actor = {
        "id": "u-admin",
        "role": "admin",
        "nickname": "管理员",
        "username": "admin",
        "project_scope": "全部项目",
    }

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


def test_api_test_case_set_endpoint_count_matches_project_assets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoints(["apiend-1", "apiend-2"])
    actor = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}

    created = service.create_api_test_case_set(
        "project-1",
        ApiTestCaseSetIn(name="接口集", notes=""),
        actor,
    )
    listed = service.list_api_test_case_sets("project-1", actor)

    assert created["endpoint_count"] == 2
    assert created["case_count"] == 0
    assert listed[0]["endpoint_count"] == 2
    assert ApiTestCaseSetOut.model_validate(listed[0]).model_dump()["endpoint_count"] == 2
