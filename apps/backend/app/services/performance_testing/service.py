import csv
import json
import re
import secrets
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from app.core import settings
from app.core.db import connect
from app.core.environment_credentials import decrypt_api_environment_secret
from app.core.exceptions import api_error
from app.repositories import api_automation_repo, performance_script_repo, performance_test_repo, project_repo
from app.schemas.performance_test import (
    PerformanceRequestPreviewIn,
    PerformanceSseRulePreviewIn,
    PerformanceTestCreateIn,
    PerformanceTestUpdateIn,
)
from app.services import operation_log_service


SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
}
ENVIRONMENT_AUTH_HEADER_NAMES = {
    "cybertron-robot-key",
    "cybertron-robot-token",
}


def list_performance_tests(project_id: str, actor) -> list[dict[str, Any]]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        return [
            performance_test_repo.serialize_performance_test(row)
            for row in performance_test_repo.list_performance_tests(db, project_id)
        ]


def get_performance_test(project_id: str, test_id: str, actor) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = _require_performance_test(db, project_id, test_id)
        return performance_test_repo.serialize_performance_test(row)


def preview_performance_request(
    project_id: str,
    payload: PerformanceRequestPreviewIn,
    actor,
) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        endpoint, environment = _validate_references(
            db,
            project_id,
            endpoint_id=payload.endpoint_id,
            api_environment_id=payload.api_environment_id,
            require_environment=False,
        )
        positive_case = _select_positive_case(db, project_id, endpoint["id"])
        return _build_request_preview(endpoint, environment, positive_case)


def preview_sse_rules(project_id: str, payload: PerformanceSseRulePreviewIn, actor) -> dict[str, Any]:
    """Validate parsing and matching locally; the sample is never persisted."""
    from app.services.performance_testing.sse import event_matches, parse_sse_events

    with connect() as db:
        _require_visible_project(db, project_id, actor)
    events = parse_sse_events(payload.sample.splitlines(), max_frame_bytes=262_144)
    if len(events) > 500:
        raise api_error(400, "PERFORMANCE_SSE_SAMPLE_LIMIT", "SSE 样例事件数不能超过 500。")
    matches: list[dict[str, Any]] = []
    for metric in payload.sse.metrics:
        index = next(
            (index + 1 for index, event in enumerate(events) if event_matches(event, metric.match.model_dump(mode="json"))),
            None,
        )
        matches.append({"metric_id": metric.id, "event_index": index, "matched": index is not None})
    end_index = None
    if payload.sse.end_rule is not None:
        end_rule = payload.sse.end_rule.model_dump(mode="json")
        end_index = next((index + 1 for index, event in enumerate(events) if event_matches(event, end_rule)), None)
    return {
        "event_count": len(events),
        "events": [{"index": index + 1, "event_name": event.event_name, "data_length": len(event.data_text)} for index, event in enumerate(events)],
        "metrics": matches,
        "end_rule_event_index": end_index,
    }


def create_performance_test(project_id: str, payload: PerformanceTestCreateIn, actor) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        endpoint, scenario, environment = _validate_target_references(
            db,
            project_id,
            target_type=payload.target_type,
            endpoint_id=payload.endpoint_id,
            scenario_id=payload.scenario_id,
            api_environment_id=payload.api_environment_id,
        )
        request_config = payload.request_config.model_dump(mode="json")
        request_config["headers"] = {
            **dict(request_config.get("headers") or {}),
            **_environment_runtime_headers(environment),
        }
        success_rules = _minimal_success_rules(
            [rule.model_dump(mode="json") for rule in payload.success_rules]
        )
        if endpoint is not None and "success_rules" not in payload.model_fields_set:
            success_rules = _documented_success_rules(endpoint)
        test_id = f"perftest-{secrets.token_hex(8)}"
        data_config = payload.data_config.model_dump(mode="json")
        csv_target = _csv_data_target(project_id, test_id, data_config)
        if csv_target:
            data_config["csv_file_path"] = csv_target[0]
        try:
            performance_test_repo.create_performance_test(
                db,
                test_id=test_id,
                project_id=project_id,
                name=payload.name.strip(),
                description=payload.description.strip(),
                target_type=payload.target_type,
                endpoint_id=payload.endpoint_id,
                scenario_id=payload.scenario_id,
                api_environment_id=payload.api_environment_id,
                request_config=request_config,
                load_config=payload.load_config.model_dump(mode="json"),
                data_config=data_config,
                circuit_breaker=payload.circuit_breaker.model_dump(mode="json"),
                performance_goal=payload.performance_goal.model_dump(mode="json", exclude_none=True),
                success_rules=success_rules,
                created_by=actor["id"],
            )
            if csv_target:
                _write_csv_data(csv_target[1], data_config["json_rows"])
        except sqlite3.IntegrityError as exc:
            if "performance_tests.project_id, performance_tests.name" in str(exc):
                raise api_error(409, "PERFORMANCE_TEST_NAME_CONFLICT", "当前项目已存在同名性能测试。") from exc
            raise
        row = _require_performance_test(db, project_id, test_id)
        result = performance_test_repo.serialize_performance_test(row)
    operation_log_service.record_change(
        log_type="audit",
        module="performance_testing",
        action="create",
        object_type="performance_test",
        object_id=test_id,
        object_name=payload.name,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"创建性能测试：{payload.name}",
        after={"name": payload.name, "endpoint_id": payload.endpoint_id, "scenario_id": payload.scenario_id},
    )
    return result


