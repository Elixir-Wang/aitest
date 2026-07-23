from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core import db as db_core
from app.core import settings
from app.core.db import connect
from app.repositories import api_automation_repo
from app.schemas.performance_test import (
    PerformanceCircuitBreaker,
    PerformanceDataConfig,
    PerformanceLoadConfig,
    PerformanceLoadStage,
    PerformanceRequestPreviewIn,
    PerformanceTestCreateIn,
    PerformanceTestUpdateIn,
)
from app.seed.init_db import init_db
from app.services.performance_testing import run_repo, service


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
                {"name": "limit", "in": "query", "required": True, "schema": {"type": "integer", "minimum": 5}},
                {"name": "Authorization", "in": "header", "required": True, "schema": {"type": "string"}},
                {
                    "name": "cybertron-robot-key",
                    "in": "header",
                    "required": True,
                    "schema": {"type": "string", "example": "robot-key-example"},
                },
                {
                    "name": "cybertron-robot-token",
                    "in": "header",
                    "required": True,
                    "schema": {"type": "string", "enum": ["robot-token-example"]},
                },
            ],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["name", "count", "tags"],
                            "properties": {
                                "name": {"type": "string", "example": "mock-name"},
                                "count": {"type": "integer", "minimum": 2},
                                "tags": {"type": "array", "items": {"type": "string", "enum": ["smoke"]}},
                                "optional": {"type": "string"},
                            },
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


def test_load_config_supports_fixed_and_ascending_stage_modes() -> None:
    fixed = PerformanceLoadConfig(mode="fixed")
    gradient = PerformanceLoadConfig(
        mode="gradient",
        stages=[
            PerformanceLoadStage(name="阶段 1", target_users=10, spawn_rate=2, hold_seconds=60, order=0),
            PerformanceLoadStage(name="阶段 2", target_users=50, spawn_rate=5, hold_seconds=120, order=1),
        ],
    )

    assert fixed.stages == []
    assert [stage.target_users for stage in gradient.stages] == [10, 50]


def test_load_config_rejects_descending_gradient_but_allows_spike_recovery() -> None:
    with pytest.raises(ValidationError):
        PerformanceLoadConfig(
            mode="gradient",
            stages=[
                {"name": "高位", "target_users": 100, "spawn_rate": 10, "hold_seconds": 60, "order": 0},
                {"name": "回落", "target_users": 20, "spawn_rate": 10, "hold_seconds": 60, "order": 1},
            ],
        )

    spike = PerformanceLoadConfig(
        mode="spike",
        stages=[
            {"name": "正常", "target_users": 20, "spawn_rate": 5, "hold_seconds": 60, "order": 0},
            {"name": "峰值", "target_users": 200, "spawn_rate": 100, "hold_seconds": 30, "order": 1},
            {"name": "恢复", "target_users": 20, "spawn_rate": 100, "hold_seconds": 60, "order": 2},
        ],
    )

    assert spike.stages[-1].target_users == 20


def test_performance_data_and_circuit_breaker_contracts() -> None:
    data = PerformanceDataConfig(
        source="json",
        selection_strategy="random",
        json_rows=[{"user_id": 1}, {"user_id": 2}],
    )
    breaker = PerformanceCircuitBreaker(
        enabled=True,
        window_seconds=10,
        max_fail_ratio=0.5,
        consecutive_windows=3,
    )

    assert data.selection_strategy == "random"
    assert len(data.json_rows) == 2
    assert breaker.max_fail_ratio == 0.5


