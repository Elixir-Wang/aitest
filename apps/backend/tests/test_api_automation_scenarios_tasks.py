from pathlib import Path

import pytest

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.schemas.api_automation import ApiScenarioIn, ApiScenarioStepIn, ApiScenarioStepsReplaceIn
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


def test_replace_validate_and_publish_scenario(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    with connect() as db:
        api_automation_repo.create_api_test_case(
            db,
            case_id="apitc-1",
            project_id="project-1",
            endpoint_id="apiend-1",
            source_test_case_id=None,
            generation_run_id=None,
            title="查询资料成功",
            priority="P1",
            coverage="positive",
            source="manual",
            preconditions=[],
            request={"method": "GET", "path": "/profile/{user_id}"},
            test_data={"user_id": {"value": "seed-user"}},
            expected={"status_code": 200},
            assertions=[{"type": "status_code", "expected": 200}],
            variables={},
            data_origin={},
            data_file_path="",
            notes="",
            created_by=ACTOR["id"],
        )
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="登录后查资料"), ACTOR)
    detail = service.replace_api_scenario_steps(
        "project-1",
        scenario["id"],
        ApiScenarioStepsReplaceIn(
            steps=[
                ApiScenarioStepIn(
                    api_test_case_id="apitc-1",
                    name="查资料",
                    bindings=[
                        {
                            "target": "/test_data/user_id/value",
                            "source": {"type": "environment", "name": "user_id"},
                        }
                    ],
                    extractors=[{"name": "profile_id", "source": "response.body", "expression": "$.id"}],
                )
            ]
        ),
        ACTOR,
    )

    validation = service.validate_api_scenario("project-1", scenario["id"], ACTOR)
    published = service.publish_api_scenario("project-1", scenario["id"], ACTOR)

    assert detail["steps"][0]["step_order"] == 0
    assert detail["steps"][0]["endpoint_id"] == "apiend-1"
    assert validation == {"valid": True, "errors": [], "warnings": []}
    assert published["status"] == "ready"
    assert published["revision"] == 1
    assert published["published_hash"]


def test_scenario_validation_rejects_forward_variable_reference(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="非法依赖"), ACTOR)
    service.create_api_scenario_step(
        "project-1",
        scenario["id"],
        ApiScenarioStepIn(
            endpoint_id="apiend-1",
            name="先使用后提取",
            bindings=[
                {
                    "target": "/request/query/user_id",
                    "source": {"type": "step_output", "step_id": "future-step", "variable": "user_id"},
                }
            ],
        ),
        ACTOR,
    )

    validation = service.validate_api_scenario("project-1", scenario["id"], ACTOR)

    assert validation["valid"] is False
    assert any("引用的步骤不存在" in error for error in validation["errors"])


def test_published_scenario_creates_collectable_run_artifact(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    with connect() as db:
        db.execute(
            """
            INSERT INTO api_test_environments (
              id, project_id, name, api_base_url, auth_type, created_by
            ) VALUES (?, ?, ?, ?, 'none', ?)
            """,
            ("apienv-1", "project-1", "测试环境", "https://api.example.test", ACTOR["id"]),
        )
        api_automation_repo.create_api_test_case(
            db,
            case_id="apitc-run",
            project_id="project-1",
            endpoint_id="apiend-1",
            source_test_case_id=None,
            generation_run_id=None,
            title="查询资料",
            priority="P1",
            coverage="positive",
            source="manual",
            preconditions=[],
            request={"method": "GET", "path": "/profile"},
            test_data={},
            expected={"status_code": 200},
            assertions=[{"type": "status_code", "expected": 200}],
            variables={},
            data_origin={},
            data_file_path="",
            notes="",
            created_by=ACTOR["id"],
        )
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="资料查询"), ACTOR)
    service.replace_api_scenario_steps(
        "project-1",
        scenario["id"],
        ApiScenarioStepsReplaceIn(steps=[ApiScenarioStepIn(api_test_case_id="apitc-run")]),
        ACTOR,
    )
    service.publish_api_scenario("project-1", scenario["id"], ACTOR)
    collection_calls = []
    monkeypatch.setattr(
        service,
        "collect_script_suite",
        lambda **kwargs: collection_calls.append(kwargs) or {"ok": True, "exitcode": 0, "stdout": "", "stderr": ""},
    )

    run = service.create_api_scenario_run("project-1", scenario["id"], "apienv-1", ACTOR)

    suite_path = storage.resolve_stored_path(run["execution_snapshot"]["suite_path"])
    test_file = storage.resolve_stored_path(run["execution_snapshot"]["test_file_path"])
    assert run["target_type"] == "scenario"
    assert run["target_ids"] == [scenario["id"]]
    assert test_file and test_file.exists()
    assert suite_path and (suite_path / "support" / "scenario.py").exists()
    assert collection_calls[0]["test_paths"] == [str(test_file.relative_to(suite_path))]

    monkeypatch.setattr(
        service,
        "run_script_suite",
        lambda **kwargs: {
            "status": "passed",
            "summary": {"total": 1, "passed": 1, "failed": 0},
            "error_message": "",
            "stdout_path": str(tmp_path / "stdout.txt"),
            "stderr_path": str(tmp_path / "stderr.txt"),
            "json_report_path": str(tmp_path / "report.json"),
            "exitcode": 0,
        },
    )
    completed = service.execute_api_run(run["id"])

    assert completed["status"] == "passed"
    assert completed["summary"]["passed"] == 1


def test_task_service_includes_api_automation_tasks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()

    tasks = task_service.list_running_tasks(ACTOR, project_id="project-1")
    source_types = {task["source_type"] for task in tasks}

    assert "api_automation_generation_run" in source_types
    assert "api_automation_run" in source_types
