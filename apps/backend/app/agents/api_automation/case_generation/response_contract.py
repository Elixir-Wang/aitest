import re
from typing import Any, Iterable

from app.agents.api_automation.case_generation.schemas import ApiAssertion


class ResponseContractError(ValueError):
    pass


_DYNAMIC_FIELD_TOKENS = (
    "time",
    "date",
    "timestamp",
    "uuid",
    "id",
    "token",
    "cookie",
    "captcha",
    "url",
    "count",
    "cnt",
    "rate",
    "ratio",
)


def compile_response_contract(
    endpoint: dict[str, Any],
    *,
    expected_status_code: int | None = None,
) -> list[ApiAssertion]:
    status_code, response = _select_response(endpoint.get("responses") or {}, expected_status_code)
    assertions = [ApiAssertion(type="status_code", expected=status_code)]
    if response is None:
        return assertions

    media_type, media = _select_media(response.get("content") or {})
    if not media_type:
        return assertions

    assertions.append(ApiAssertion(type="content_type", expected=media_type))
    schema = media.get("schema") if isinstance(media, dict) else None
    if not isinstance(schema, dict):
        return assertions
    _reject_unresolved_ref(schema)

    if _is_json_media_type(media_type):
        assertions.extend(_compile_json_schema(schema))
    elif _is_binary_schema(media_type, schema):
        assertions.append(ApiAssertion(type="body_not_empty", expected=True))

    return _deduplicate(assertions)


def merge_response_assertions(
    required: Iterable[ApiAssertion | dict[str, Any]],
    generated: Iterable[ApiAssertion | dict[str, Any]],
) -> list[ApiAssertion]:
    required_assertions = [_as_assertion(assertion) for assertion in required]
    generated_assertions = [_as_assertion(assertion) for assertion in generated]
    merged = list(required_assertions)
    by_key = {_assertion_key(assertion): assertion for assertion in required_assertions}

    for assertion in generated_assertions:
        key = _assertion_key(assertion)
        existing = by_key.get(key)
        if existing is not None:
            if existing.expected != assertion.expected:
                if assertion.type == "status_code":
                    raise ResponseContractError("状态码断言与响应契约冲突。")
                raise ResponseContractError(
                    f"断言与响应契约冲突：{assertion.type} {assertion.path or '<root>'}。"
                )
            continue
        merged.append(assertion)
        by_key[key] = assertion

    return merged


def _select_response(
    responses: dict[str, Any],
    expected_status_code: int | None,
) -> tuple[int, dict[str, Any] | None]:
    if expected_status_code is not None:
        exact = responses.get(str(expected_status_code))
        if isinstance(exact, dict):
            return expected_status_code, exact
        range_response = responses.get(f"{expected_status_code // 100}XX")
        if not isinstance(range_response, dict):
            range_response = responses.get(f"{expected_status_code // 100}xx")
        if isinstance(range_response, dict):
            return expected_status_code, range_response
        default = responses.get("default")
        return expected_status_code, default if isinstance(default, dict) else None

    success_codes = sorted(
        int(status)
        for status in responses
        if str(status).isdigit() and 200 <= int(status) <= 299
    )
    if success_codes:
        status_code = success_codes[0]
        return status_code, responses[str(status_code)]
    for key in ("2XX", "2xx"):
        if isinstance(responses.get(key), dict):
            return 200, responses[key]
    raise ResponseContractError("接口未声明可用于新成功用例的响应契约。")


