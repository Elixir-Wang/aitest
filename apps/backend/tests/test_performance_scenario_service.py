from pathlib import Path

import pytest

from app.core import db as db_core
from app.core import settings
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.schemas.performance_scenario import PerformanceScenarioCreateIn
from app.services.performance_testing import scenario_service


ADMIN = {"id": "u-admin", "role": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_core, "DB_PATH", tmp_path / "test.db")
    init_db()


def _seed_assets() -> None:
    with connect() as db:
        db.execute("INSERT INTO projects (id, name, description, status, created_by) VALUES ('project-1', '项目', '', 'active', 'u-admin')")
        api_automation_repo.upsert_endpoint(
            db, endpoint_id="endpoint-1", project_id="project-1", document_id=None, method="GET", path="/items/{id}",
            normalized_path="/items/{id}", summary="items", description="", tags=[], parameters=[], request_body={}, responses={"200": {}}, auth={}, source={}, created_by="u-admin",
        )
        api_automation_repo.create_api_environment(
            db, environment_id="env-1", project_id="project-1", linked_ui_environment_id=None, name="环境", api_base_url="https://example.test",
            username="", password_encrypted="", password_hash="", auth_type="none", auth_config={}, variables={}, default_headers={}, timeout_seconds=30,
            verify_ssl=True, auth_state_ttl_seconds=3600, description="", created_by="u-admin",
        )


def _payload(**overrides) -> PerformanceScenarioCreateIn:
    value = {
        "name": "场景", "api_environment_id": "env-1",
        "scenario_definition": {"personas": [{"wait_time": {"min_seconds": 1, "max_seconds": 2}, "steps": [{"endpoint_id": "endpoint-1", "request": {}, "assertions": [{"kind": "status_code", "status_codes": [200]}]}]}]},
        "load_profile": {"mode": "fixed", "target_users": 10, "spawn_rate": 3, "warmup_seconds": 5, "measurement_seconds": 20},
        "quality_gate": {"max_fail_ratio": 0.01, "min_request_count": 1},
    }
    value.update(overrides)
    return PerformanceScenarioCreateIn.model_validate(value)


def test_run_snapshot_is_immutable_after_scenario_update(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_assets()
    scenario = scenario_service.create_scenario("project-1", _payload(), ADMIN)
    run = scenario_service.create_run("project-1", scenario["id"], ADMIN)
    scenario_service.update_scenario("project-1", scenario["id"], _payload(name="已变更", load_profile={"mode": "fixed", "target_users": 20, "spawn_rate": 5, "warmup_seconds": 0, "measurement_seconds": 10}), ADMIN)

    assert run["run_snapshot"]["scenario"]["name"] == "场景"
    assert run["run_snapshot"]["execution_preview"]["total_run_seconds"] == 29


def test_execution_preview_uses_full_staged_duration() -> None:
    preview = scenario_service.execution_preview({"mode": "staged", "stages": [
        {"name": "warmup", "target_users": 10, "spawn_rate": 4, "hold_seconds": 5, "record_metrics": False},
        {"name": "measure", "target_users": 20, "spawn_rate": 3, "hold_seconds": 10, "record_metrics": True},
    ]})

    assert preview["total_run_seconds"] == 22
    assert preview["measurement_seconds"] == 14


def test_quality_gate_marks_zero_request_measurement_as_not_evaluated() -> None:
    status, results = scenario_service.evaluate_quality_gate(
        {"max_fail_ratio": 0.01, "max_p95_response_time_ms": 200},
        {"request_count": 0, "failure_rate": 0, "p95_response_time_ms": 0},
    )

    assert status == "failed"
    assert {result["status"] for result in results} == {"not_evaluated"}


def test_quality_gate_does_not_pass_interrupted_runs() -> None:
    status, results = scenario_service.evaluate_quality_gate(
        {"max_fail_ratio": 0.01}, {"request_count": 100, "failure_rate": 0}, terminal_reason="manual_stop"
    )

    assert status == "not_evaluated"
    assert results[0]["status"] == "not_evaluated"


def test_gate_results_are_persisted_on_the_new_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_assets()
    scenario = scenario_service.create_scenario("project-1", _payload(), ADMIN)
    run = scenario_service.create_run("project-1", scenario["id"], ADMIN)

    status = scenario_service.save_quality_gate_result(
        run["id"], {"max_fail_ratio": 0.01}, {"request_count": 10, "failure_rate": 0}
    )
    persisted = scenario_service.get_run("project-1", run["id"], ADMIN)

    assert status == "passed"
    assert persisted["quality_status"] == "passed"
    assert persisted["gate_results"][0]["metric"] == "failure_rate"
