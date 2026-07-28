import csv
import json
import re
from pathlib import Path
from typing import Any

from app.core.db import connect
from app.repositories import (
    api_automation_repo,
    performance_analysis_repo,
    performance_script_repo,
    performance_test_repo,
)
from app.services.performance_testing import run_repo


SENSITIVE_NAMES = {
    "authorization",
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "cybertron-robot-key",
    "cybertron-robot-token",
}
DEFAULT_TEXT_LIMIT = 4000
EVIDENCE_REDACTION_MARKER = {"redacted": True, "value_present": True}


def redact_sensitive(
    value: Any,
    *,
    key: str = "",
    max_text_length: int = DEFAULT_TEXT_LIMIT,
    redaction_marker: Any = "***",
) -> Any:
    normalized_key = key.strip().lower().replace("-", "_")
    if normalized_key in {name.replace("-", "_") for name in SENSITIVE_NAMES} or any(
        marker in normalized_key for marker in ("password", "secret", "token")
    ):
        return dict(redaction_marker) if isinstance(redaction_marker, dict) else redaction_marker
    if isinstance(value, dict):
        return {
            str(item_key): redact_sensitive(
                item,
                key=str(item_key),
                max_text_length=max_text_length,
                redaction_marker=redaction_marker,
            )
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [
            redact_sensitive(item, max_text_length=max_text_length, redaction_marker=redaction_marker)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            redact_sensitive(item, max_text_length=max_text_length, redaction_marker=redaction_marker)
            for item in value
        ]
    if isinstance(value, bytes):
        return {"type": "binary", "length": len(value)}
    if isinstance(value, str) and len(value) > max_text_length:
        return f"{value[:max_text_length]}…[truncated]"
    return value


def collect_performance_evidence(project_id: str, run_id: str) -> dict[str, Any]:
    with connect() as db:
        run = run_repo.get_run(db, run_id)
        if not run or run["project_id"] != project_id:
            raise LookupError("性能测试运行不存在")
        performance_test_row = performance_test_repo.find_performance_test(db, run["performance_test_id"])
        script_row = performance_script_repo.find_script(db, run["script_id"])
        endpoint_row = None
        if performance_test_row and performance_test_row["endpoint_id"]:
            endpoint_row = api_automation_repo.find_endpoint(db, performance_test_row["endpoint_id"])
        stats = [_stat_payload(row) for row in run_repo.list_stats(db, run_id)]
        failures = [dict(row) for row in run_repo.list_failures(db, run_id)]
        exceptions = [dict(row) for row in run_repo.list_exceptions(db, run_id)]
        events = [_event_payload(row) for row in run_repo.list_events(db, run_id)]
        source_analysis_row = performance_analysis_repo.find_analysis_for_applied_run(db, run_id)
        source_analysis = (
            performance_analysis_repo.serialize_analysis_session(source_analysis_row) if source_analysis_row else {}
        )
        history = [
            _run_summary(row)
            for row in run_repo.list_runs(db, project_id, run["performance_test_id"])
            if row["id"] != run_id
        ][:5]

    performance_test = performance_test_repo.serialize_performance_test(performance_test_row) if performance_test_row else {}
    script = performance_script_repo.serialize_script(script_row) if script_row else {}
    endpoint = _endpoint_payload(endpoint_row)
    runtime_config = _json_value(run["runtime_config_json"], {})
    request_execution_facts = _request_execution_facts(script, runtime_config)
    report_directory = Path(str(run["report_directory"] or "")) if run["report_directory"] else None
    artifacts, missing_evidence = _collect_artifacts(report_directory)
    prior_preflight = _prior_preflight_payload(source_analysis)
    diagnostic_constraints = _diagnostic_constraints(prior_preflight, request_execution_facts)
    if not endpoint:
        missing_evidence.append("openapi_endpoint")
    if not failures:
        missing_evidence.append("performance_failures")

    return redact_sensitive(
        {
            "run": _run_summary(run),
            "summary": _json_value(run["latest_summary_json"], {}),
            "stats": stats,
            "failures": failures,
            "exceptions": exceptions,
            "events": events,
            "performance_test": performance_test,
            "script": script,
            "endpoint": endpoint,
            "runtime_config": runtime_config,
            "request_execution_facts": request_execution_facts,
            "redaction_semantics": {
                "timing": "after_execution_during_ai_evidence_collection",
                "marker": EVIDENCE_REDACTION_MARKER,
                "meaning": "原值在运行时存在，但仅在 AI 证据中隐藏；该标记不是实际请求值。",
            },
            "prior_preflight": prior_preflight,
            "diagnostic_constraints": diagnostic_constraints,
            "historical_runs": history,
            "artifacts": artifacts,
            "missing_evidence": list(dict.fromkeys(missing_evidence)),
        },
        redaction_marker=EVIDENCE_REDACTION_MARKER,
    )


def _prior_preflight_payload(source_analysis: dict[str, Any]) -> dict[str, Any]:
    preflight = source_analysis.get("preflight") if isinstance(source_analysis.get("preflight"), dict) else {}
    if not preflight:
        return {}
    response = dict(preflight.get("response") or {})
    if isinstance(response.get("body"), str):
        response["body"] = _json_value(response["body"], response["body"])
    return {
        "source_analysis_id": source_analysis.get("id", ""),
        "passed": bool(preflight.get("passed")),
        "status_code": preflight.get("status_code"),
        "final_url": preflight.get("final_url", ""),
        "request": preflight.get("request", {}),
        "response": response,
        "failures": preflight.get("failures", []),
    }


def _request_execution_facts(script: dict[str, Any], runtime_config: dict[str, Any]) -> dict[str, Any]:
    plan = script.get("plan") if isinstance(script.get("plan"), dict) else {}
    request = plan.get("request") if isinstance(plan.get("request"), dict) else {}
    plan_headers = request.get("headers") if isinstance(request.get("headers"), dict) else {}
    runtime_headers = runtime_config.get("headers") if isinstance(runtime_config.get("headers"), dict) else {}
    managed_header_names = {
        str(name).lower()
        for name in runtime_config.get("managed_header_names", [])
        if isinstance(name, str)
    }
    overlapping_headers = set(plan_headers) & set(runtime_headers)
    data = plan.get("data") if isinstance(plan.get("data"), dict) else {}
    rows = data.get("json_rows") if isinstance(data.get("json_rows"), list) else []
    data_keys = {
        str(key)
        for row in rows
        if isinstance(row, dict)
        for key in row
    }
    builtins = {"sequence", "uuid", "timestamp", "random_int"}
    unresolved_templates: list[dict[str, Any]] = []
    for header, value in plan_headers.items():
        variables = re.findall(r"\$\{([^}]+)\}", value) if isinstance(value, str) else []
        unresolved = sorted(set(variables) - data_keys - builtins)
        if unresolved:
            unresolved_templates.append(
                {
                    "header_name": str(header),
                    "variable_names": unresolved,
                }
            )
    return {
        "evidence_redaction_timing": "after_execution",
        "redaction_marker_is_runtime_value": False,
        "request_header_merge_precedence": "script_plan_except_environment_managed_auth",
        "runtime_headers_overridden_by_plan": sorted(
            name for name in overlapping_headers if name.lower() not in managed_header_names
        ),
        "environment_managed_headers_protected": sorted(
            name for name in overlapping_headers if name.lower() in managed_header_names
        ),
        "unresolved_plan_header_templates": unresolved_templates,
    }


def _diagnostic_constraints(
    prior_preflight: dict[str, Any],
    request_execution_facts: dict[str, Any],
) -> dict[str, Any]:
    status_code = prior_preflight.get("status_code")
    constraints: dict[str, Any] = {"rules": []}
    if isinstance(status_code, int) and 200 <= status_code < 400:
        constraints.update(
            {
                "route_reachability": "confirmed_by_prior_preflight",
                "verified_url": prior_preflight.get("final_url", ""),
            }
        )
        constraints["rules"].extend([
            "先前预检已从目标环境访问到该 URL，不得将路径不存在、接口未部署或 base URL 错误表述为已证实根因。",
            "HTTP 2xx 只证明路由可达；是否业务成功仍须检查响应业务字段和成功规则。",
            "若单请求预检可达而并发压测失败，应优先比较请求差异、并发策略、网关/WAF/限流行为；缺少响应体或服务端日志时使用 insufficient_evidence。",
        ])
    constraints["rules"].append(
        "所有 redacted=true 的对象都是运行结束后构造 AI 证据时产生的脱敏标记，不是实际运行值；不得声称请求发送了该标记。"
    )
    if request_execution_facts.get("unresolved_plan_header_templates"):
        constraints["rules"].append(
            "request_execution_facts.unresolved_plan_header_templates 是按脚本解析规则确定的未解析模板；应据此判断脚本发送了未解析模板字符串，而不是脱敏标记。"
        )
    return constraints


def has_analyzable_evidence(bundle: dict[str, Any]) -> bool:
    summary = bundle.get("summary") if isinstance(bundle.get("summary"), dict) else {}
    return bool(
        int(summary.get("request_count") or 0)
        or bundle.get("failures")
        or bundle.get("exceptions")
        or bundle.get("events")
        or bundle.get("artifacts", {}).get("locust_events")
    )


def _collect_artifacts(report_directory: Path | None) -> tuple[dict[str, Any], list[str]]:
    artifacts: dict[str, Any] = {}
    missing: list[str] = []
    expected = {
        "locust_events": "locust-events.jsonl",
        "result_failures": "result_failures.csv",
        "result_exceptions": "result_exceptions.csv",
        "generated_locustfile": "generated_locustfile.py",
        "effective_locustfile": "locustfile.py",
    }
    if report_directory is None or not report_directory.is_dir():
        return artifacts, list(expected.values())
    for key, file_name in expected.items():
        path = report_directory / file_name
        if not path.is_file():
            missing.append(file_name)
            continue
        if path.suffix == ".jsonl":
            artifacts[key] = _read_jsonl(path)
        elif path.suffix == ".csv":
            artifacts[key] = _read_csv(path)
        else:
            artifacts[key] = path.read_text(encoding="utf-8", errors="replace")[:12000]
    return artifacts, missing


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:200]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))[:200]


