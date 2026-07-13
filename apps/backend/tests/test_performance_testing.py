from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core import db as db_core
from app.core import settings
from app.core.db import connect
from app.repositories import api_automation_repo
from app.schemas.performance_test import (
    PerformanceLoadConfig,
    PerformanceRequestPreviewIn,
    PerformanceTestCreateIn,
    PerformanceTestUpdateIn,
)
from app.seed.init_db import init_db
from app.services.performance_testing import service


ADMIN = {"id": "u-admin", "role": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    monkeypatch.setattr(db_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_core, "DB_PATH", tmp_path / "test.db")
    init_db()


def _seed_project_assets(project_id: str = "project-1") -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', 'u-admin')",
            (project_id, f"项目-{project_id}"),
        )
        api_automation_repo.upsert_endpoint(
            db,
            endpoint_id=f"endpoint-{project_id}",
            project_id=project_id,
            document_id=None,
            method="GET",
            path="/api/items/{item_id}",
            normalized_path="/api/items/{item_id}",
            summary="查询条目",
            description="",
            tags=[],
            parameters=[
                {"name": "item_id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}},
                {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                {"name": "Authorization", "in": "header", "required": True, "schema": {"type": "string"}},
            ],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["name"],
                            "properties": {"name": {"type": "string"}, "optional": {"type": "string"}},
                        }
                    }
                }
            },
            responses={"200": {"description": "ok"}, "201": {"description": "created"}},
            auth={},
            source={},
            created_by="u-admin",
        )
        api_automation_repo.create_api_environment(
            db,
            environment_id=f"environment-{project_id}",
            project_id=project_id,
            linked_ui_environment_id=None,
            name="测试环境",
            api_base_url="https://example.test",
            username="",
            password_encrypted="",
            password_hash="",
            auth_type="none",
            auth_config={},
            variables={},
            default_headers={},
            timeout_seconds=30,
            verify_ssl=True,
            auth_state_ttl_seconds=86400,
            description="",
            created_by="u-admin",
        )


def _payload(project_id: str = "project-1", **overrides) -> PerformanceTestCreateIn:
    values = {
        "name": "查询条目性能测试",
        "endpoint_id": f"endpoint-{project_id}",
        "api_environment_id": f"environment-{project_id}",
        "request_config": {"path_parameters": {"item_id": "${sequence}"}},
        "load_config": {
            "users": 20,
            "spawn_rate": 5,
            "measurement_duration_seconds": 120,
            "wait_time_min_seconds": 1,
            "wait_time_max_seconds": 3,
            "request_timeout_seconds": 10,
        },
        "success_rules": [{"kind": "status_code", "status_codes": [200]}],
    }
    values.update(overrides)
    return PerformanceTestCreateIn.model_validate(values)


def test_load_config_rejects_zero_or_reversed_wait_time() -> None:
    with pytest.raises(ValidationError):
        PerformanceLoadConfig(wait_time_min_seconds=0, wait_time_max_seconds=1)
    with pytest.raises(ValidationError):
        PerformanceLoadConfig(wait_time_min_seconds=2, wait_time_max_seconds=1)


