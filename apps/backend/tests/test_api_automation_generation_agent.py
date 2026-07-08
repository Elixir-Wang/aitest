from pathlib import Path

import pytest

from app.agents.api_automation.schemas import ApiAutomationGenerationResult, ApiGeneratedCase
from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.schemas.api_automation import ApiAutomationGenerateIn
from app.services.api_automation import service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    project_root = data_dir / "projects"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", project_root)
    monkeypatch.setattr(db_core, "DATA_DIR", data_dir)
    monkeypatch.setattr(db_core, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", project_root)
    init_db()


def _seed_project_endpoint() -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
            ("project-1", "测试项目", ACTOR["id"]),
        )
        api_automation_repo.upsert_endpoint(
            db,
            endpoint_id="apiend-1",
            project_id="project-1",
            document_id=None,
            method="POST",
            path="/login",
            normalized_path="/login",
            summary="登录",
            description="",
            tags=["auth"],
            parameters=[],
            request_body={"content": {"application/json": {"schema": {"type": "object"}}}},
            responses={"200": {"description": "ok"}},
            auth={},
            source={"source_type": "manual"},
            created_by=ACTOR["id"],
        )


def test_execute_generation_run_saves_ready_and_needs_input_cases(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()

    def fake_generate_api_test_cases(input_data):
        return ApiAutomationGenerationResult(
            summary="生成 2 条",
            cases=[
                ApiGeneratedCase(
                    title="登录成功",
                    priority="P1",
                    endpoint_id="apiend-1",
                    request={"method": "POST", "path": "/login", "body": {"username": "demo", "password": "demo"}},
                    expected={"status_code": 200},
                    assertions=[{"type": "status_code", "expected": 200}],
                    status="ready",
                ),
                ApiGeneratedCase(
                    title="登录缺少密码",
                    priority="P2",
                    endpoint_id="apiend-1",
                    request={"method": "POST", "path": "/login", "body": {"username": "demo"}},
                    expected={"status_code": 400},
                    assertions=[{"type": "status_code", "expected": 400}],
                    status="needs_input",
                ),
            ],
        )

    monkeypatch.setattr(service.api_generation_agent_service, "generate_api_test_cases", fake_generate_api_test_cases)

    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1"], generation_goal="覆盖登录", generate_code=False),
        ACTOR,
    )
    result = service.execute_generation_run(created["id"])

    with connect() as db:
        run = api_automation_repo.find_generation_run(db, created["id"])
        cases = api_automation_repo.list_api_test_cases(db, "project-1")

    assert result["status"] == "completed"
    assert run["status"] == "completed"
    assert len(cases) == 2
    assert {case["status"] for case in cases} == {"ready", "needs_input"}
    assert api_automation_repo.loads_json(run["result_summary_json"], {})["needs_input_count"] == 1
