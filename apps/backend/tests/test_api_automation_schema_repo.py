from pathlib import Path

import pytest

from app.core import settings
from app.core import db as db_core
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


def _seed_project() -> None:
    with connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, description, status, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("project-1", "项目一", "", "active", "u-admin"),
        )


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
            status="ready",
            tags=["login"],
            request={"method": "POST", "path": "/login"},
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

        cases = api_automation_repo.list_api_test_cases(db, "project-1", status="ready")
        script = api_automation_repo.find_script(db, script_id)
        run = api_automation_repo.find_api_run(db, run_id)

    assert cases[0]["id"] == case_id
    assert script["api_test_case_id"] == case_id
    assert api_automation_repo.loads_json(run["script_ids_json"], []) == [script_id]
