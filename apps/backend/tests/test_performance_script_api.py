from pathlib import Path
import json

import pytest
from fastapi import HTTPException

from app.core import db as db_core
from app.core import settings
from app.core.db import connect
from app.core.environment_credentials import encrypt_api_environment_secret
from app.repositories import api_automation_repo
from app.schemas.performance_test import PerformanceTestCreateIn
from app.seed.init_db import init_db
from app.api.v1 import performance_runs
from app.services.performance_testing import script_service, service


ADMIN = {"id": "u-admin", "role": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    monkeypatch.setattr(db_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_core, "DB_PATH", tmp_path / "test.db")
    init_db()


def _create_test(project_id: str = "project-1") -> dict:
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', 'u-admin')",
            (project_id, project_id),
        )
        api_automation_repo.upsert_endpoint(
            db,
            endpoint_id=f"endpoint-{project_id}",
            project_id=project_id,
            document_id=None,
            method="GET",
            path="/api/items",
            normalized_path="/api/items",
            summary="items",
            description="",
            tags=[],
            parameters=[],
            request_body={},
            responses={"200": {"description": "ok"}},
            auth={},
            source={},
            created_by="u-admin",
        )
        api_automation_repo.create_api_environment(
            db,
            environment_id=f"environment-{project_id}",
            project_id=project_id,
            linked_ui_environment_id=None,
            name="local",
            api_base_url="http://127.0.0.1:8000",
            username="",
            password_encrypted="",
            password_hash="",
            auth_type="none",
            auth_config={},
            variables={},
            default_headers={},
            timeout_seconds=10,
            verify_ssl=True,
            auth_state_ttl_seconds=3600,
            description="",
            created_by="u-admin",
        )
    return service.create_performance_test(
        project_id,
        PerformanceTestCreateIn(
            name="items performance",
            endpoint_id=f"endpoint-{project_id}",
            api_environment_id=f"environment-{project_id}",
        ),
        ADMIN,
    )


def _create_scenario_test() -> dict:
    _create_test()
    snapshot = {
        "id": "scenario-project-1",
        "project_id": "project-1",
        "name": "查询条目场景",
        "variables": {"tenant": "default"},
        "revision": 3,
        "steps": [
            {
                "id": "step-assign",
                "step_type": "assign",
                "step_order": 0,
                "name": "设置租户",
                "control_config": {"name": "tenant", "source": {"type": "literal", "value": "tenant-a"}},
                "on_failure": "stop",
                "enabled": True,
            },
            {
                "id": "step-request",
                "step_type": "api_request",
                "step_order": 1,
                "name": "查询条目",
                "endpoint_id": "endpoint-project-1",
                "endpoint": {
                    "id": "endpoint-project-1",
                    "method": "GET",
                    "path": "/api/items/{item_id}",
                    "summary": "items",
                    "parameters": [],
                    "request_body": {},
                    "responses": {"200": {"description": "ok"}},
                    "auth": {},
                },
                "request_overrides": {"path_parameters": {"item_id": "fixed"}},
                "bindings": [
                    {"target": "/request/query_parameters/tenant", "source": {"type": "scenario", "name": "tenant"}}
                ],
                "extractors": [{"name": "item_id", "source": "response.body", "expression": "$.id"}],
                "assertions": [{"type": "status_code", "expected": 200}],
                "control_config": {},
                "on_failure": "continue",
                "enabled": True,
            },
            {
                "id": "step-condition",
                "step_type": "condition",
                "step_order": 2,
                "name": "校验提取结果",
                "control_config": {
                    "source": {"type": "step_output", "step_id": "step-request", "variable": "item_id"},
                    "operator": "exists",
                },
                "on_failure": "stop",
                "enabled": True,
            },
            {
                "id": "step-wait",
                "step_type": "wait",
                "step_order": 3,
                "name": "短暂停顿",
                "control_config": {"duration_ms": 10},
                "on_failure": "always_run",
                "enabled": True,
            },
        ],
    }
    with connect() as db:
        db.execute(
            """
            INSERT INTO api_scenarios (
              id, project_id, api_environment_id, name, description, status,
              variables_json, revision, published_snapshot_json, published_hash,
              created_by, updated_by
            )
            VALUES (?, ?, ?, ?, '', 'ready', ?, 3, ?, '', 'u-admin', 'u-admin')
            """,
            (
                "scenario-project-1",
                "project-1",
                "environment-project-1",
                "查询条目场景",
                json.dumps(snapshot["variables"], ensure_ascii=False),
                json.dumps(snapshot, ensure_ascii=False),
            ),
        )
    return service.create_performance_test(
        "project-1",
        PerformanceTestCreateIn(
            name="scenario performance",
            target_type="scenario",
            scenario_id="scenario-project-1",
            api_environment_id="environment-project-1",
        ),
        ADMIN,
    )


def test_scenario_script_generation_uses_current_saved_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_scenario_test()

    generated = script_service.generate_script("project-1", performance_test["id"], ADMIN)

    assert generated["validation_status"] == "valid"
    assert generated["plan"]["target_type"] == "scenario"
    assert generated["plan"]["scenario_id"] == "scenario-project-1"
    assert generated["plan"]["scenario_name"] == "查询条目场景"
    assert [step["step_type"] for step in generated["plan"]["steps"]] == [
        "assign",
        "api_request",
        "condition",
        "wait",
    ]
    assert generated["plan"]["steps"][1]["request"]["name"] == "02 GET /api/items/{item_id}"
    assert "SCENARIO 查询条目场景" in generated["code"]
    assert "events.request.fire" in generated["code"]
    assert "def _run_scenario_step" in generated["code"]
    assert generated["runtime_preview"]["scenario"]["revision"] == 3