def test_create_and_update_performance_test(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_assets()

    created = service.create_performance_test("project-1", _payload(), ADMIN)

    assert created["endpoint_method"] == "GET"
    assert created["endpoint_path"] == "/api/items/{item_id}"
    assert created["environment_name"] == "测试环境"
    assert created["request_config"]["path_parameters"] == {"item_id": "${sequence}"}
    assert created["load_config"]["measurement_duration_seconds"] == 120

    updated = service.update_performance_test(
        "project-1",
        created["id"],
        PerformanceTestUpdateIn(name="查询条目基线", performance_goal={"max_p95_response_time_ms": 500}),
        ADMIN,
    )

    assert updated["name"] == "查询条目基线"
    assert updated["performance_goal"] == {"max_p95_response_time_ms": 500.0}
    with connect() as db:
        db.execute(
            """
            INSERT INTO performance_test_scripts (
              id, performance_test_id, project_id, version, generation_source,
              template_version, input_hash, code, validation_status
            ) VALUES ('perfscript-1', ?, 'project-1', 1, 'default_plan', 'v1', 'hash', 'code', 'confirmed')
            """,
            (created["id"],),
        )
        db.execute(
            """
            INSERT INTO performance_test_runs (
              id, performance_test_id, script_id, project_id, task_id, status,
              started_by, goal_result_json
            ) VALUES ('perfrun-1', ?, 'perfscript-1', 'project-1', 'performance_test_run:perfrun-1',
                      'completed', 'u-admin', '{"status":"passed"}')
            """,
            (created["id"],),
        )
    listed = service.list_performance_tests("project-1", ADMIN)[0]
    assert listed["id"] == created["id"]
    assert listed["latest_run_status"] == "completed"
    assert listed["latest_goal_status"] == "passed"
    assert listed["latest_run_at"] is not None


def test_default_success_codes_come_from_openapi(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_assets()

    created = service.create_performance_test(
        "project-1",
        PerformanceTestCreateIn(
            name="默认成功规则",
            endpoint_id="endpoint-project-1",
            api_environment_id="environment-project-1",
        ),
        ADMIN,
    )

    assert created["success_rules"] == [{"kind": "status_code", "status_codes": [200, 201]}]


def test_request_preview_merges_openapi_and_source_case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_assets()
    with connect() as db:
        api_automation_repo.create_api_test_case(
            db,
            case_id="case-1",
            project_id="project-1",
            endpoint_id="endpoint-project-1",
            source_test_case_id=None,
            generation_run_id=None,
            title="指定数据",
            priority="P1",
            coverage="positive",
            source="manual",
            preconditions=[],
            request={"query": {"page": 3}, "headers": {"X-Trace": "case"}, "body": {"name": "case-name"}},
            test_data={"item_id": {"value": "${sequence}"}},
            expected={"status_code": 201},
            assertions=[{"type": "status_code", "expected": 201}],
            variables={},
            data_origin={},
            data_file_path="",
            notes="",
            created_by="u-admin",
        )

    preview = service.preview_performance_request(
        "project-1",
        PerformanceRequestPreviewIn(endpoint_id="endpoint-project-1", source_api_test_case_id="case-1"),
        ADMIN,
    )

    assert preview["request_config"]["path_parameters"] == {"item_id": "${sequence}"}
    assert preview["request_config"]["query_parameters"] == {"page": 3}
    assert preview["request_config"]["headers"] == {"X-Trace": "case"}
    assert preview["request_config"]["body"] == {"name": "case-name"}
    assert preview["success_rules"] == [{"kind": "status_code", "status_codes": [201]}]
    assert preview["provenance"]["body"] == "api_test_case"
    assert any("Authorization" in warning for warning in preview["warnings"])


def test_create_rejects_cross_project_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_assets("project-1")
    _seed_project_assets("project-2")

    with pytest.raises(HTTPException) as exc_info:
        service.create_performance_test(
            "project-1",
            _payload(api_environment_id="environment-project-2"),
            ADMIN,
        )

    assert exc_info.value.detail["code"] == "PERFORMANCE_ENVIRONMENT_INVALID"


def test_sensitive_headers_must_come_from_api_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_assets()

    with pytest.raises(HTTPException) as exc_info:
        service.create_performance_test(
            "project-1",
            _payload(request_config={"headers": {"Authorization": "Bearer unsafe"}}),
            ADMIN,
        )

    assert exc_info.value.detail["code"] == "PERFORMANCE_SENSITIVE_HEADER_OVERRIDE"


def test_performance_script_state_excludes_running(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with connect() as db:
        table = db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'performance_test_scripts'"
        ).fetchone()

    assert table is not None
    assert "pending_confirmation" in table["sql"]
    assert "'running'" not in table["sql"]
