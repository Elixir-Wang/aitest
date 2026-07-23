from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import ValidationError

from app.agents.performance_testing.script_generation.planner import build_default_plan
from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import (
    api_automation_repo,
    performance_analysis_repo,
    performance_script_repo,
    performance_test_repo,
)
from app.schemas.performance_test import (
    PerformanceDataConfig,
    PerformanceLoadConfig,
    PerformanceRequestConfig,
    PerformanceSuccessRule,
)
from app.services.performance_testing import headless_worker, run_repo, service
from app.services.performance_testing.analysis_evidence import redact_sensitive
from app.services.performance_testing.script_renderer import render_locust_script
from app.services.performance_testing.script_service import TEMPLATE_VERSION, _environment_runtime_headers
from app.services.performance_testing.validator import validate_locust_script


TARGET_ALIASES = {
    "performance_test.request_config.path_parameters": "request_config.path_parameters",
    "performance_test.request_config.query_parameters": "request_config.query_parameters",
    "performance_test.request_config.headers": "request_config.headers",
    "performance_test.request_config.body": "request_config.body",
    "performance_test.request_config.random_seed": "request_config.random_seed",
    "performance_test.load_config.request_timeout_seconds": "load_config.request_timeout_seconds",
    "performance_test.load_config.wait_time_min_seconds": "load_config.wait_time_min_seconds",
    "performance_test.load_config.wait_time_max_seconds": "load_config.wait_time_max_seconds",
    "performance_test.data_config": "data_config",
    "performance_test.data_config.json_rows": "data_config.json_rows",
    "performance_test.success_rules": "success_rules",
    "PLAN['request']['body']": "request_config.body",
    'PLAN["request"]["body"]': "request_config.body",
}
ALLOWED_TARGETS = {
    "request_config.path_parameters",
    "request_config.query_parameters",
    "request_config.headers",
    "request_config.body",
    "request_config.random_seed",
    "load_config.request_timeout_seconds",
    "load_config.wait_time_min_seconds",
    "load_config.wait_time_max_seconds",
    "data_config",
    "data_config.json_rows",
    "success_rules",
}


def is_supported_change(change: dict[str, Any]) -> bool:
    if change.get("target_type") == "platform_code":
        return False
    return _normalize_target(str(change.get("target") or "")) in ALLOWED_TARGETS