def _select_media(content: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for media_type in content:
        if media_type.lower() == "application/json":
            return media_type, content[media_type]
    for media_type in content:
        if media_type.lower().endswith("+json"):
            return media_type, content[media_type]
    if content:
        media_type = sorted(content)[0]
        return media_type, content[media_type]
    return "", {}


def _compile_json_schema(schema: dict[str, Any]) -> list[ApiAssertion]:
    normalized = _normalize_schema(schema)
    assertions: list[ApiAssertion] = []
    _append_property_assertions(normalized, "$", assertions)
    return assertions


def _append_property_assertions(
    schema: dict[str, Any],
    parent_path: str,
    assertions: list[ApiAssertion],
) -> None:
    properties = schema.get("properties") or {}
    if not isinstance(properties, dict):
        return
    for name, child_schema in properties.items():
        if not isinstance(child_schema, dict):
            continue
        _reject_unresolved_ref(child_schema)
        path = f"{parent_path}.{name}"
        fixed_value = _fixed_value(str(name), child_schema)
        if fixed_value is _MISSING:
            assertions.append(ApiAssertion(type="jsonpath_exists", path=path, expected=True))
        else:
            assertions.append(ApiAssertion(type="jsonpath_equals", path=path, expected=fixed_value))
        normalized_child = _normalize_schema(child_schema)
        if normalized_child.get("type") == "object" or normalized_child.get("properties"):
            _append_property_assertions(normalized_child, path, assertions)
        if normalized_child.get("type") == "array" and int(normalized_child.get("minItems") or 0) >= 1:
            assertions.append(ApiAssertion(type="body_not_empty", path=path, expected=True))


def _normalize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    _reject_unresolved_ref(schema)
    if "allOf" in schema:
        merged = {key: value for key, value in schema.items() if key != "allOf"}
        properties: dict[str, Any] = dict(merged.get("properties") or {})
        for branch in schema.get("allOf") or []:
            if not isinstance(branch, dict):
                continue
            normalized_branch = _normalize_schema(branch)
            properties.update(normalized_branch.get("properties") or {})
        if properties:
            merged["properties"] = properties
            merged.setdefault("type", "object")
        return merged
    for keyword in ("oneOf", "anyOf"):
        branches = schema.get(keyword)
        if isinstance(branches, list) and branches:
            normalized_branches = [_normalize_schema(branch) for branch in branches if isinstance(branch, dict)]
            if not normalized_branches:
                return schema
            common_names = set((normalized_branches[0].get("properties") or {}).keys())
            for branch in normalized_branches[1:]:
                common_names &= set((branch.get("properties") or {}).keys())
            common_properties = {
                name: normalized_branches[0]["properties"][name]
                for name in common_names
                if all(
                    (branch.get("properties") or {}).get(name) == normalized_branches[0]["properties"][name]
                    for branch in normalized_branches[1:]
                )
            }
            return {"type": "object", "properties": common_properties}
    return schema


class _Missing:
    pass


_MISSING = _Missing()


def _fixed_value(name: str, schema: dict[str, Any]) -> Any:
    if any(token in name.lower() for token in _DYNAMIC_FIELD_TOKENS):
        return _MISSING
    if "const" in schema:
        return schema["const"]
    enum = schema.get("enum")
    if isinstance(enum, list) and len(enum) == 1:
        return enum[0]
    example = schema.get("example")
    description = str(schema.get("description") or "")
    if example is None or not description:
        return _MISSING
    if not any(marker in description for marker in ("成功", "正常")):
        return _MISSING
    quoted_values = re.findall(r'["“”]([^"“”]+)["“”]', description)
    if str(example) in quoted_values:
        return example
    return _MISSING


def _reject_unresolved_ref(schema: dict[str, Any]) -> None:
    if "$ref" in schema:
        raise ResponseContractError(f"无法解析响应 Schema 引用：{schema['$ref']}")


def _is_json_media_type(media_type: str) -> bool:
    normalized = media_type.lower().split(";", 1)[0].strip()
    return normalized == "application/json" or normalized.endswith("+json")


def _is_binary_schema(media_type: str, schema: dict[str, Any]) -> bool:
    return media_type.lower().split(";", 1)[0].strip() == "application/octet-stream" or (
        schema.get("type") == "string" and schema.get("format") == "binary"
    )


def _as_assertion(assertion: ApiAssertion | dict[str, Any]) -> ApiAssertion:
    if isinstance(assertion, ApiAssertion):
        return assertion
    return ApiAssertion.model_validate(assertion)


def _assertion_key(assertion: ApiAssertion) -> tuple[str, str]:
    return assertion.type, assertion.path.strip()


def _deduplicate(assertions: Iterable[ApiAssertion]) -> list[ApiAssertion]:
    result: list[ApiAssertion] = []
    seen: set[tuple[str, str, str]] = set()
    for assertion in assertions:
        key = (assertion.type, assertion.path.strip(), repr(assertion.expected))
        if key in seen:
            continue
        seen.add(key)
        result.append(assertion)
    return result