def _endpoint_payload(row) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "id": row["id"],
        "method": row["method"],
        "path": row["path"],
        "summary": row["summary"],
        "description": row["description"],
        "parameters": _json_value(row["parameters_json"], []),
        "request_body": _json_value(row["request_body_json"], {}),
        "responses": _json_value(row["responses_json"], {}),
    }


def _run_summary(row) -> dict[str, Any]:
    status = str(row["status"] or "")
    termination_reason = {
        "completed": "completed",
        "stopped": "manual_stop",
        "failed": "engine_error",
        "cancelled": "cancelled",
    }.get(status, "unknown")
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "performance_test_id": row["performance_test_id"],
        "script_id": row["script_id"],
        "status": row["status"],
        "termination_reason": termination_reason,
        "termination_label": {
            "completed": "正常完成",
            "manual_stop": "人工停止",
            "engine_error": "运行失败",
            "cancelled": "已取消",
            "unknown": "未知",
        }[termination_reason],
        "load_config": _json_value(row["load_config_json"], {}),
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "trace_id": row["trace_id"],
    }


def _stat_payload(row) -> dict[str, Any]:
    payload = dict(row)
    payload.update(_json_value(payload.pop("stats_json", "{}"), {}))
    return payload


def _event_payload(row) -> dict[str, Any]:
    payload = dict(row)
    payload["payload"] = _json_value(payload.pop("payload_json", "{}"), {})
    return payload


def _json_value(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default