def test_csv_data_is_persisted_with_the_performance_test(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_assets()

    created = service.create_performance_test(
        "project-1",
        _payload(
            name="CSV 参数化性能测试",
            data_config={
                "source": "csv",
                "selection_strategy": "sequential_loop",
                "csv_file_name": "users.csv",
                "json_rows": [{"user_id": "1", "name": "Alice"}, {"user_id": "2", "name": "Bob"}],
            },
        ),
        ADMIN,
    )

    stored_path = settings.PROJECT_FILE_STORAGE_ROOT / created["data_config"]["csv_file_path"]
    assert stored_path.is_file()
    assert "Alice" in stored_path.read_text(encoding="utf-8-sig")


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
    listed = service.list_performance_tests("project-1", ADMIN)[0]
    assert listed["id"] == created["id"]
    assert listed["latest_run_status"] == ""
    assert listed["latest_goal_status"] == ""
    assert listed["latest_run_at"] is None


def test_delete_performance_test_rejects_active_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_assets()
    created = service.create_performance_test("project-1", _payload(), ADMIN)

    with connect() as db:
        db.execute(
            """
            INSERT INTO performance_test_scripts (
              id, performance_test_id, project_id, version, generation_source,
              template_version, input_hash, code, validation_status
            ) VALUES (?, ?, ?, 1, 'default_plan', 'v1', 'hash', 'code', 'confirmed')
            """,
            ("perfscript-1", created["id"], "project-1"),
        )
        run_repo.create_run(
            db,
            run_id="perfrun-1",
            project_id="project-1",
            performance_test_id=created["id"],
            script_id="perfscript-1",
            load_config={},
            runtime_config={},
            created_by="u-admin",
        )
        run_repo.update_run_status(db, "perfrun-1", "starting")
        run_repo.update_run_status(db, "perfrun-1", "running")

    with pytest.raises(HTTPException) as exc_info:
        service.delete_performance_test("project-1", created["id"], ADMIN)

    assert exc_info.value.detail["code"] == "PERFORMANCE_TEST_RUN_ACTIVE"
    with connect() as db:
        assert db.execute("SELECT id FROM performance_tests WHERE id = ?", (created["id"],)).fetchone() is not None


def test_delete_performance_test_removes_all_run_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_assets()
    created = service.create_performance_test("project-1", _payload(), ADMIN)
    run_dir = settings.PROJECT_FILE_STORAGE_ROOT / "project-1" / "performance_testing" / "runs" / "perfrun-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result_stats.csv").write_text("history", encoding="utf-8")

    with connect() as db:
        db.execute(
            """
            INSERT INTO performance_test_scripts (
              id, performance_test_id, project_id, version, generation_source,
              template_version, input_hash, code, validation_status
            ) VALUES (?, ?, ?, 1, 'default_plan', 'v1', 'hash', 'code', 'confirmed')
            """,
            ("perfscript-1", created["id"], "project-1"),
        )
        run_repo.create_run(
            db,
            run_id="perfrun-1",
            project_id="project-1",
            performance_test_id=created["id"],
            script_id="perfscript-1",
            load_config={},
            runtime_config={},
            created_by="u-admin",
        )
        run_repo.update_run_status(db, "perfrun-1", "starting")
        run_repo.update_run_status(db, "perfrun-1", "running")
        run_repo.update_run_status(db, "perfrun-1", "completed")

    service.delete_performance_test("project-1", created["id"], ADMIN)

    with connect() as db:
        assert db.execute("SELECT id FROM performance_test_runs WHERE id = 'perfrun-1'").fetchone() is None
    assert not run_dir.exists()


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


def test_performance_contract_rejects_removed_source_case_field() -> None:
    with pytest.raises(ValidationError):
        PerformanceTestCreateIn.model_validate(
            {
                "name": "来源字段已删除",
                "endpoint_id": "endpoint-1",
                "api_environment_id": "environment-1",
                "source_api_test_case_id": "case-1",
            }
        )

    with pytest.raises(ValidationError):
        PerformanceRequestPreviewIn.model_validate(
            {"endpoint_id": "endpoint-1", "source_api_test_case_id": "case-1"}
        )


def test_performance_table_does_not_store_source_case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)

    with connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(performance_tests)").fetchall()}

    assert "source_api_test_case_id" not in columns


def test_request_preview_uses_schema_mock_and_shows_cybertron_headers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_assets()

    preview = service.preview_performance_request(
        "project-1",
        PerformanceRequestPreviewIn(endpoint_id="endpoint-project-1"),
        ADMIN,
    )

    assert preview["request_config"]["path_parameters"] == {"item_id": "${uuid}"}
    assert preview["request_config"]["query_parameters"] == {"page": 1, "limit": 5}
    assert preview["request_config"]["headers"] == {
        "cybertron-robot-key": "robot-key-example",
        "cybertron-robot-token": "robot-token-example",
    }
    assert preview["request_config"]["body"] == {
        "name": "mock-name",
        "count": 2,
        "tags": ["smoke"],
    }
    assert preview["success_rules"] == [{"kind": "status_code", "status_codes": [200, 201]}]
    assert preview["provenance"]["body"] == "openapi_schema"
    assert any("Authorization" in warning for warning in preview["warnings"])
    assert all("cybertron-robot" not in warning for warning in preview["warnings"])


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
