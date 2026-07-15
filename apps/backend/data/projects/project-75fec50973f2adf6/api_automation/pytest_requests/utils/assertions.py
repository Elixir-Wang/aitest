"""断言工具 - 支持 status_code、jsonpath、jsonpath_type、schema、response_time、body_sha256 等"""
from __future__ import annotations

import hashlib
import json
import re

_JSONPATH_PATTERN = re.compile(r"\$\.[^.]+(?:\.[^.]+)*")


def get_nested(data, path: str):
    for key in path.split("."):
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return None
    return data


def _resolve_jsonpath(response, jsonpath: str):
    body = response.json() if hasattr(response, "json") and callable(response.json) else response.json()
    match = _JSONPATH_PATTERN.fullmatch(jsonpath)
    if not match:
        return None
    cursor = body
    for key in [segment for segment in match.group(0)[2:].split(".") if segment]:
        if isinstance(cursor, dict):
            cursor = cursor.get(key)
        else:
            return None
    return cursor


def _validate_jsonpath_type(value, expected: str) -> bool:
    mapping = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }
    target = mapping.get(expected)
    if target is None:
        return False
    return isinstance(value, target)


def _validate_schema(value, schema: dict) -> bool:
    expected_type = schema.get("type")
    type_map = {"object": dict, "array": list, "string": str, "number": (int, float), "integer": int, "boolean": bool}
    if expected_type and not isinstance(value, type_map.get(expected_type, object)):
        return False
    if expected_type == "object":
        for required in schema.get("required", []):
            if required not in value:
                return False
        for key, sub_schema in (schema.get("properties") or {}).items():
            if key in value and not _validate_schema(value[key], sub_schema):
                return False
    elif expected_type == "array":
        item_schema = schema.get("items")
        if item_schema:
            for item in value:
                if not _validate_schema(item, item_schema):
                    return False
    return True


def assert_response_assertions(response, assertions: list) -> None:
    for assertion in assertions:
        atype = assertion.get("type")
        if atype == "status_code":
            assert response.status_code == assertion["expected"]
        elif atype == "content_type":
            assert assertion["expected"] in response.headers.get("Content-Type", "")
        elif atype == "header_exists":
            assert assertion["path"] in response.headers
        elif atype == "body_not_empty":
            assert bool(response.content)
        elif atype == "body_sha256":
            assert hashlib.sha256(response.content).hexdigest() == assertion["expected"]
        elif atype == "jsonpath":
            value = _resolve_jsonpath(response, assertion["path"])
            assert value == assertion["expected"]
        elif atype == "jsonpath_type":
            value = _resolve_jsonpath(response, assertion["path"])
            assert _validate_jsonpath_type(value, assertion["expected"]) is True
        elif atype == "response_time_max":
            assert response.elapsed.total_seconds() * 1000 <= assertion["expected"]
        elif atype == "schema_basic":
            body = response.json()
            assert _validate_schema(body, assertion["expected"]) is True
        elif atype == "body":
            body = response.json()
            for key, expected in assertion.get("expected", {}).items():
                assert get_nested(body, key) == expected
