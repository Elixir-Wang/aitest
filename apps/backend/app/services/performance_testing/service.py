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
from app.core.exceptions import api_error
from app.repositories import api_automation_repo, performance_script_repo, performance_test_repo, project_repo
from app.schemas.performance_test import PerformanceRequestPreviewIn, PerformanceTestCreateIn, PerformanceTestUpdateIn
from app.services import operation_log_service


SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
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
        return _build_request_preview(endpoint, environment)


def create_performance_test(project_id: str, payload: PerformanceTestCreateIn, actor) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        endpoint, _ = _validate_references(
            db,
            project_id,
            endpoint_id=payload.endpoint_id,
            api_environment_id=payload.api_environment_id,
        )
        _validate_non_sensitive_headers(payload.request_config.headers)
        success_rules = [rule.model_dump(mode="json", exclude_none=True) for rule in payload.success_rules]
        if "success_rules" not in payload.model_fields_set:
            success_rules = [{"kind": "status_code", "status_codes": _documented_success_codes(endpoint)}]
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
                api_environment_id=payload.api_environment_id,
                request_config=payload.request_config.model_dump(mode="json"),
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
        after={"name": payload.name, "endpoint_id": payload.endpoint_id},
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
        endpoint_id = raw_fields.get("endpoint_id", current["endpoint_id"])
        api_environment_id = raw_fields.get("api_environment_id", current["api_environment_id"])
        _validate_references(
            db,
            project_id,
            endpoint_id=endpoint_id,
            api_environment_id=api_environment_id,
        )
        if payload.request_config is not None:
            _validate_non_sensitive_headers(payload.request_config.headers)

        fields: dict[str, Any] = {}
        for field in payload.model_fields_set:
            value = getattr(payload, field)
            if field in {"request_config", "load_config", "data_config", "circuit_breaker", "performance_goal"} and value is not None:
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
        performance_script_repo.delete_scripts_by_test(db, test_id)
        performance_test_repo.delete_performance_test(db, test_id)
        _cleanup_test_artifacts(project_id, test_id)
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


def _build_request_preview(endpoint, environment=None) -> dict[str, Any]:
    provenance: dict[str, str] = {}
    warnings: list[str] = []
    path_parameters: dict[str, Any] = {}
    query_parameters: dict[str, Any] = {}
    headers: dict[str, Any] = {}

    # Load environment headers if available
    environment_headers: dict[str, Any] = {}
    if environment:
        environment_headers = api_automation_repo.loads_json(environment.get("default_headers_json") or "{}", {})
        # Mark headers from environment
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
            if name.lower() in SENSITIVE_HEADER_NAMES:
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
    provenance["success_rules"] = "openapi_response"
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


def _cleanup_test_artifacts(project_id: str, test_id: str) -> None:
    from app.services.performance_testing import headless_worker

    perf_root = settings.PROJECT_FILE_STORAGE_ROOT / project_id / "performance_testing"
    with connect() as db:
        run_ids = [
            row["id"]
            for row in db.execute(
                "SELECT id FROM performance_test_runs WHERE project_id = ? AND performance_test_id = ?",
                (project_id, test_id),
            ).fetchall()
        ]
    for run_id in run_ids:
        headless_worker.stop_headless_run(run_id)
        shutil.rmtree(perf_root / "runs" / run_id, ignore_errors=True)
