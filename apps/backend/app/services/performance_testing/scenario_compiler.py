from typing import Any

from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan
from app.core.exceptions import api_error


def build_scenario_plan(
    performance_test: dict[str, Any],
    snapshot: dict[str, Any],
    environment_headers: dict[str, str],
    environment_variables: dict[str, Any] | None = None,
) -> LocustScriptPlan:
    steps = list(snapshot.get("steps") or [])
    request_steps = [step for step in steps if step.get("step_type", "api_request") == "api_request"]
    if not request_steps:
        raise api_error(400, "PERFORMANCE_SCENARIO_EMPTY", "接口场景没有可执行的接口请求步骤。")

    load_config = dict(performance_test.get("load_config") or {})
    data_config = dict(performance_test.get("data_config") or {})
    compiled_steps = []
    for index, step in enumerate(steps, start=1):
        step_type = str(step.get("step_type") or "api_request")
        compiled: dict[str, Any] = {
            "id": str(step.get("id") or f"step-{index}"),
            "name": str(step.get("name") or step_type),
            "step_type": step_type,
            "bindings": list(step.get("bindings") or []),
            "extractors": list(step.get("extractors") or []),
            "assertions": list(step.get("assertions") or []),
            "control_config": dict(step.get("control_config") or {}),
            "on_failure": str(step.get("on_failure") or "stop"),
        }
        if step_type == "api_request":
            endpoint = step.get("endpoint") or {}
            if not endpoint.get("id") or not endpoint.get("path"):
                raise api_error(
                    400,
                    "PERFORMANCE_SCENARIO_ENDPOINT_INVALID",
                    f"场景步骤 {compiled['id']} 引用的接口不存在。",
                )
            overrides = dict(step.get("request_overrides") or {})
            request = dict(overrides.get("request") or overrides)
            method = str(request.get("method") or endpoint.get("method") or "GET").upper()
            path = str(request.get("path") or endpoint.get("path") or "/")
            headers = {**dict(request.get("headers") or {}), **environment_headers}
            compiled["request"] = {
                "method": method,
                "path": path,
                "name": f"{index:02d} {method} {path}",
                "path_parameters": request.get("path_parameters") or request.get("path_params") or {},
                "query_parameters": request.get("query_parameters") or request.get("query") or {},
                "headers": headers,
                "body": request.get("body", request.get("json")),
                "timeout_seconds": load_config.get("request_timeout_seconds", 30),
                "transport": request.get("transport", "http"),
                "sse": request.get("sse"),
            }
        compiled_steps.append(compiled)

    return LocustScriptPlan.model_validate(
        {
            "test_id": performance_test["id"],
            "target_type": "scenario",
            "random_seed": performance_test.get("request_config", {}).get("random_seed"),
            "scenario_id": snapshot.get("id") or performance_test.get("scenario_id"),
            "scenario_name": snapshot.get("name") or performance_test.get("scenario_name"),
            "scenario_revision": snapshot.get("revision"),
            "scenario_variables": {
                **dict(snapshot.get("variables") or {}),
                **dict(environment_variables or {}),
                **environment_headers,
            },
            "steps": compiled_steps,
            "load": {
                "mode": load_config.get("mode", "fixed"),
                "wait_time_min_seconds": load_config.get("wait_time_min_seconds", 1),
                "wait_time_max_seconds": load_config.get("wait_time_max_seconds", 3),
                "stages": load_config.get("stages") or [],
            },
            "data": {
                "source": data_config.get("source", "fixed"),
                "selection_strategy": data_config.get("selection_strategy", "sequential_loop"),
                "json_rows": data_config.get("json_rows") or [],
            },
        }
    )


__all__ = ["build_scenario_plan"]
