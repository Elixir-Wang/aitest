from pathlib import Path

import pytest

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.schemas.api_automation import ApiScenarioIn, ApiScenarioStepIn
from app.services import task_service
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


def _seed_project_endpoint_and_runs() -> None:
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
            method="GET",
            path="/profile",
            normalized_path="/profile",
            summary="用户资料",
            description="",
            tags=["user"],
            parameters=[],
            request_body={},
            responses={"200": {"description": "ok"}},
            auth={},
            source={},
            created_by=ACTOR["id"],
        )
        api_automation_repo.create_generation_run(
            db,
            run_id="apigen-1",
            task_id="api_automation_generation:apigen-1",
            project_id="project-1",
            api_environment_id=None,
            endpoint_ids=["apiend-1"],
            source_test_case_ids=[],
            generation_goal="生成资料接口用例",
            options={},
            created_by=ACTOR["id"],
            status="running",
        )
        api_automation_repo.create_api_run(
            db,
            run_id="apirun-1",
            task_id="api_automation_run:apirun-1",
            project_id="project-1",
            api_environment_id=None,
            script_ids=[],
            command_summary="uv run pytest tests",
            created_by=ACTOR["id"],
            status="running",
        )


def test_create_scenario_and_steps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()

    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="登录后查资料"), ACTOR)
    step = service.create_api_scenario_step(
        "project-1",
        scenario["id"],
        ApiScenarioStepIn(
            endpoint_id="apiend-1",
            step_order=1,
            name="查资料",
            extractors=[{"name": "user_id", "path": "$.id"}],
            assertions=[{"type": "status_code", "expected": 200}],
        ),
        ACTOR,
    )
    detail = service.get_api_scenario("project-1", scenario["id"], ACTOR)

    assert step["endpoint_id"] == "apiend-1"
    assert detail["steps"][0]["extractors"] == [{"name": "user_id", "path": "$.id"}]


def test_task_service_includes_api_automation_tasks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()

    tasks = task_service.list_running_tasks(ACTOR, project_id="project-1")
    source_types = {task["source_type"] for task in tasks}

    assert "api_automation_generation_run" in source_types
    assert "api_automation_run" in source_types
