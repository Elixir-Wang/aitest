import secrets
from typing import Any

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import (
    api_automation_repo,
    performance_script_repo,
    performance_test_repo,
)
from app.services.performance_testing import service
from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan
from app.agents.performance_testing.script_generation.service import PROMPT_VERSION, build_ai_or_default_plan
from app.services.performance_testing.script_renderer import render_locust_script
from app.services.performance_testing.validator import validate_locust_script


def generate_script(project_id: str, test_id: str, actor) -> dict[str, Any]:
    with connect() as db:
        service._require_visible_project(db, project_id, actor)
        test_row = service._require_performance_test(db, project_id, test_id)
        performance_test = performance_test_repo.serialize_performance_test(test_row)
        environment = api_automation_repo.find_api_environment(db, test_row["api_environment_id"])
        performance_test["request_config"]["headers"] = {
            **dict(performance_test["request_config"].get("headers") or {}),
            **service._environment_runtime_headers(environment),
        }
        plan, generation_source, model_id = build_ai_or_default_plan(performance_test)
        code = render_locust_script(plan)
        validation = validate_locust_script(plan, code)
        current = performance_script_repo.find_script_by_test(db, test_id)
        script_id = str(current["id"]) if current else f"perfscript-{secrets.token_hex(8)}"
        performance_script_repo.save_script(
            db,
            script_id=script_id,
            performance_test_id=test_id,
            project_id=project_id,
            generation_source=generation_source,
            model_id=model_id,
            prompt_version=PROMPT_VERSION if model_id else "",
            plan=plan.model_dump(mode="json"),
            code=code,
            validation_status="valid" if validation.valid else "validation_failed",
            validation_result=validation.model_dump(mode="json"),
        )
        return _serialize_required_script(db, project_id, test_id, script_id)


def get_current_script(project_id: str, test_id: str, actor) -> dict[str, Any]:
    with connect() as db:
        service._require_visible_project(db, project_id, actor)
        service._require_performance_test(db, project_id, test_id)
        row = performance_script_repo.find_script_by_test(db, test_id)
        if not row:
            raise api_error(404, "PERFORMANCE_SCRIPT_NOT_FOUND", "性能测试脚本不存在。")
        return _serialize_required_script(db, project_id, test_id, str(row["id"]))


def update_script_configuration(
    project_id: str,
    test_id: str,
    script_id: str,
    patch: dict[str, Any] | Any,
    actor,
) -> dict[str, Any]:
    with connect() as db:
        service._require_visible_project(db, project_id, actor)
        service._require_performance_test(db, project_id, test_id)
        script = _require_script(db, project_id, test_id, script_id)
        patch_data = patch.model_dump(exclude_unset=True) if hasattr(patch, "model_dump") else dict(patch)
        merged = _deep_merge(script["plan"], patch_data)
        plan = LocustScriptPlan.model_validate(merged)
        code = render_locust_script(plan)
        validation = validate_locust_script(plan, code)
        performance_script_repo.update_script(
            db,
            script_id,
            plan=plan.model_dump(mode="json"),
            code=code,
            validation_status="valid" if validation.valid else "validation_failed",
            validation_result=validation.model_dump(mode="json"),
        )
        return _serialize_required_script(db, project_id, test_id, script_id)


def _require_script(db, project_id: str, test_id: str, script_id: str) -> dict[str, Any]:
    row = performance_script_repo.find_script(db, script_id)
    if not row or row["project_id"] != project_id or row["performance_test_id"] != test_id:
        raise api_error(404, "PERFORMANCE_SCRIPT_NOT_FOUND", "性能测试脚本不存在。")
    script = performance_script_repo.serialize_script(row)
    script["runtime_preview"] = _build_runtime_preview(db, project_id, test_id, script)
    return script


def _serialize_required_script(db, project_id: str, test_id: str, script_id: str) -> dict[str, Any]:
    return _require_script(db, project_id, test_id, script_id)


def _build_runtime_preview(db, project_id: str, test_id: str, script: dict[str, Any]) -> dict[str, Any]:
    """Build the complete request preview with current environment headers."""
    test_row = service._require_performance_test(db, project_id, test_id)
    environment = None
    if test_row["api_environment_id"]:
        environment = api_automation_repo.find_api_environment(db, test_row["api_environment_id"])
    env_headers = service._environment_runtime_headers(environment)
    plan_request = dict(script.get("plan", {}).get("request") or {})
    plan_headers = dict(plan_request.get("headers") or {})
    merged_headers = {**plan_headers, **env_headers}
    return {
        "request": {
            "method": plan_request.get("method", ""),
            "path": plan_request.get("path", ""),
            "name": plan_request.get("name", ""),
            "headers": merged_headers,
            "body": plan_request.get("body"),
        },
        "success_rules": list(script.get("plan", {}).get("success_rules") or []),
        "env_headers": env_headers,
        "plan_headers": plan_headers,
        "managed_header_names": sorted(service._environment_managed_header_names(environment)),
    }


_environment_runtime_headers = service._environment_runtime_headers


def _deep_merge(current: Any, patch: Any) -> Any:
    if not isinstance(current, dict) or not isinstance(patch, dict):
        return patch
    merged = dict(current)
    for key, value in patch.items():
        merged[key] = _deep_merge(merged.get(key), value) if key in merged else value
    return merged
