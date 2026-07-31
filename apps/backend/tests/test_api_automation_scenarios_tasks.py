from pathlib import Path

import pytest

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.seed.seeds import seed_system_defaults
from app.schemas.api_automation import ApiScenarioIn, ApiScenarioStepIn, ApiScenarioStepsReplaceIn, ApiScenarioVersionSaveIn
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
    assert step["step_type"] == "api_request"
    assert step["control_config"] == {}
    assert detail["steps"][0]["extractors"] == [{"name": "user_id", "path": "$.id"}]


def test_endpoint_only_scenario_validates_and_publishes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="资料查询"), ACTOR)
    service.replace_api_scenario_steps(
        "project-1",
        scenario["id"],
        ApiScenarioStepsReplaceIn(
            steps=[
                ApiScenarioStepIn(
                    endpoint_id="apiend-1",
                    name="查询资料",
                    request_overrides={"request": {"query": {"expand": "roles"}}},
                    assertions=[{"type": "status_code", "expected": 200}],
                )
            ]
        ),
        ACTOR,
    )

    validation = service.validate_api_scenario("project-1", scenario["id"], ACTOR)
    published = service.publish_api_scenario("project-1", scenario["id"], ACTOR)
    with connect() as db:
        row = db.execute("SELECT published_snapshot_json FROM api_scenarios WHERE id = ?", (scenario["id"],)).fetchone()
        snapshot = api_automation_repo.loads_json(row["published_snapshot_json"], {})

    assert validation == {"valid": True, "errors": [], "warnings": []}
    assert published["steps"][0]["endpoint_id"] == "apiend-1"
    assert published["steps"][0]["api_test_case_id"] is None
    assert snapshot["steps"][0]["endpoint"] == {
        "id": "apiend-1",
        "method": "GET",
        "path": "/profile",
        "summary": "用户资料",
        "parameters": [],
        "request_body": {},
        "responses": {"200": {"description": "ok"}},
        "auth": {},
    }
    assert "case" not in snapshot["steps"][0]


