import json
from typing import Any

from app.services.performance_testing.models import LocustScriptPlan
from app.services.performance_testing.plan_builder import SENSITIVE_HEADER_NAMES, build_default_plan


CAPABILITY_ID = "performance_script_generation"
PROMPT_VERSION = "v1"


def script_plan_input(performance_test: dict[str, Any]) -> dict[str, Any]:
    default = build_default_plan(performance_test)
    return {
        "test_id": default.test_id,
        "endpoint": {"method": default.request.method, "path": default.request.path, "name": default.request.name},
        "request": {
            "path_parameters": default.request.path_parameters,
            "query_parameters": default.request.query_parameters,
            "headers": default.request.headers,
            "body": default.request.body,
            "timeout_seconds": default.request.timeout_seconds,
            "random_seed": default.random_seed,
        },
        "load": default.load.model_dump(mode="json"),
        "data": default.data.model_dump(mode="json"),
        "success_rules": [rule.model_dump(mode="json", exclude_none=True) for rule in default.success_rules],
    }


def build_ai_or_default_plan(performance_test: dict[str, Any]) -> tuple[LocustScriptPlan, str, str]:
    default = build_default_plan(performance_test)
    payload = script_plan_input(performance_test)
    try:
        from app.agents.model_selection import build_agent_model, resolve_model_selection

        selection = resolve_model_selection(CAPABILITY_ID)
        model = build_agent_model(selection).with_structured_output(LocustScriptPlan)
        generated = model.invoke(
            "根据白名单输入生成 LocustScriptPlan。不得新增接口、导入、文件或进程能力。"
            f"\nINPUT={json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        )
        plan = generated if isinstance(generated, LocustScriptPlan) else LocustScriptPlan.model_validate(generated)
        plan.test_id = default.test_id
        plan.request.method = default.request.method
        plan.request.path = default.request.path
        plan.request.name = default.request.name
        plan.request.headers = {
            key: value
            for key, value in plan.request.headers.items()
            if key.strip().lower() not in SENSITIVE_HEADER_NAMES
        }
        plan.load = default.load
        plan.data = default.data
        return plan, "ai_plan", selection.model
    except Exception:
        return default, "default_plan", ""