def _csv_data_target(project_id: str, test_id: str, data_config: dict[str, Any]) -> tuple[str, Path] | None:
    if data_config.get("source") != "csv":
        return None
    file_name = Path(str(data_config.get("csv_file_name") or "data.csv")).name
    if not file_name.lower().endswith(".csv"):
        file_name = f"{file_name}.csv"
    relative = Path(project_id) / "performance_testing" / "data" / test_id / file_name
    return relative.as_posix(), settings.PROJECT_FILE_STORAGE_ROOT / relative


def _write_csv_data(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    field_names = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_names, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def update_performance_test(
    project_id: str,
    test_id: str,
    payload: PerformanceTestUpdateIn,
    actor,
) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        current = _require_performance_test(db, project_id, test_id)
        current_data = performance_test_repo.serialize_performance_test(current)
        raw_fields = payload.model_dump(exclude_unset=True)
        target_type = str(raw_fields.get("target_type", current["target_type"]))
        endpoint_id = raw_fields.get("endpoint_id", current["endpoint_id"])
        scenario_id = raw_fields.get("scenario_id", current["scenario_id"])
        api_environment_id = raw_fields.get("api_environment_id", current["api_environment_id"])
        _, _, environment = _validate_target_references(
            db,
            project_id,
            target_type=target_type,
            endpoint_id=endpoint_id,
            scenario_id=scenario_id,
            api_environment_id=api_environment_id,
        )
        normalized_request_config = None
        if payload.request_config is not None:
            normalized_request_config = payload.request_config.model_dump(mode="json")
            normalized_request_config["headers"] = {
                **dict(normalized_request_config.get("headers") or {}),
                **_environment_runtime_headers(environment),
            }

        from app.schemas.performance_test import validate_sse_goal_references

        effective_request_config = normalized_request_config or current_data.get("request_config") or {}
        effective_performance_goal = (
            payload.performance_goal.model_dump(mode="json", exclude_none=True)
            if payload.performance_goal is not None
            else current_data.get("performance_goal") or {}
        )
        validate_sse_goal_references(effective_request_config, effective_performance_goal)

        fields: dict[str, Any] = {}
        for field in payload.model_fields_set:
            value = getattr(payload, field)
            if field == "request_config" and normalized_request_config is not None:
                fields[field] = normalized_request_config
            elif field in {"load_config", "data_config", "circuit_breaker", "performance_goal"} and value is not None:
                fields[field] = value.model_dump(
                    mode="json",
                    exclude_none=True,
                    exclude_unset=field == "performance_goal",
                )
            elif field == "success_rules" and value is not None:
                fields[field] = _minimal_success_rules([rule.model_dump(mode="json") for rule in value])
            elif field in {"name", "description"} and isinstance(value, str):
                fields[field] = value.strip()
            else:
                fields[field] = value
        try:
            performance_test_repo.update_performance_test(db, test_id, fields)
        except sqlite3.IntegrityError as exc:
            if "performance_tests.project_id, performance_tests.name" in str(exc):
                raise api_error(409, "PERFORMANCE_TEST_NAME_CONFLICT", "当前项目已存在同名性能测试。") from exc
            raise
        row = _require_performance_test(db, project_id, test_id)
        result = performance_test_repo.serialize_performance_test(row)
    operation_log_service.record_change(
        log_type="audit",
        module="performance_testing",
        action="update",
        object_type="performance_test",
        object_id=test_id,
        object_name=current_data.get("name"),
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"更新性能测试：{current_data.get('name')}",
        before={"name": current_data.get("name"), "description": current_data.get("description")},
        after={"name": result.get("name"), "description": result.get("description")},
    )
    return result


def delete_performance_test(project_id: str, test_id: str, actor) -> None:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        current = _require_performance_test(db, project_id, test_id)
        current_data = performance_test_repo.serialize_performance_test(current)
        runs = db.execute(
            "SELECT id, status FROM performance_test_runs WHERE project_id = ? AND performance_test_id = ?",
            (project_id, test_id),
        ).fetchall()
    _stop_active_test_runs(runs)

    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _require_performance_test(db, project_id, test_id)
        runs = db.execute(
            "SELECT id, status FROM performance_test_runs WHERE project_id = ? AND performance_test_id = ?",
            (project_id, test_id),
        ).fetchall()
    _stop_active_test_runs(runs)

    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _require_performance_test(db, project_id, test_id)
        runs = db.execute(
            "SELECT id, status FROM performance_test_runs WHERE project_id = ? AND performance_test_id = ?",
            (project_id, test_id),
        ).fetchall()
        run_ids = [row["id"] for row in runs]
        performance_script_repo.delete_scripts_by_test(db, test_id)
        performance_test_repo.delete_performance_test(db, test_id)
    _cleanup_test_artifacts(project_id, test_id, run_ids)
    operation_log_service.record_change(
        log_type="audit",
        module="performance_testing",
        action="delete",
        object_type="performance_test",
        object_id=test_id,
        object_name=current_data.get("name"),
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"删除性能测试：{current_data.get('name')}",
        before={"name": current_data.get("name"), "description": current_data.get("description")},
    )


def _validate_references(
    db,
    project_id: str,
    *,
    endpoint_id: str | None,
    api_environment_id: str | None,
    require_environment: bool = True,
) -> tuple[Any, Any]:
    endpoint = api_automation_repo.find_endpoint(db, endpoint_id) if endpoint_id else None
    if not endpoint or endpoint["project_id"] != project_id:
        raise api_error(400, "PERFORMANCE_ENDPOINT_INVALID", "性能测试接口不存在或不属于当前项目。")
    environment = api_automation_repo.find_api_environment(db, api_environment_id) if api_environment_id else None
    if require_environment and (not environment or environment["project_id"] != project_id):
        raise api_error(400, "PERFORMANCE_ENVIRONMENT_INVALID", "API 环境不存在或不属于当前项目。")
    if environment and environment["project_id"] != project_id:
        raise api_error(400, "PERFORMANCE_ENVIRONMENT_INVALID", "API 环境不存在或不属于当前项目。")
    return endpoint, environment


def _validate_target_references(
    db,
    project_id: str,
    *,
    target_type: str,
    endpoint_id: str | None,
    scenario_id: str | None,
    api_environment_id: str | None,
) -> tuple[Any, Any, Any]:
    endpoint = None
    scenario = None
    if target_type == "endpoint":
        if not endpoint_id or scenario_id:
            raise api_error(400, "PERFORMANCE_TARGET_INVALID", "接口性能测试必须且只能选择一个接口。")
        endpoint = api_automation_repo.find_endpoint(db, endpoint_id)
        if not endpoint or endpoint["project_id"] != project_id:
            raise api_error(400, "PERFORMANCE_ENDPOINT_INVALID", "性能测试接口不存在或不属于当前项目。")
    elif target_type == "scenario":
        if not scenario_id or endpoint_id:
            raise api_error(400, "PERFORMANCE_TARGET_INVALID", "场景性能测试必须且只能选择一个接口场景。")
        scenario = db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone()
        if not scenario or scenario["project_id"] != project_id:
            raise api_error(400, "PERFORMANCE_SCENARIO_INVALID", "接口场景不存在或不属于当前项目。")
    else:
        raise api_error(400, "PERFORMANCE_TARGET_INVALID", "不支持的性能测试目标类型。")

    environment = api_automation_repo.find_api_environment(db, api_environment_id) if api_environment_id else None
    if not environment or environment["project_id"] != project_id:
        raise api_error(400, "PERFORMANCE_ENVIRONMENT_INVALID", "API 环境不存在或不属于当前项目。")
    return endpoint, scenario, environment


def _documented_success_codes(endpoint) -> list[int]:
    responses = api_automation_repo.loads_json(endpoint["responses_json"], {})
    codes = sorted(
        {
            int(code)
            for code in responses
            if str(code).isdigit() and 200 <= int(code) < 300
        }
    )
    return codes or [200]


def _build_request_preview(endpoint, environment=None, positive_case=None) -> dict[str, Any]:
    provenance: dict[str, str] = {}
    warnings: list[str] = []
    path_parameters: dict[str, Any] = {}
    query_parameters: dict[str, Any] = {}
    headers: dict[str, Any] = {}
    environment_headers = _environment_runtime_headers(environment)
    headers.update(environment_headers)
    for name in environment_headers:
        provenance[f"headers.{name}"] = "environment"

    for parameter in api_automation_repo.loads_json(endpoint["parameters_json"], []):
        if not isinstance(parameter, dict):
            continue
        name = str(parameter.get("name", "")).strip()
        location = str(parameter.get("in", "")).strip()
        if not name or location not in {"path", "query", "header"}:
            continue
        if location == "header":
            # Prefer environment header value if available
            if name.lower() in {k.lower() for k in environment_headers}:
                env_key = next(k for k in environment_headers if k.lower() == name.lower())
                headers[name] = environment_headers[env_key]
                provenance[f"headers.{name}"] = "environment"
                continue
        value, source = _parameter_value(parameter)
        target = {"path": path_parameters, "query": query_parameters, "header": headers}[location]
        target[name] = value
        provenance[f"{location}_parameters.{name}" if location != "header" else f"headers.{name}"] = source

    body, body_source = _request_body_value(api_automation_repo.loads_json(endpoint["request_body_json"], {}))
    if body_source:
        provenance["body"] = body_source

    success_rules = _documented_success_rules(endpoint)
    if positive_case is not None:
        case_request = api_automation_repo.loads_json(positive_case["request_json"], {})
        case_headers = case_request.get("headers") if isinstance(case_request.get("headers"), dict) else {}
        headers.update(case_headers)
        if "body" in case_request:
            body = case_request["body"]
            provenance["body"] = "positive_api_test_case"
        success_rules = _positive_case_success_rules(positive_case, success_rules)
        provenance["positive_case_id"] = positive_case["id"]
    provenance["success_rules"] = "positive_api_test_case" if positive_case is not None else "openapi_response"
    return {
        "endpoint": {
            "id": endpoint["id"],
            "method": endpoint["method"],
            "path": endpoint["path"],
            "name": endpoint["summary"] or endpoint["path"],
        },
        "request_config": {
            "path_parameters": path_parameters,
            "query_parameters": query_parameters,
            "headers": headers,
            "body": body,
            "random_seed": None,
        },
        "success_rules": success_rules,
        "provenance": provenance,
        "warnings": list(dict.fromkeys(warnings)),
    }


def _select_positive_case(db, project_id: str, endpoint_id: str):
    cases = [
        row
        for row in api_automation_repo.list_api_test_cases(db, project_id, endpoint_id=endpoint_id)
        if row["coverage"] == "positive"
    ]
    if not cases:
        return None
    rank = {"confirmed": 0, "inferred": 1, "needs_confirmation": 2}
    best_rank = min(rank.get(str(row["oracle_status"]), 3) for row in cases)
    preferred = [row for row in cases if rank.get(str(row["oracle_status"]), 3) == best_rank]
    return max(preferred, key=lambda row: (str(row["updated_at"]), row["id"]))


def _positive_case_success_rules(positive_case, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for assertion in api_automation_repo.loads_json(positive_case["assertions_json"], []):
        if not isinstance(assertion, dict):
            continue
        kind = str(assertion.get("type") or "")
        if kind == "status_code":
            expected = assertion.get("expected")
            codes = expected if isinstance(expected, list) else [expected]
            valid_codes = [code for code in codes if isinstance(code, int) and 100 <= code <= 599]
            if valid_codes:
                rules.append({"kind": "status_code", "status_codes": valid_codes})
        elif kind in {"jsonpath_exists", "jsonpath_equals"} and str(assertion.get("path") or "").strip():
            rule = {"kind": kind, "json_path": str(assertion["path"])}
            if kind == "jsonpath_equals":
                rule["expected"] = assertion.get("expected")
            rules.append(rule)
    status_rule = next((rule for rule in rules if rule["kind"] == "status_code"), None)
    if status_rule is None:
        status_rule = next((rule for rule in fallback if rule["kind"] == "status_code"), None)

    equals_rules = [rule for rule in rules if rule["kind"] == "jsonpath_equals"]
    if not equals_rules:
        equals_rules = [rule for rule in fallback if rule["kind"] == "jsonpath_equals"]
    business_rule = next((rule for rule in equals_rules if rule["json_path"] == "$.code"), None)
    if business_rule is None:
        business_rule = next(iter(equals_rules), None)

    selected = [rule for rule in (status_rule, business_rule) if rule is not None]
    return _minimal_success_rules(selected or fallback)


def _minimal_success_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    equals_paths = {
        str(rule.get("json_path") or "")
        for rule in rules
        if rule.get("kind") == "jsonpath_equals" and str(rule.get("json_path") or "")
    }
    minimal: list[dict[str, Any]] = []
    for rule in rules:
        if rule.get("kind") == "jsonpath_exists" and str(rule.get("json_path") or "") in equals_paths:
            continue
        if rule not in minimal:
            minimal.append(rule)
    return minimal


def _documented_success_rules(endpoint) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = [
        {"kind": "status_code", "status_codes": _documented_success_codes(endpoint)}
    ]
    responses = api_automation_repo.loads_json(endpoint["responses_json"], {})
    for status, response in responses.items():
        if not str(status).isdigit() or not 200 <= int(status) < 300 or not isinstance(response, dict):
            continue
        content = response.get("content") if isinstance(response.get("content"), dict) else {}
        for media in content.values():
            if not isinstance(media, dict):
                continue
            examples = media.get("examples") if isinstance(media.get("examples"), dict) else {}
            candidates = [media.get("example"), *(item.get("value") for item in examples.values() if isinstance(item, dict))]
            sample = next((item for item in candidates if isinstance(item, dict)), None)
            if sample and sample.get("code") is not None:
                rules.append({"kind": "jsonpath_equals", "json_path": "$.code", "expected": sample["code"]})
                return rules
    return rules


def _environment_managed_header_names(environment) -> set[str]:
    managed = set(ENVIRONMENT_AUTH_HEADER_NAMES)
    if environment is None:
        return managed
    auth_type = str(environment["auth_type"] or "")
    auth_config = api_automation_repo.loads_json(environment["auth_config_json"], {})
    if auth_type == "static_bearer":
        managed.add("authorization")
    if auth_type == "static_headers":
        managed.update(str(name).lower() for name in auth_config.get("headers_encrypted", {}))
    if auth_type == "cookie":
        managed.add("cookie")
    if auth_type == "cybertron_agent":
        managed.add("username")
    return managed


def _environment_runtime_headers(row) -> dict[str, str]:
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


def _parameter_value(parameter: dict[str, Any]) -> tuple[Any, str]:
    if "example" in parameter:
        return parameter["example"], "openapi_example"
    schema = parameter.get("schema") if isinstance(parameter.get("schema"), dict) else {}
    if "example" in schema:
        return schema["example"], "openapi_example"
    if "default" in schema:
        return schema["default"], "openapi_default"
    return _schema_placeholder(schema), "openapi_schema"


def _request_body_value(request_body: dict[str, Any]) -> tuple[Any, str]:
    content = request_body.get("content")
    if not isinstance(content, dict) or not content:
        return None, ""
    media = content.get("application/json")
    if not isinstance(media, dict):
        media = next((value for value in content.values() if isinstance(value, dict)), {})
    if "example" in media:
        return media["example"], "openapi_example"
    schema = media.get("schema") if isinstance(media.get("schema"), dict) else {}
    if "example" in schema:
        return schema["example"], "openapi_example"
    if "default" in schema:
        return schema["default"], "openapi_default"
    return _schema_placeholder(schema), "openapi_schema"


def _string_placeholder(schema: dict[str, Any]) -> str:
    min_length = max(int(schema.get("minLength") or 0), 1)
    max_length = int(schema.get("maxLength") or 0)
    pattern = schema.get("pattern")
    if pattern:
        return _pattern_sample(pattern, min_length)
    if min_length == 1:
        return "a"
    if min_length <= 3:
        return "abc"
    if min_length <= 8:
        return "sample"
    if max_length and max_length <= 32:
        return "text"[:min_length] + "x" * (min_length - 4)
    return "sample_text"


def _pattern_sample(pattern: str, min_length: int) -> str:
    # Remove anchors and quantifiers for simpler matching
    clean = re.sub(r"[\^\$]|\{\d+(?:,\d*)?\}|\+|\*|\?|\(|\)", "", pattern)
    if not clean:
        return "a" * max(min_length, 4)
    # Extract meaningful characters from character classes
    result = []
    i = 0
    while i < len(clean):
        if clean[i] == "[":
            end = clean.find("]", i)
            if end > i + 1:
                chars = clean[i + 1 : end]
                chars = chars.lstrip("^")
                result.append(chars[0] if chars else "a")
                i = end + 1
            else:
                result.append("a")
                i += 1
        elif clean[i] == "\\":
            if i + 1 < len(clean):
                esc = clean[i + 1]
                result.append({"d": "1", "D": "a", "w": "a", "W": "!"}.get(esc, "a"))
                i += 2
            else:
                result.append("a")
                i += 1
        else:
            result.append(clean[i])
            i += 1
    while len(result) < min_length:
        result.extend(result)
    return "".join(result[:max(min_length, 4)])[:64]


def _schema_placeholder(schema: dict[str, Any], depth: int = 0) -> Any:
    if depth >= 5 or "$ref" in schema:
        return {}
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        return enum_values[0]
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((value for value in schema_type if value != "null"), "null")
    schema_format = schema.get("format")
    if schema_type == "string":
        if schema_format == "uuid":
            return "${uuid}"
        if schema_format == "date":
            return "2026-01-01"
        if schema_format == "date-time":
            return "${timestamp}"
        if schema_format == "email":
            return "user@example.com"
        if schema_format == "uri":
            return "https://example.com/path"
        if schema_format == "hostname":
            return "example.com"
        if schema_format == "ipv4":
            return "192.168.1.1"
        if schema_format == "ipv6":
            return "::1"
        if schema_format == "byte":
            return "${base64_content}"
        if schema_format == "binary":
            return "${binary_content}"
        return _string_placeholder(schema)
    if schema_type in {"integer", "number"}:
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)):
            return int(minimum) if schema_type == "integer" else minimum
        maximum = schema.get("maximum")
        if isinstance(maximum, (int, float)):
            return int(maximum) if schema_type == "integer" else maximum
        return 1
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        items = schema.get("items")
        item_count = max(int(schema.get("minItems") or 1), 1)
        return [_schema_placeholder(items, depth + 1) for _ in range(min(item_count, 3))] if isinstance(items, dict) else []
    if schema_type == "object" or isinstance(schema.get("properties"), dict):
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = set(schema.get("required") or [])
        explicit = {
            name
            for name, value in properties.items()
            if isinstance(value, dict) and any(key in value for key in ("example", "default"))
        }
        selected = required | explicit
        return {
            name: _schema_placeholder(value, depth + 1)
            for name, value in properties.items()
            if name in selected and isinstance(value, dict)
        }
    return None


