import pytest
from pydantic import ValidationError

from app.schemas.performance_scenario import PerformanceScenarioCreateIn


def valid_payload(*, load_profile: dict | None = None) -> dict:
    return {
        "name": "接口性能测试",
        "description": "",
        "api_environment_id": "env-1",
        "scenario_definition": {
            "personas": [
                {
                    "wait_time": {"min_seconds": 1, "max_seconds": 3},
                    "steps": [
                        {
                            "type": "http",
                            "endpoint_id": "endpoint-1",
                            "request": {"path_parameters": {}, "query_parameters": {}, "headers": {}, "body": None, "timeout_seconds": 30},
                            "assertions": [{"kind": "status_code", "status_codes": [200]}],
                        }
                    ],
                }
            ]
        },
        "load_profile": load_profile
        or {"mode": "fixed", "target_users": 10, "spawn_rate": 2, "warmup_seconds": 5, "measurement_seconds": 20, "stop_timeout_seconds": 10},
        "data_source": {"source": "fixed", "selection_strategy": "sequential_loop", "rows": []},
        "quality_gate": {"max_fail_ratio": 0.01},
        "safety_policy": {"enabled": False, "window_seconds": 10, "max_fail_ratio": 0.5, "consecutive_windows": 3},
    }


def test_v1_rejects_more_than_one_persona() -> None:
    payload = valid_payload()
    payload["scenario_definition"]["personas"].append(payload["scenario_definition"]["personas"][0])

    with pytest.raises(ValidationError, match="exactly one persona"):
        PerformanceScenarioCreateIn.model_validate(payload)


def test_v1_rejects_more_than_one_http_step() -> None:
    payload = valid_payload()
    payload["scenario_definition"]["personas"][0]["steps"].append(
        payload["scenario_definition"]["personas"][0]["steps"][0]
    )

    with pytest.raises(ValidationError, match="exactly one HTTP step"):
        PerformanceScenarioCreateIn.model_validate(payload)


def test_staged_load_requires_measured_stage_and_computes_runtime() -> None:
    scenario = PerformanceScenarioCreateIn.model_validate(
        valid_payload(
            load_profile={
                "mode": "staged",
                "stages": [
                    {"name": "warmup", "target_users": 10, "spawn_rate": 5, "hold_seconds": 30, "record_metrics": False},
                    {"name": "measure", "target_users": 20, "spawn_rate": 5, "hold_seconds": 60, "record_metrics": True},
                ],
            }
        )
    )

    assert scenario.load_profile.total_run_seconds == 94


def test_fixed_load_computes_ramp_warmup_and_measurement_duration() -> None:
    scenario = PerformanceScenarioCreateIn.model_validate(valid_payload())

    assert scenario.load_profile.total_run_seconds == 30
