import hashlib
import json
import secrets
from typing import Any

from app.core.db import connect
from app.core.environment_credentials import decrypt_api_environment_secret
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


TEMPLATE_VERSION = "v1"


def generate_script(project_id: str, test_id: str, actor) -> dict[str, Any]:
    with connect() as db:
        service._require_visible_project(db, project_id, actor)
        test_row = service._require_performance_test(db, project_id, test_id)
        performance_test = performance_test_repo.serialize_performance_test(test_row)
        plan, generation_source, model_id = build_ai_or_default_plan(performance_test)
        code = render_locust_script(plan)
        validation = validate_locust_script(plan, code)
        script_id = f"perfscript-{secrets.token_hex(8)}"
        performance_script_repo.create_script(
            db,
            script_id=script_id,
            performance_test_id=test_id,
            project_id=project_id,
            version=performance_script_repo.next_version(db, test_id),
            generation_source=generation_source,
            template_version=TEMPLATE_VERSION,
            input_hash=_plan_hash(plan),
            plan=plan.model_dump(mode="json"),
            code=code,
            validation_status="pending_confirmation" if validation.valid else "validation_failed",
            validation_result=validation.model_dump(mode="json"),
        )
        if model_id:
            db.execute(
                "UPDATE performance_test_scripts SET model_id = ?, prompt_version = ? WHERE id = ?",
                (model_id, PROMPT_VERSION, script_id),
            )
        return _serialize_required_script(db, project_id, test_id, script_id)


def list_scripts(project_id: str, test_id: str, actor) -> list[dict[str, Any]]:
    with connect() as db:
        service._require_visible_project(db, project_id, actor)
        service._require_performance_test(db, project_id, test_id)
        rows = performance_script_repo.list_scripts(db, test_id)
        return [
            {
                **performance_script_repo.serialize_script(row),
                "runtime_preview": _build_runtime_preview(db, project_id, test_id, performance_script_repo.serialize_script(row)),
            }
            for row in rows
        ]


def get_script(project_id: str, test_id: str, script_id: str, actor) -> dict[str, Any]:
    with connect() as db:
        service._require_visible_project(db, project_id, actor)
        service._require_performance_test(db, project_id, test_id)
        return _serialize_required_script(db, project_id, test_id, script_id)


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
        if script["validation_status"] in {"confirmed", "superseded"}:
            raise api_error(409, "PERFORMANCE_SCRIPT_IMMUTABLE", "已确认脚本不可修改，请生成新版本。")
        patch_data = patch.model_dump(exclude_unset=True) if hasattr(patch, "model_dump") else dict(patch)
        merged = _deep_merge(script["plan"], patch_data)
        plan = LocustScriptPlan.model_validate(merged)
        code = render_locust_script(plan)
        validation = validate_locust_script(plan, code)
        performance_script_repo.update_pending_script(
            db,
            script_id,
            plan=plan.model_dump(mode="json"),
            code=code,
            input_hash=_plan_hash(plan),
            validation_status="pending_confirmation" if validation.valid else "validation_failed",
            validation_result=validation.model_dump(mode="json"),
        )
        return _serialize_required_script(db, project_id, test_id, script_id)


def confirm_script(project_id: str, test_id: str, script_id: str, actor) -> dict[str, Any]:
    with connect() as db:
        service._require_visible_project(db, project_id, actor)
        service._require_performance_test(db, project_id, test_id)
        script = _require_script(db, project_id, test_id, script_id)
        if script["validation_status"] != "pending_confirmation" or not script["validation_result"].get("valid"):
            raise api_error(409, "PERFORMANCE_SCRIPT_NOT_CONFIRMABLE", "脚本校验通过后才能确认。")
        performance_script_repo.confirm_script(db, script_id, actor["id"])
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
    """合并环境注入头和 plan 头，复用 run_service 实际压测时的合并规则（env 先、plan 后）。"""
    test_row = service._require_performance_test(db, project_id, test_id)
    environment = None
    if test_row["api_environment_id"]:
        environment = api_automation_repo.find_api_environment(db, test_row["api_environment_id"])
    env_headers = _environment_runtime_headers(environment) if environment else {}
    plan_request = dict(script.get("plan", {}).get("request") or {})
    plan_headers = dict(plan_request.get("headers") or {})
    merged_headers = {**env_headers, **plan_headers}
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
    }


def _environment_runtime_headers(row) -> dict[str, str]:
    """与 run_service._runtime_environment 注入规则保持一致：env 的 default_headers + auth 注入。"""
    if row is None:
        return {}
    headers = {
        str(key): str(value)
        for key, value in api_automation_repo.loads_json(row["default_headers_json"], {}).items()
    }
    auth_config = api_automation_repo.loads_json(row["auth_config_json"], {})
    auth_type = row["auth_type"]
    if auth_type == "static_bearer" and auth_config.get("token_encrypted"):
        token = decrypt_api_environment_secret(auth_config["token_encrypted"]) or ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
    if auth_type == "static_headers":
        for key, encrypted in auth_config.get("headers_encrypted", {}).items():
            headers[str(key)] = decrypt_api_environment_secret(str(encrypted)) or ""
    if auth_type == "cookie" and auth_config.get("cookie_name"):
        cookie_value = decrypt_api_environment_secret(auth_config.get("cookie_value_encrypted", "")) or ""
        if cookie_value:
            headers["Cookie"] = f"{auth_config['cookie_name']}={cookie_value}"
    if auth_type == "cybertron_agent":
        if auth_config.get("username"):
            headers["username"] = str(auth_config["username"])
        robot_key = decrypt_api_environment_secret(auth_config.get("cybertron_robot_key_encrypted", "")) or ""
        robot_token = decrypt_api_environment_secret(auth_config.get("cybertron_robot_token_encrypted", "")) or ""
        if robot_key:
            headers["cybertron-robot-key"] = robot_key
        if robot_token:
            headers["cybertron-robot-token"] = robot_token
    return headers


def _plan_hash(plan: LocustScriptPlan) -> str:
    payload = json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _deep_merge(current: Any, patch: Any) -> Any:
    if not isinstance(current, dict) or not isinstance(patch, dict):
        return patch
    merged = dict(current)
    for key, value in patch.items():
        merged[key] = _deep_merge(merged.get(key), value) if key in merged else value
    return merged