def apply_and_rerun(project_id: str, analysis_id: str, change_ids: list[str], actor) -> dict[str, Any]:
    selected_ids = list(dict.fromkeys(str(change_id) for change_id in change_ids if str(change_id).strip()))
    if not selected_ids:
        raise api_error(422, "PERFORMANCE_REPAIR_CHANGES_REQUIRED", "至少选择一项修复建议。")

    with connect() as db:
        service._require_visible_project(db, project_id, actor)
        row = performance_analysis_repo.find_analysis_session(db, analysis_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "PERFORMANCE_ANALYSIS_NOT_FOUND", "性能分析不存在。")
        analysis = performance_analysis_repo.serialize_analysis_session(row)
        if analysis["status"] != "waiting_approval":
            raise api_error(409, "PERFORMANCE_REPAIR_NOT_APPROVABLE", "当前分析状态不能应用修复。")
        if analysis["application_status"] not in {"not_requested", "preflight_failed", "apply_failed"}:
            raise api_error(409, "PERFORMANCE_REPAIR_ALREADY_APPLIED", "当前分析正在修复或已经完成修复。")
        changes_by_id = {
            str(change.get("id")): change
            for change in analysis["proposal"].get("changes", [])
            if isinstance(change, dict) and change.get("id")
        }
        unknown = [change_id for change_id in selected_ids if change_id not in changes_by_id]
        unsupported = [change_id for change_id in selected_ids if not is_supported_change(changes_by_id.get(change_id, {}))]
        if unknown or unsupported:
            raise api_error(422, "PERFORMANCE_REPAIR_CHANGE_UNSUPPORTED", "选中的修复建议不存在或不在安全白名单中。")

        run = run_repo.get_run(db, analysis["run_id"])
        if not run:
            raise api_error(404, "PERFORMANCE_RUN_NOT_FOUND", "性能测试运行不存在。")
        test_row = performance_test_repo.find_performance_test(db, run["performance_test_id"])
        if not test_row:
            raise api_error(404, "PERFORMANCE_TEST_NOT_FOUND", "性能测试不存在。")
        current = performance_test_repo.serialize_performance_test(test_row)
        candidate = _candidate_configuration(current, [changes_by_id[change_id] for change_id in selected_ids])
        plan = build_default_plan(candidate)
        code = render_locust_script(plan)
        validation = validate_locust_script(plan, code)
        if not validation.valid:
            raise api_error(422, "PERFORMANCE_REPAIR_SCRIPT_INVALID", "修复后的 Locust 脚本校验失败。")
        runtime = _runtime_environment(db, current, run)
        performance_analysis_repo.update_analysis_session(
            db,
            analysis_id,
            application_status="preflighting",
            selected_change_ids=selected_ids,
            error_message="",
        )

    preflight = _send_preflight(plan.model_dump(mode="json"), runtime)
    if not preflight["passed"]:
        with connect() as db:
            performance_analysis_repo.update_analysis_session(
                db,
                analysis_id,
                application_status="preflight_failed",
                preflight=preflight,
                error_message="修复预检失败，未修改配置，也未启动并发压测。",
            )
            return performance_analysis_repo.serialize_analysis_session(
                performance_analysis_repo.find_analysis_session(db, analysis_id)
            )

    script_id = f"perfscript-{secrets.token_hex(8)}"
    with connect() as db:
        latest = performance_analysis_repo.find_analysis_session(db, analysis_id)
        if not latest or latest["application_status"] != "preflighting":
            raise api_error(409, "PERFORMANCE_REPAIR_STATE_CHANGED", "修复状态已变化，请重新分析。")
        performance_test_repo.update_performance_test(
            db,
            candidate["id"],
            {
                "request_config": candidate["request_config"],
                "load_config": candidate["load_config"],
                "data_config": candidate["data_config"],
                "success_rules": candidate["success_rules"],
            },
        )
        performance_script_repo.create_script(
            db,
            script_id=script_id,
            performance_test_id=candidate["id"],
            project_id=project_id,
            version=performance_script_repo.next_version(db, candidate["id"]),
            generation_source="ai_repair",
            template_version=TEMPLATE_VERSION,
            input_hash=_plan_hash(plan.model_dump(mode="json")),
            plan=plan.model_dump(mode="json"),
            code=code,
            validation_status="pending_confirmation",
            validation_result=validation.model_dump(mode="json"),
        )
        performance_script_repo.confirm_script(db, script_id, str(actor["id"]))
        performance_analysis_repo.update_analysis_session(
            db,
            analysis_id,
            application_status="rerunning",
            preflight=preflight,
            applied_script_id=script_id,
            applied_by=str(actor["id"]),
        )

    try:
        new_run_id = headless_worker.create_run_session(
            project_id=project_id,
            test_id=candidate["id"],
            script_id=script_id,
            script_code=code,
            runtime_payload=runtime,
            load_config=candidate["load_config"],
            created_by=str(actor["id"]),
        )
        headless_worker.start_headless_run(new_run_id)
    except Exception as exc:
        with connect() as db:
            performance_analysis_repo.update_analysis_session(
                db,
                analysis_id,
                application_status="apply_failed",
                error_message=f"配置和脚本已修复，但自动重跑启动失败：{type(exc).__name__}。",
            )
        raise api_error(500, "PERFORMANCE_REPAIR_RERUN_FAILED", "修复已应用，但自动重新压测启动失败。") from exc

    with connect() as db:
        performance_analysis_repo.update_analysis_session(
            db,
            analysis_id,
            application_status="completed",
            applied_run_id=new_run_id,
            applied_at=datetime.now(timezone.utc).isoformat(),
            error_message="",
        )
        return performance_analysis_repo.serialize_analysis_session(
            performance_analysis_repo.find_analysis_session(db, analysis_id)
        )


