import secrets
import sqlite3
from typing import Any

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import api_automation_repo, performance_test_repo, project_repo
from app.schemas.performance_test import PerformanceRequestPreviewIn, PerformanceTestCreateIn, PerformanceTestUpdateIn


SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
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
        endpoint, _, source_case = _validate_references(
            db,
            project_id,
            endpoint_id=payload.endpoint_id,
            api_environment_id=None,
            source_api_test_case_id=payload.source_api_test_case_id,
            require_environment=False,
        )
        return _build_request_preview(endpoint, source_case)


def create_performance_test(project_id: str, payload: PerformanceTestCreateIn, actor) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        endpoint, _, _ = _validate_references(
            db,
            project_id,
            endpoint_id=payload.endpoint_id,
            api_environment_id=payload.api_environment_id,
            source_api_test_case_id=payload.source_api_test_case_id,
        )
        _validate_non_sensitive_headers(payload.request_config.headers)
        success_rules = [rule.model_dump(mode="json", exclude_none=True) for rule in payload.success_rules]
        if "success_rules" not in payload.model_fields_set:
            success_rules = [{"kind": "status_code", "status_codes": _documented_success_codes(endpoint)}]
        test_id = f"perftest-{secrets.token_hex(8)}"
        try:
            performance_test_repo.create_performance_test(
                db,
                test_id=test_id,
                project_id=project_id,
                name=payload.name.strip(),
                description=payload.description.strip(),
                target_type=payload.target_type,
                endpoint_id=payload.endpoint_id,
                api_environment_id=payload.api_environment_id,
                source_api_test_case_id=payload.source_api_test_case_id,
                request_config=payload.request_config.model_dump(mode="json"),
                load_config=payload.load_config.model_dump(mode="json"),
                performance_goal=payload.performance_goal.model_dump(mode="json", exclude_none=True),
                success_rules=success_rules,
                created_by=actor["id"],
            )
        except sqlite3.IntegrityError as exc:
            if "performance_tests.project_id, performance_tests.name" in str(exc):
                raise api_error(409, "PERFORMANCE_TEST_NAME_CONFLICT", "当前项目已存在同名性能测试。") from exc
            raise
        row = _require_performance_test(db, project_id, test_id)
        return performance_test_repo.serialize_performance_test(row)


def update_performance_test(
    project_id: str,
    test_id: str,
    payload: PerformanceTestUpdateIn,
    actor,
) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        current = _require_performance_test(db, project_id, test_id)
        raw_fields = payload.model_dump(exclude_unset=True)
        endpoint_id = raw_fields.get("endpoint_id", current["endpoint_id"])
        api_environment_id = raw_fields.get("api_environment_id", current["api_environment_id"])
        source_api_test_case_id = raw_fields.get("source_api_test_case_id", current["source_api_test_case_id"])
        _validate_references(
            db,
            project_id,
            endpoint_id=endpoint_id,
            api_environment_id=api_environment_id,
            source_api_test_case_id=source_api_test_case_id,
        )
        if payload.request_config is not None:
            _validate_non_sensitive_headers(payload.request_config.headers)

        fields: dict[str, Any] = {}
        for field in payload.model_fields_set:
            value = getattr(payload, field)
            if field in {"request_config", "load_config", "performance_goal"} and value is not None:
                fields[field] = value.model_dump(mode="json", exclude_none=field == "performance_goal")
            elif field == "success_rules" and value is not None:
                fields[field] = [rule.model_dump(mode="json", exclude_none=True) for rule in value]
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
        return performance_test_repo.serialize_performance_test(row)


def delete_performance_test(project_id: str, test_id: str, actor) -> None:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _require_performance_test(db, project_id, test_id)
        if performance_test_repo.has_runs(db, test_id):
            raise api_error(409, "PERFORMANCE_TEST_HAS_RUNS", "已有运行记录的性能测试不能删除。")
        performance_test_repo.delete_performance_test(db, test_id)


def _validate_references(
    db,
    project_id: str,
    *,
    endpoint_id: str | None,
    api_environment_id: str | None,
    source_api_test_case_id: str | None,
    require_environment: bool = True,
) -> tuple[Any, Any, Any | None]:
    endpoint = api_automation_repo.find_endpoint(db, endpoint_id) if endpoint_id else None
    if not endpoint or endpoint["project_id"] != project_id:
        raise api_error(400, "PERFORMANCE_ENDPOINT_INVALID", "性能测试接口不存在或不属于当前项目。")
    environment = api_automation_repo.find_api_environment(db, api_environment_id) if api_environment_id else None
    if require_environment and (not environment or environment["project_id"] != project_id):
        raise api_error(400, "PERFORMANCE_ENVIRONMENT_INVALID", "API 环境不存在或不属于当前项目。")
    if environment and environment["project_id"] != project_id:
        raise api_error(400, "PERFORMANCE_ENVIRONMENT_INVALID", "API 环境不存在或不属于当前项目。")
    if source_api_test_case_id:
        case = api_automation_repo.find_api_test_case(db, source_api_test_case_id)
        if not case or case["project_id"] != project_id:
            raise api_error(400, "PERFORMANCE_SOURCE_CASE_INVALID", "请求数据来源用例不存在或不属于当前项目。")
        if case["endpoint_id"] and case["endpoint_id"] != endpoint_id:
            raise api_error(400, "PERFORMANCE_SOURCE_CASE_ENDPOINT_MISMATCH", "请求数据来源用例不属于所选接口。")
    else:
        case = None
    return endpoint, environment, case


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


