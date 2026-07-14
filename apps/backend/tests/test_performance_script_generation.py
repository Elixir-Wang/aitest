from app.services.performance_testing.models import LocustScriptPlan
from app.services.performance_testing.ai_plan_builder import script_plan_input
from app.services.performance_testing.plan_builder import build_default_plan
from app.services.performance_testing.script_renderer import render_locust_script
from app.services.performance_testing.validator import validate_locust_script


def _performance_test() -> dict:
    return {
        "id": "perftest-1",
        "project_id": "project-1",
        "endpoint_method": "POST",
        "endpoint_path": "/api/items/{item_id}",
        "request_config": {
            "path_parameters": {"item_id": "${sequence}"},
            "query_parameters": {"trace": "${uuid}"},
            "headers": {
                "X-Request-Source": "performance",
                "Authorization": "Bearer must-not-leak",
                "cybertron-robot-key": "robot-key",
                "cybertron-robot-token": "robot-token",
            },
            "body": {"name": "item-${sequence}"},
            "random_seed": 7,
        },
        "load_config": {
            "mode": "fixed",
            "users": 5,
            "spawn_rate": 2,
            "measurement_duration_seconds": 10,
            "wait_time_min_seconds": 0.5,
            "wait_time_max_seconds": 1.5,
            "request_timeout_seconds": 3,
            "stages": [],
        },
        "data_config": {"source": "fixed", "selection_strategy": "sequential_loop", "json_rows": []},
        "success_rules": [{"kind": "status_code", "status_codes": [200, 201]}],
    }


def test_default_plan_excludes_sensitive_headers() -> None:
    plan = build_default_plan(_performance_test())

    assert plan.request.headers == {
        "X-Request-Source": "performance",
        "cybertron-robot-key": "robot-key",
        "cybertron-robot-token": "robot-token",
    }
    assert plan.request.method == "POST"
    assert plan.request.path == "/api/items/{item_id}"


def test_renderer_uses_locust_http_user_and_controlled_request() -> None:
    plan = build_default_plan(_performance_test())

    source = render_locust_script(plan)

    assert "class PerformanceUser(HttpUser):" in source
    assert "catch_response=True" in source
    assert "between(0.5, 1.5)" in source
    assert "Authorization" not in source
    assert "cybertron-robot-key" in source
    assert "cybertron-robot-token" in source
    assert "self.client.request(" in source
    assert "LoadTestShape" not in source


def test_renderer_emits_controlled_load_shape_for_gradient_mode() -> None:
    performance_test = _performance_test()
    performance_test["load_config"] = {
        **performance_test["load_config"],
        "mode": "gradient",
        "stages": [
            {"name": "阶段 1", "target_users": 10, "spawn_rate": 2, "hold_seconds": 60, "order": 0},
            {"name": "阶段 2", "target_users": 50, "spawn_rate": 5, "hold_seconds": 120, "order": 1},
        ],
    }

    source = render_locust_script(build_default_plan(performance_test))

    assert "class PerformanceLoadShape(LoadTestShape):" in source
    assert '"target_users": 50' in source
    assert "return (stage[\"target_users\"], stage[\"spawn_rate\"])" in source


def test_renderer_supports_json_parameter_rows() -> None:
    performance_test = _performance_test()
    performance_test["data_config"] = {
        "source": "json",
        "selection_strategy": "random",
        "json_rows": [{"name": "alpha"}, {"name": "beta"}],
    }

    plan = build_default_plan(performance_test)
    source = render_locust_script(plan)

    assert plan.data.source == "json"
    assert "def _next_data_row" in source
    assert "random.choice(rows)" in source


def test_validator_accepts_rendered_script() -> None:
    plan = build_default_plan(_performance_test())
    source = render_locust_script(plan)

    result = validate_locust_script(plan, source)

    assert result.valid is True
    assert result.errors == []
    assert result.code_hash


def test_validator_rejects_forbidden_import() -> None:
    plan = LocustScriptPlan.model_validate(build_default_plan(_performance_test()).model_dump())
    source = "import os\n" + render_locust_script(plan)

    result = validate_locust_script(plan, source)

    assert result.valid is False
    assert any("os" in error for error in result.errors)


def test_ai_plan_input_is_whitelisted() -> None:
    payload = script_plan_input(_performance_test())

    serialized = str(payload)
    assert "Authorization" not in serialized
    assert "must-not-leak" not in serialized
    assert "cybertron-robot-key" in serialized
    assert set(payload) == {"test_id", "endpoint", "request", "load", "data", "success_rules"}
