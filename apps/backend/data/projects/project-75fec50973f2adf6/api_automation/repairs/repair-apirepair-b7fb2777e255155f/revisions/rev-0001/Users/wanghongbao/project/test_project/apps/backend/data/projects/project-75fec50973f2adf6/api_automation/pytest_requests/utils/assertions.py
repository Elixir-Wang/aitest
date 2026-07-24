"""
断言工具：封装 pytest 断言，支持 status_code、content_type、jsonpath 等断言类型。
"""
import json
import pytest
from utils.assert_utils import (
    jsonpath_extract,
    jsonpath_exists as _jp_exists,
)


def assert_status_code(response, expected: int):
    """断言 HTTP 状态码"""
    assert response.status_code == expected, (
        f"预期状态码 {expected}，实际 {response.status_code}"
    )


def assert_content_type(response, expected: str):
    """断言 Content-Type"""
    ct = response.headers.get("Content-Type", "")
    assert expected in ct, (
        f"预期 Content-Type 包含 '{expected}'，实际 '{ct}'"
    )


def assert_jsonpath_exists(response, path: str):
    """断言 JSONPath 路径存在"""
    body = _get_json_body(response)
    assert _jp_exists(body, path), (
        f"JSONPath '{path}' 不存在"
    )


def assert_jsonpath_not_exists(response, path: str):
    """断言 JSONPath 路径不存在"""
    body = _get_json_body(response)
    assert not _jp_exists(body, path), (
        f"JSONPath '{path}' 不应存在"
    )


def assert_jsonpath_equals(response, path: str, expected):
    """断言 JSONPath 值等于预期"""
    body = _get_json_body(response)
    actual = jsonpath_extract(body, path)
    assert actual == expected, (
        f"JSONPath '{path}' 预期 {expected!r}，实际 {actual!r}"
    )


def assert_jsonpath_type(response, path: str, expected: str):
    """断言 JSONPath 值的类型"""
    body = _get_json_body(response)
    actual = jsonpath_extract(body, path)
    type_map = {
        "string": str,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": list,
        "null": type(None),
    }
    py_type = type_map.get(expected)
    if py_type is None:
        pytest.fail(f"未知类型: {expected}")
    assert isinstance(actual, py_type), (
        f"JSONPath '{path}' 预期类型 {expected}，实际 {type(actual).__name__}"
    )


def assert_jsonpath_contains(response, path: str, expected):
    """断言 JSONPath 值包含预期"""
    body = _get_json_body(response)
    actual = jsonpath_extract(body, path)
    assert expected in actual, (
        f"JSONPath '{path}' 不包含 {expected!r}，实际 {actual!r}"
    )


def _get_json_body(response):
    """安全获取 JSON 响应体"""
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError) as e:
        pytest.fail(f"响应不是合法 JSON: {e}")


def execute_assertions(response, assertions: list):
    """
    执行断言列表。
    assertions: list[dict]，每个 dict 包含 type, path, expected。
    """
    assertion_map = {
        "status_code": assert_status_code,
        "content_type": assert_content_type,
        "jsonpath_exists": assert_jsonpath_exists,
        "jsonpath_not_exists": assert_jsonpath_not_exists,
        "jsonpath_equals": assert_jsonpath_equals,
        "jsonpath_type": assert_jsonpath_type,
        "jsonpath_contains": assert_jsonpath_contains,
    }
    for assertion in assertions:
        atype = assertion.get("type", "")
        func = assertion_map.get(atype)
        if func is None:
            pytest.fail(f"未知断言类型: {atype}")
        func(response, assertion.get("path", ""), assertion.get("expected"))