def _build_request_preview(endpoint, source_case) -> dict[str, Any]:
    provenance: dict[str, str] = {}
    warnings: list[str] = []
    path_parameters: dict[str, Any] = {}
    query_parameters: dict[str, Any] = {}
    headers: dict[str, Any] = {}

    for parameter in api_automation_repo.loads_json(endpoint["parameters_json"], []):
        if not isinstance(parameter, dict):
            continue
        name = str(parameter.get("name", "")).strip()
        location = str(parameter.get("in", "")).strip()
        if not name or location not in {"path", "query", "header"}:
            continue
        if location == "header" and name.lower() in SENSITIVE_HEADER_NAMES:
            warnings.append(f"敏感 Header {name} 将由接口自动化环境注入。")
            continue
        value, source = _parameter_value(parameter)
        target = {"path": path_parameters, "query": query_parameters, "header": headers}[location]
        target[name] = value
        provenance[f"{location}_parameters.{name}" if location != "header" else f"headers.{name}"] = source

    body, body_source = _request_body_value(api_automation_repo.loads_json(endpoint["request_body_json"], {}))
    if body_source:
        provenance["body"] = body_source

    success_codes = _documented_success_codes(endpoint)
    success_source = "openapi_response"
    if source_case:
        request = api_automation_repo.loads_json(source_case["request_json"], {})
        test_data = api_automation_repo.loads_json(source_case["test_data_json"], {})
        for name in path_parameters:
            if name in test_data:
                path_parameters[name] = _test_data_value(test_data[name])
                provenance[f"path_parameters.{name}"] = "api_test_case"
        for key, value in _mapping(request.get("query") or request.get("query_params")).items():
            query_parameters[key] = value
            provenance[f"query_parameters.{key}"] = "api_test_case"
        for key, value in _mapping(request.get("headers")).items():
            if key.lower() in SENSITIVE_HEADER_NAMES:
                warnings.append(f"用例中的敏感 Header {key} 已忽略，将由接口自动化环境注入。")
                continue
            headers[key] = value
            provenance[f"headers.{key}"] = "api_test_case"
        if "body" in request:
            body = request["body"]
            provenance["body"] = "api_test_case"
        case_codes = _case_success_codes(source_case)
        if case_codes:
            success_codes = case_codes
            success_source = "api_test_case"

    provenance["success_rules"] = success_source
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
        "success_rules": [{"kind": "status_code", "status_codes": success_codes}],
        "provenance": provenance,
        "warnings": list(dict.fromkeys(warnings)),
    }


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


def _schema_placeholder(schema: dict[str, Any], depth: int = 0) -> Any:
    if depth >= 5 or "$ref" in schema:
        return {}
    schema_type = schema.get("type")
    schema_format = schema.get("format")
    if schema_type == "string":
        if schema_format == "uuid":
            return "${uuid}"
        if schema_format == "date":
            return "2026-01-01"
        if schema_format == "date-time":
            return "${timestamp}"
        return "string"
    if schema_type in {"integer", "number"}:
        return 1
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        items = schema.get("items")
        return [_schema_placeholder(items, depth + 1)] if isinstance(items, dict) else []
    if schema_type == "object" or isinstance(schema.get("properties"), dict):
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = set(schema.get("required") or [])
        selected = required or set(properties)
        return {
            name: _schema_placeholder(value, depth + 1)
            for name, value in properties.items()
            if name in selected and isinstance(value, dict)
        }
    return None


def _case_success_codes(source_case) -> list[int]:
    assertions = api_automation_repo.loads_json(source_case["assertions_json"], [])
    codes = {
        int(assertion["expected"])
        for assertion in assertions
        if isinstance(assertion, dict)
        and assertion.get("type") == "status_code"
        and str(assertion.get("expected", "")).isdigit()
    }
    expected = api_automation_repo.loads_json(source_case["expected_json"], {})
    if isinstance(expected, dict) and str(expected.get("status_code", "")).isdigit():
        codes.add(int(expected["status_code"]))
    return sorted(codes)


def _mapping(value: Any) -> dict[str, Any]:
    return {str(key): item for key, item in value.items()} if isinstance(value, dict) else {}


def _test_data_value(value: Any) -> Any:
    return value.get("value") if isinstance(value, dict) and "value" in value else value


def _validate_non_sensitive_headers(headers: dict[str, Any]) -> None:
    sensitive = sorted(key for key in headers if key.strip().lower() in SENSITIVE_HEADER_NAMES)
    if sensitive:
        raise api_error(
            400,
            "PERFORMANCE_SENSITIVE_HEADER_OVERRIDE",
            f"敏感 Header 必须通过接口自动化环境注入：{', '.join(sensitive)}",
        )


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
