from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.performance_testing.script_generation.planner import build_default_plan
from app.agents.performance_testing.script_generation.schemas import LocustLoadPlan, LocustScriptPlan
from app.agents.performance_testing.script_generation.service import script_plan_input
from app.services.performance_testing.scenario_compiler import build_scenario_plan
from app.services.performance_testing.script_renderer import _render_scenario_helpers, render_locust_script
from app.services.performance_testing.validator import validate_locust_script


SKILL_PATH = (
    Path(__file__).parents[1]
    / "app"
    / "agents"
    / "performance_testing"
    / "script_generation"
    / "skills"
    / "performance-script-generation"
    / "SKILL.md"
)


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


def _legacy_first_output_sse_config() -> dict:
    return {
        "max_stream_seconds": 60,
        "metrics": [
            {
                "id": "sse_first_output_98bdefc2",
                "name": "首次有效内容时间",
                "match": {
                    "event_name": "message",
                    "source": "data_json",
                    "path": "$.data.event_type",
                    "operator": "equals",
                    "expected": "answer",
                },
            },
            {
                "id": "sse_milestone_start_da4c4636",
                "name": "call_llm 开始时间",
                "match": {
                    "event_name": "message",
                    "source": "data_json",
                    "path": "$.data.event_type",
                    "operator": "equals",
                    "expected": "call_llm_start",
                },
            },
        ],
    }


def test_planners_upgrade_legacy_first_output_rule_to_index_zero() -> None:
    performance_test = _performance_test()
    performance_test["request_config"] = {
        **performance_test["request_config"],
        "transport": "sse",
        "sse": _legacy_first_output_sse_config(),
    }
    endpoint_plan = build_default_plan(performance_test)
    scenario_plan = build_scenario_plan(
        {
            "id": "perftest-sse",
            "request_config": {
                "scenario_step_id": "step-sse",
                "transport": "sse",
                "sse": _legacy_first_output_sse_config(),
            },
            "load_config": {},
        },
        {
            "id": "scenario-1",
            "name": "SSE 场景",
            "revision": 1,
            "steps": [
                {
                    "id": "step-sse",
                    "name": "SSE",
                    "step_type": "api_request",
                    "endpoint": {"id": "endpoint-sse", "method": "POST", "path": "/sse"},
                }
            ],
        },
        {},
    )

    for config in (endpoint_plan.request.sse, scenario_plan.steps[0].request.sse):
        first_output = next(metric for metric in config["metrics"] if metric["id"].startswith("sse_first_output_"))
        llm_start = next(metric for metric in config["metrics"] if metric["id"].startswith("sse_milestone_start_"))
        assert first_output["match"] == {
            "event_name": "message",
            "source": "data_json",
            "path": "$.data.index",
            "operator": "equals",
            "expected": 0,
        }
        assert first_output["category"] == "first_output"
        assert llm_start["category"] == "milestone_start"
        assert first_output["timing"]["scope"] == "request"
        assert first_output["timing"]["start"] == "request_started"

    assert endpoint_plan.request.sse["metrics"][0]["timing"]["source_request_name"] == endpoint_plan.request.name
    assert scenario_plan.steps[0].request.sse["metrics"][0]["timing"] == {
        "scope": "request",
        "start": "request_started",
        "source_request_id": "step-sse",
        "source_request_name": "01 POST /sse",
    }


def test_planners_preserve_confirmed_answer_content_rule() -> None:
    performance_test = _performance_test()
    sse_config = _legacy_first_output_sse_config()
    sse_config["metrics"][0]["match"] = {
        "event_name": "message",
        "source": "data_json",
        "path": "$.data.answer",
        "operator": "non_empty",
        "expected": None,
    }
    performance_test["request_config"] = {
        **performance_test["request_config"],
        "transport": "sse",
        "sse": sse_config,
    }

    plan = build_default_plan(performance_test)

    assert plan.request.sse["metrics"][0]["match"] == sse_config["metrics"][0]["match"]


def test_scenario_compiler_keeps_required_endpoint_header_defaults() -> None:
    plan = build_scenario_plan(
        {
            "id": "perftest-sse",
            "request_config": {
                "scenario_step_id": "step-sse",
                "transport": "sse",
                "sse": {"metrics": []},
            },
            "load_config": {},
        },
        {
            "id": "scenario-1",
            "name": "SSE 场景",
            "revision": 1,
            "steps": [
                {
                    "id": "step-sse",
                    "name": "SSE",
                    "step_type": "api_request",
                    "endpoint": {
                        "id": "endpoint-sse",
                        "method": "POST",
                        "path": "/sse",
                        "parameters": [
                            {
                                "name": "SSE-Backend-Type",
                                "in": "header",
                                "required": True,
                                "schema": {"enum": ["sse"]},
                            },
                            {
                                "name": "cybertron-app-id",
                                "in": "header",
                                "required": True,
                                "schema": {"default": "multi-agent-server"},
                            },
                        ],
                    },
                    "request_overrides": {"request": {"multipart_form": {"question": "你好"}}},
                }
            ],
        },
        {},
    )

    assert plan.steps[0].request.headers == {
        "SSE-Backend-Type": "sse",
        "cybertron-app-id": "multi-agent-server",
    }