def _require_visible_project(db, project_id: str, actor):
    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "NOT_FOUND", "项目不存在。")
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return project
    if project["name"] == actor["project_scope"]:
        return project
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _require_performance_test(db, project_id: str, test_id: str):
    row = performance_test_repo.find_performance_test(db, test_id)
    if not row or row["project_id"] != project_id:
        raise api_error(404, "PERFORMANCE_TEST_NOT_FOUND", "性能测试不存在。")
    return row


def _stop_active_test_runs(runs) -> None:
    from app.services.performance_testing import headless_worker

    for run in runs:
        if run["status"] not in {"starting", "running", "stopping"}:
            continue
        if not headless_worker.stop_headless_run_and_wait(run["id"]):
            raise api_error(
                409,
                "PERFORMANCE_TEST_RUN_STOP_TIMEOUT",
                "终止运行中的压测超时，请稍后重试删除。",
            )


def _cleanup_test_artifacts(project_id: str, test_id: str, run_ids: list[str]) -> None:
    perf_root = settings.PROJECT_FILE_STORAGE_ROOT / project_id / "performance_testing"
    for run_id in run_ids:
        shutil.rmtree(perf_root / "runs" / run_id, ignore_errors=True)
    shutil.rmtree(perf_root / "data" / test_id, ignore_errors=True)
