"""Deterministic, non-LLM defaults for Locust script plan generation."""

from typing import Any

from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan
from app.services.performance_testing.sse import normalize_sse_config


def build_default_plan(performance_test: dict[str, Any]) -> LocustScriptPlan:
    request_config = dict(performance_test.get("request_config") or {})
    load_config = dict(performance_test.get("load_config") or {})
    data_config = dict(performance_test.get("data_config") or {})
    method = str(performance_test.get("endpoint_method") or "GET").upper()
    path = str(performance_test.get("endpoint_path") or "/")
    headers = {str(key): value for key, value in dict(request_config.get("headers") or {}).items()}
    return LocustScriptPlan.model_validate(
        {
            "test_id": performance_test["id"],
            "random_seed": request_config.get("random_seed"),
            "request": {
                "method": method,
                "path": path,
                "name": f"{method} {path}",
                "path_parameters": request_config.get("path_parameters") or {},
                "query_parameters": request_config.get("query_parameters") or {},
                "headers": headers,
                "body": request_config.get("body"),
                "timeout_seconds": load_config.get("request_timeout_seconds", 30),
                "transport": request_config.get("transport", "http"),
                "sse": normalize_sse_config(
                    request_config.get("sse"),
                    source_request_id=str(performance_test.get("endpoint_id") or "") or None,
                    source_request_name=f"{method} {path}",
                ),
            },
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
            "success_rules": performance_test.get("success_rules")
            or [{"kind": "status_code", "status_codes": [200]}],
        }
    )


__all__ = ["build_default_plan"]