def _scenario_plan_with_binding(source: dict, *, data_rows: list[dict] | None = None) -> LocustScriptPlan:
    return LocustScriptPlan.model_validate(
        {
            "test_id": "perftest-scenario",
            "target_type": "scenario",
            "scenario_id": "scenario-1",
            "scenario_name": "场景",
            "scenario_variables": {},
            "steps": [
                {
                    "id": "step-1",
                    "name": "请求",
                    "step_type": "api_request",
                    "request": {
                        "method": "POST",
                        "path": "/api/items",
                        "name": "POST /api/items",
                        "headers": {"cybertron-robot-key": "runtime-value"},
                        "timeout_seconds": 30,
                    },
                    "bindings": [
                        {
                            "required": True,
                            "source": source,
                            "target": "/request/headers/cybertron-robot-key",
                        }
                    ],
                }
            ],
            "load": {
                "mode": "fixed",
                "wait_time_min_seconds": 1,
                "wait_time_max_seconds": 3,
            },
            "data": {
                "source": "json" if data_rows else "fixed",
                "selection_strategy": "sequential_loop",
                "json_rows": data_rows or [],
            },
        }
    )


def test_default_plan_keeps_all_headers() -> None:
    plan = build_default_plan(_performance_test())

    assert plan.request.headers == {
        "X-Request-Source": "performance",
        "Authorization": "Bearer must-not-leak",
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
    assert "Authorization" in source
    assert "cybertron-robot-key" in source
    assert "cybertron-robot-token" in source
    assert "self.client.request(" in source
    assert "LoadTestShape" not in source


def test_renderer_reads_sse_lines_without_requests_default_buffering() -> None:
    performance_test = _performance_test()
    performance_test["request_config"] = {
        **performance_test["request_config"],
        "transport": "sse",
        "sse": _legacy_first_output_sse_config(),
    }

    source = render_locust_script(build_default_plan(performance_test))

    assert "response.iter_lines(chunk_size=1, decode_unicode=True)" in source


def test_renderer_keeps_http_and_business_success_rules() -> None:
    performance_test = _performance_test()
    performance_test["success_rules"] = [
        {"kind": "status_code", "status_codes": [200]},
        {"kind": "jsonpath_exists", "json_path": "$.code"},
        {"kind": "jsonpath_equals", "json_path": "$.code", "expected": "000000"},
    ]

    plan = build_default_plan(performance_test)
    source = render_locust_script(plan)

    assert [rule.kind for rule in plan.success_rules] == ["status_code", "jsonpath_equals"]
    assert plan.success_rules[1].json_path == "$.code"
    assert plan.success_rules[1].expected == "000000"
    assert plan.model_dump(mode="json")["success_rules"] == [
        {"kind": "status_code", "status_codes": [200]},
        {"kind": "jsonpath_equals", "json_path": "$.code", "expected": "000000"},
    ]
    assert 'rule["kind"].startswith("jsonpath_")' in source
    assert "JSONPath mismatch" in source
    assert source.count("payload = response.json()") == 1
    assert "payload_loaded = False" in source


def test_renderer_resolves_single_brace_path_parameters() -> None:
    source = render_locust_script(build_default_plan(_performance_test()))

    assert 'path = path.replace("{" + key + "}", str(value))' in source
    assert 'path.replace("{{" + key + "}}"' not in source


def test_scenario_source_resolves_normalized_environment_secret_names() -> None:
    namespace: dict[str, object] = {}
    exec(_render_scenario_helpers(), namespace)

    scenario_source = namespace["_scenario_source"]

    assert scenario_source(
        {"type": "secret", "key": "cybertron_robot_key"},
        {"cybertron-robot-key": "robot-key"},
        {},
    ) == "robot-key"


def test_scenario_variable_prefers_exact_name_over_normalized_alias() -> None:
    namespace: dict[str, object] = {}
    exec(_render_scenario_helpers(), namespace)

    scenario_variable = namespace["_scenario_variable"]

    assert scenario_variable(
        {
            "cybertron_robot_key": "exact-value",
            "cybertron-robot-key": "alias-value",
        },
        "cybertron_robot_key",
    ) == "exact-value"


def test_scenario_variable_rejects_ambiguous_normalized_names() -> None:
    namespace: dict[str, object] = {}
    exec(_render_scenario_helpers(), namespace)

    scenario_variable = namespace["_scenario_variable"]

    with pytest.raises(ValueError, match="ambiguous scenario variable: Cybertron_Robot_Key"):
        scenario_variable(
            {
                "cybertron_robot_key": "first-value",
                "cybertron-robot-key": "second-value",
            },
            "Cybertron_Robot_Key",
        )


def test_required_scenario_binding_rejects_missing_value_before_overwrite() -> None:
    namespace: dict[str, object] = {}
    exec(_render_scenario_helpers(), namespace)

    apply_bindings = namespace["_apply_scenario_bindings"]
    request = {"headers": {"cybertron-robot-key": "runtime-value"}}
    binding = {
        "required": True,
        "source": {"type": "secret", "key": "cybertron_robot_key"},
        "target": "/request/headers/cybertron-robot-key",
    }

    with pytest.raises(
        ValueError,
        match="required scenario binding unresolved: cybertron_robot_key -> /request/headers/cybertron-robot-key",
    ):
        apply_bindings(request, [binding], {}, {})

    assert request["headers"]["cybertron-robot-key"] == "runtime-value"


def test_optional_scenario_binding_preserves_existing_value_when_missing() -> None:
    namespace: dict[str, object] = {}
    exec(_render_scenario_helpers(), namespace)

    apply_bindings = namespace["_apply_scenario_bindings"]
    request = {"headers": {"cybertron-robot-key": "runtime-value"}}
    binding = {
        "required": False,
        "source": {"type": "secret", "key": "cybertron_robot_key"},
        "target": "/request/headers/cybertron-robot-key",
    }

    apply_bindings(request, [binding], {}, {})

    assert request["headers"]["cybertron-robot-key"] == "runtime-value"


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


def test_load_plan_rejects_wait_time_range_in_reverse() -> None:
    with pytest.raises(ValidationError, match="wait_time_min_seconds"):
        LocustLoadPlan.model_validate(
            {
                "mode": "fixed",
                "wait_time_min_seconds": 3,
                "wait_time_max_seconds": 1,
                "stages": [],
            }
        )


def test_load_plan_requires_stages_for_non_fixed_mode() -> None:
    with pytest.raises(ValidationError, match="stages"):
        LocustLoadPlan.model_validate(
            {
                "mode": "spike",
                "wait_time_min_seconds": 1,
                "wait_time_max_seconds": 3,
                "stages": [],
            }
        )


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


def test_stress_script_stops_after_consecutive_failure_windows() -> None:
    performance_test = _performance_test()
    performance_test["load_config"] = {
        **performance_test["load_config"],
        "mode": "stress",
        "stages": [
            {"name": "压力阶段 1", "target_users": 10, "spawn_rate": 2, "hold_seconds": 60, "order": 0},
            {"name": "压力阶段 2", "target_users": 20, "spawn_rate": 2, "hold_seconds": 60, "order": 1},
        ],
    }
    performance_test["circuit_breaker"] = {
        "enabled": True,
        "window_seconds": 30,
        "max_fail_ratio": 0.1,
        "consecutive_windows": 3,
    }

    source = render_locust_script(build_default_plan(performance_test))

    assert 'PLAN["circuit_breaker"]' in source
    assert "window_fail_ratio" in source
    assert "self.failed_windows >= breaker[\"consecutive_windows\"]" in source


def test_validator_rejects_unresolved_required_static_scenario_binding() -> None:
    plan = _scenario_plan_with_binding({"type": "secret", "key": "cybertron_robot_key"})
    source = render_locust_script(plan)

    result = validate_locust_script(plan, source)

    assert result.valid is False
    assert result.errors == [
        "必填场景绑定无法解析：step-1 cybertron_robot_key -> /request/headers/cybertron-robot-key"
    ]


def test_validator_allows_required_user_input_from_runtime_data() -> None:
    plan = _scenario_plan_with_binding(
        {"type": "user_input", "name": "cybertron_robot_key"},
        data_rows=[{"cybertron_robot_key": "runtime-value"}],
    )
    source = render_locust_script(plan)

    result = validate_locust_script(plan, source)

    assert result.valid is True
    assert result.errors == []


def test_validator_rejects_forbidden_import() -> None:
    plan = LocustScriptPlan.model_validate(build_default_plan(_performance_test()).model_dump())
    source = "import os\n" + render_locust_script(plan)

    result = validate_locust_script(plan, source)

    assert result.valid is False
    assert any("os" in error for error in result.errors)


def test_ai_plan_input_keeps_all_request_headers() -> None:
    payload = script_plan_input(_performance_test())

    serialized = str(payload)
    assert "Authorization" in serialized
    assert "must-not-leak" in serialized
    assert "cybertron-robot-key" in serialized
    assert set(payload) == {"test_id", "endpoint", "request", "load", "data", "success_rules"}


def test_skill_describes_structured_plan_contract() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    assert "LocustScriptPlan" in skill
    assert "只输出符合 `LocustScriptPlan`" in skill
    assert "直接输出完整的 `locustfile.py`" not in skill