def _candidate_configuration(current: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
    candidate = {
        **current,
        "request_config": json.loads(json.dumps(current["request_config"])),
        "load_config": json.loads(json.dumps(current["load_config"])),
        "data_config": json.loads(json.dumps(current["data_config"])),
        "success_rules": json.loads(json.dumps(current["success_rules"])),
    }
    for change in changes:
        target = _normalize_target(str(change["target"]))
        actual = _get_path(candidate, target)
        before = _decode_json_literal(change.get("before"))
        if before != actual:
            raise api_error(409, "PERFORMANCE_REPAIR_BASELINE_CHANGED", f"配置 {target} 已变化，请重新分析。")
        _set_path(candidate, target, change.get("after"))

    if candidate["data_config"].get("json_rows") and candidate["data_config"].get("source") == "fixed":
        candidate["data_config"]["source"] = "json"
    candidate["request_config"] = PerformanceRequestConfig.model_validate(candidate["request_config"]).model_dump(mode="json")
    candidate["load_config"] = PerformanceLoadConfig.model_validate(candidate["load_config"]).model_dump(mode="json")
    candidate["data_config"] = PerformanceDataConfig.model_validate(candidate["data_config"]).model_dump(mode="json")
    candidate["success_rules"] = [
        PerformanceSuccessRule.model_validate(rule).model_dump(mode="json") for rule in candidate["success_rules"]
    ]
    service._validate_non_sensitive_headers(candidate["request_config"]["headers"])
    return candidate


def _runtime_environment(db, current: dict[str, Any], run) -> dict[str, Any]:
    environment = (
        api_automation_repo.find_api_environment(db, current["api_environment_id"])
        if current.get("api_environment_id")
        else None
    )
    if environment:
        return {
            "api_base_url": environment["api_base_url"],
            "headers": _environment_runtime_headers(environment),
            "variables": api_automation_repo.loads_json(environment["variables_json"], {}),
            "verify_ssl": bool(environment["verify_ssl"]),
        }
    return api_automation_repo.loads_json(run["runtime_config_json"], {})


def _send_preflight(plan: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    request = plan["request"]
    data = (plan.get("data", {}).get("json_rows") or [{}])[0]
    path = _resolve(request["path"], data)
    for key, value in _resolve(request.get("path_parameters") or {}, data).items():
        path = path.replace("{" + key + "}", str(value))
    url = urljoin(str(runtime["api_base_url"]).rstrip("/") + "/", path.lstrip("/"))
    headers = {**dict(runtime.get("headers") or {}), **_resolve(request.get("headers") or {}, data)}
    try:
        with httpx.Client(
            verify=bool(runtime.get("verify_ssl", True)),
            follow_redirects=True,
            timeout=float(request.get("timeout_seconds") or 30),
        ) as client:
            response = client.request(
                request["method"],
                url,
                params=_resolve(request.get("query_parameters") or {}, data),
                headers=headers,
                json=_resolve(request.get("body"), data),
            )
        failures = _success_rule_failures(response, plan.get("success_rules") or [])
        return {
            "passed": not failures,
            "status_code": response.status_code,
            "final_url": str(response.url),
            "request": redact_sensitive({"method": request["method"], "body": _resolve(request.get("body"), data)}),
            "response": redact_sensitive({"content_type": response.headers.get("content-type", ""), "body": response.text[:2000]}),
            "failures": failures,
        }
    except httpx.HTTPError as exc:
        return {"passed": False, "status_code": None, "final_url": url, "failures": [f"请求失败：{type(exc).__name__}"]}


def _success_rule_failures(response: httpx.Response, rules: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    payload: Any = None
    for rule in rules:
        kind = rule.get("kind")
        if kind == "status_code" and response.status_code not in rule.get("status_codes", []):
            failures.append(f"状态码 {response.status_code} 不在允许范围 {rule.get('status_codes', [])}")
            continue
        if kind in {"jsonpath_exists", "jsonpath_equals"}:
            if payload is None:
                try:
                    payload = response.json()
                except ValueError:
                    failures.append("响应不是 JSON")
                    continue
            exists, actual = _json_path(payload, str(rule.get("json_path") or ""))
            if kind == "jsonpath_exists" and not exists:
                failures.append(f"缺少字段 {rule.get('json_path')}")
            if kind == "jsonpath_equals" and (not exists or actual != rule.get("expected")):
                failures.append(f"字段 {rule.get('json_path')} 不符合预期")
    return failures


def _json_path(payload: Any, path: str) -> tuple[bool, Any]:
    current = payload
    for part in path.removeprefix("$").strip(".").split("."):
        if not part:
            continue
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _resolve(value: Any, data: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _resolve(item, data) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, data) for item in value]
    if not isinstance(value, str):
        return value
    resolved = value.replace("${sequence}", "1")
    for key, item in data.items():
        resolved = resolved.replace("${" + str(key) + "}", str(item))
    return resolved


def _normalize_target(target: str) -> str:
    return TARGET_ALIASES.get(target, target)


def _get_path(payload: dict[str, Any], target: str) -> Any:
    current: Any = payload
    for part in target.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_path(payload: dict[str, Any], target: str, value: Any) -> None:
    parts = target.split(".")
    current = payload
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _decode_json_literal(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _plan_hash(plan: dict[str, Any]) -> str:
    raw = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = ["apply_and_rerun", "is_supported_change"]