def test_published_scenario_reports_and_confirms_endpoint_asset_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="资料查询"), ACTOR)
    service.replace_api_scenario_steps(
        "project-1",
        scenario["id"],
        ApiScenarioStepsReplaceIn(
            steps=[
                ApiScenarioStepIn(
                    endpoint_id="apiend-1",
                    name="查询资料",
                    assertions=[{"type": "status_code", "expected": 200}],
                )
            ]
        ),
        ACTOR,
    )
    service.publish_api_scenario("project-1", scenario["id"], ACTOR)
    with connect() as db:
        db.execute(
            """
            UPDATE api_endpoints
            SET path = ?, parameters_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                "/profiles/{user_id}",
                api_automation_repo.dumps_json([{"name": "user_id", "in": "path", "required": True}]),
                "apiend-1",
            ),
        )

    detail = service.get_api_scenario("project-1", scenario["id"], ACTOR)

    assert detail["asset_changes"] == [
        {
            "step_id": detail["steps"][0]["id"],
            "endpoint_id": "apiend-1",
            "change_type": "modified",
            "fields": ["path", "parameters"],
        }
    ]
    with pytest.raises(Exception) as error:
        service.publish_api_scenario("project-1", scenario["id"], ACTOR)
    assert error.value.detail["code"] == "API_SCENARIO_ASSET_CHANGES_UNCONFIRMED"

    republished = service.publish_api_scenario("project-1", scenario["id"], ACTOR, confirm_asset_changes=True)

    assert republished["revision"] == 2
    assert service.get_api_scenario("project-1", scenario["id"], ACTOR)["asset_changes"] == []


def test_scenario_revisions_include_orchestration_and_restore_as_new_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="资料查询"), ACTOR)
    first = service.replace_api_scenario_steps(
        "project-1",
        scenario["id"],
        ApiScenarioStepsReplaceIn(
            steps=[ApiScenarioStepIn(endpoint_id="apiend-1", name="查询资料", assertions=[{"type": "status_code", "expected": 200}])]
        ),
        ACTOR,
    )
    service.publish_api_scenario("project-1", scenario["id"], ACTOR)
    service.replace_api_scenario_steps(
        "project-1",
        scenario["id"],
        ApiScenarioStepsReplaceIn(
            steps=[
                ApiScenarioStepIn(
                    id=first["steps"][0]["id"],
                    endpoint_id="apiend-1",
                    name="查询资料并校验",
                    assertions=[{"type": "status_code", "expected": 200}],
                )
            ]
        ),
        ACTOR,
    )
    service.publish_api_scenario("project-1", scenario["id"], ACTOR)

    revisions = service.list_api_scenario_revisions("project-1", scenario["id"], ACTOR)
    restored = service.restore_api_scenario_revision("project-1", scenario["id"], 1, ACTOR)

    assert [item["revision"] for item in revisions] == [2, 1]
    assert revisions[0]["snapshot"]["steps"][0]["name"] == "查询资料并校验"
    assert restored["status"] == "ready"
    assert restored["revision"] == 3
    assert restored["steps"][0]["name"] == "查询资料"
    assert [item["revision"] for item in service.list_api_scenario_revisions("project-1", scenario["id"], ACTOR)] == [3, 2, 1]


def test_saving_versions_keeps_only_the_latest_five(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="资料查询"), ACTOR)

    for version in range(1, 7):
        saved = service.save_api_scenario_version(
            "project-1",
            scenario["id"],
            ApiScenarioVersionSaveIn(
                name=f"资料查询 {version}",
                steps=[
                    ApiScenarioStepIn(
                        endpoint_id="apiend-1",
                        name=f"查询资料 {version}",
                        assertions=[{"type": "status_code", "expected": 200}],
                    )
                ],
            ),
            ACTOR,
        )
        assert saved["revision"] == version

    revisions = service.list_api_scenario_revisions("project-1", scenario["id"], ACTOR)

    assert [item["revision"] for item in revisions] == [6, 5, 4, 3, 2]
    assert revisions[0]["snapshot"]["steps"][0]["name"] == "查询资料 6"


def test_scenario_utility_steps_validate_with_supported_control_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="轮询资料"), ACTOR)
    service.replace_api_scenario_steps(
        "project-1",
        scenario["id"],
        ApiScenarioStepsReplaceIn(
            steps=[
                ApiScenarioStepIn(
                    id="assign-1",
                    step_type="assign",
                    name="设置租户",
                    control_config={"name": "tenant", "source": {"type": "literal", "value": "acme"}},
                ),
                ApiScenarioStepIn(
                    step_type="condition",
                    name="校验租户",
                    control_config={
                        "source": {"type": "step_output", "step_id": "assign-1", "variable": "tenant"},
                        "operator": "equals",
                        "expected": "acme",
                    },
                ),
                ApiScenarioStepIn(step_type="wait", name="固定等待", control_config={"duration_ms": 10}),
                ApiScenarioStepIn(
                    step_type="poll",
                    endpoint_id="apiend-1",
                    name="轮询资料",
                    control_config={"interval_ms": 10, "timeout_ms": 100},
                    assertions=[{"type": "status_code", "expected": 200}],
                ),
            ]
        ),
        ACTOR,
    )

    assert service.validate_api_scenario("project-1", scenario["id"], ACTOR)["valid"] is True


def test_scenario_run_result_path_is_persisted_and_exposed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    result_path = tmp_path / "scenario-result.json"
    result_path.write_text('{"scenario_id":"scenario-1","status":"passed","steps":[]}', encoding="utf-8")
    with connect() as db:
        db.execute(
            "UPDATE api_automation_runs SET target_type = 'scenario', target_ids_json = '[\"scenario-1\"]' WHERE id = 'apirun-1'"
        )
        api_automation_repo.update_api_run(
            db,
            "apirun-1",
            status="passed",
            scenario_result_path=str(result_path),
            finished=True,
        )

    run = service.get_api_run("project-1", "apirun-1", ACTOR)
    result = service.get_api_scenario_run_result("project-1", "apirun-1", ACTOR)

    assert run["scenario_result_path"] == str(result_path)
    assert result == {"scenario_id": "scenario-1", "status": "passed", "steps": []}


def test_legacy_case_backed_scenario_step_backfills_endpoint_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    with connect() as db:
        api_automation_repo.create_api_test_case(
            db,
            case_id="apitc-legacy",
            project_id="project-1",
            endpoint_id="apiend-1",
            source_test_case_id=None,
            generation_run_id=None,
            title="历史资料查询",
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
        db.execute(
            "INSERT INTO api_scenarios (id, project_id, name, created_by) VALUES ('scenario-legacy', 'project-1', '历史场景', ?)",
            (ACTOR["id"],),
        )
        db.execute(
            """
            INSERT INTO api_scenario_steps (id, scenario_id, project_id, endpoint_id, api_test_case_id, name)
            VALUES ('step-legacy', 'scenario-legacy', 'project-1', NULL, 'apitc-legacy', '历史步骤')
            """
        )
        seed_system_defaults(db)
        seed_system_defaults(db)
        migrated = db.execute("SELECT endpoint_id, api_test_case_id FROM api_scenario_steps WHERE id = 'step-legacy'").fetchone()

    assert migrated["endpoint_id"] == "apiend-1"
    assert migrated["api_test_case_id"] == "apitc-legacy"


def test_api_request_step_requires_project_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="非法接口"), ACTOR)

    with pytest.raises(Exception) as error:
        service.create_api_scenario_step(
            "project-1",
            scenario["id"],
            ApiScenarioStepIn(endpoint_id="missing-endpoint"),
            ACTOR,
        )

    assert error.value.detail["code"] == "API_ENDPOINT_INVALID"


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


def test_draft_scenario_creates_one_time_run_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()
    with connect() as db:
        db.execute(
            """
            INSERT INTO api_test_environments (
              id, project_id, name, api_base_url, auth_type, created_by
            ) VALUES (?, ?, ?, ?, 'none', ?)
            """,
            ("apienv-draft", "project-1", "测试环境", "https://api.example.test", ACTOR["id"]),
        )
    scenario = service.create_api_scenario("project-1", ApiScenarioIn(name="草稿资料查询"), ACTOR)
    service.replace_api_scenario_steps(
        "project-1",
        scenario["id"],
        ApiScenarioStepsReplaceIn(
            steps=[
                ApiScenarioStepIn(
                    endpoint_id="apiend-1",
                    name="查询资料",
                    assertions=[{"type": "status_code", "expected": 200}],
                )
            ]
        ),
        ACTOR,
    )
    monkeypatch.setattr(service, "collect_script_suite", lambda **kwargs: {"ok": True, "exitcode": 0, "stdout": "", "stderr": ""})

    run = service.create_api_scenario_run(
        "project-1",
        scenario["id"],
        "apienv-draft",
        ACTOR,
        source="draft",
    )

    assert run["execution_snapshot"]["scenario"]["source"] == "draft"
    assert run["execution_snapshot"]["scenario"]["revision"] == 1
    assert service.get_api_scenario("project-1", scenario["id"], ACTOR)["status"] == "draft"


def test_task_service_includes_api_automation_tasks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_and_runs()

    tasks = task_service.list_running_tasks(ACTOR, project_id="project-1")
    source_types = {task["source_type"] for task in tasks}

    assert "api_automation_generation_run" in source_types
    assert "api_automation_run" in source_types