def test_scenario_script_generation_rejects_missing_current_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_scenario_test()
    with connect() as db:
        db.execute(
            "UPDATE api_scenarios SET published_snapshot_json = '{}' WHERE id = 'scenario-project-1'"
        )

    with pytest.raises(HTTPException) as exc_info:
        script_service.generate_script("project-1", performance_test["id"], ADMIN)

    assert exc_info.value.detail["code"] == "PERFORMANCE_SCENARIO_VERSION_MISSING"


def test_script_generation_overwrites_single_current_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_test()

    first = script_service.generate_script("project-1", performance_test["id"], ADMIN)
    second = script_service.generate_script("project-1", performance_test["id"], ADMIN)

    assert first["validation_status"] == "valid"
    assert second["id"] == first["id"]
    assert "version" not in second
    assert script_service.get_current_script("project-1", performance_test["id"], ADMIN)["id"] == first["id"]
    with connect() as db:
        rows = db.execute(
            "SELECT id FROM performance_test_scripts WHERE performance_test_id = ?",
            (performance_test["id"],),
        ).fetchall()
    assert [row["id"] for row in rows] == [first["id"]]


def test_valid_script_can_be_edited_in_place(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_test()
    generated = script_service.generate_script("project-1", performance_test["id"], ADMIN)

    updated = script_service.update_script_configuration(
        "project-1",
        performance_test["id"],
        generated["id"],
        {"request": {"headers": {"X-Test": "changed"}}},
        ADMIN,
    )

    assert updated["id"] == generated["id"]
    assert updated["validation_status"] == "valid"


def test_script_edit_rerenders_and_revalidates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_test()
    generated = script_service.generate_script("project-1", performance_test["id"], ADMIN)

    updated = script_service.update_script_configuration(
        "project-1",
        performance_test["id"],
        generated["id"],
        {"request": {"headers": {"X-Test": "changed"}, "body": {"name": "updated"}}},
        ADMIN,
    )

    assert updated["generation_source"] == "user_edited"
    assert updated["plan"]["request"]["headers"] == {"X-Test": "changed"}
    assert updated["validation_status"] == "valid"
    assert updated["validation_result"]["valid"] is True
    assert "changed" in updated["code"]


def test_script_generation_keeps_all_headers_and_shows_runtime_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_test()
    with connect() as db:
        db.execute(
            "UPDATE api_test_environments SET auth_type = ?, auth_config_json = ? WHERE id = ?",
            (
                "cybertron_agent",
                api_automation_repo.dumps_json(
                    {
                        "username": "robot-user",
                        "cybertron_robot_key_encrypted": encrypt_api_environment_secret("real-key"),
                        "cybertron_robot_token_encrypted": encrypt_api_environment_secret("real-token"),
                    }
                ),
                "environment-project-1",
            ),
        )
        db.execute(
            "UPDATE performance_tests SET request_config_json = ? WHERE id = ?",
            (
                api_automation_repo.dumps_json(
                    {
                        "headers": {
                            "X-Business": "keep",
                            "cybertron-robot-key": "bad-key",
                            "cybertron-robot-token": "bad-token",
                            "username": "bad-user",
                        }
                    }
                ),
                performance_test["id"],
            ),
        )

    generated = script_service.generate_script("project-1", performance_test["id"], ADMIN)

    assert generated["plan"]["request"]["headers"] == {
        "X-Business": "keep",
        "username": "robot-user",
        "cybertron-robot-key": "real-key",
        "cybertron-robot-token": "real-token",
    }
    assert "real-key" in generated["code"]
    assert "real-token" in generated["code"]
    assert generated["runtime_preview"]["plan_headers"] == generated["plan"]["request"]["headers"]
    assert generated["runtime_preview"]["env_headers"] == {
        "username": "robot-user",
        "cybertron-robot-key": "real-key",
        "cybertron-robot-token": "real-token",
    }
    assert generated["runtime_preview"]["request"]["headers"] == generated["plan"]["request"]["headers"]


def test_script_lookup_is_project_isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_test("project-1")
    _create_test("project-2")
    generated = script_service.generate_script("project-1", performance_test["id"], ADMIN)

    with pytest.raises(HTTPException) as exc_info:
        script_service.get_current_script("project-2", performance_test["id"], ADMIN)

    assert exc_info.value.status_code == 404


def test_create_run_does_not_require_source_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_test()
    generated = script_service.generate_script("project-1", performance_test["id"], ADMIN)
    with connect() as db:
        api_automation_repo.delete_endpoint(db, "endpoint-project-1")

    captured = {}

    def create_run_session(**kwargs):
        captured.update(kwargs)
        return "perfrun-1"

    monkeypatch.setattr(performance_runs.headless_worker, "create_run_session", create_run_session)

    result = performance_runs.create_performance_run(
        "project-1",
        performance_test["id"],
        {"script_id": generated["id"]},
        ADMIN,
    )

    assert result == {"id": "perfrun-1", "status": "created"}
    assert captured["script_code"] == generated["code"]
