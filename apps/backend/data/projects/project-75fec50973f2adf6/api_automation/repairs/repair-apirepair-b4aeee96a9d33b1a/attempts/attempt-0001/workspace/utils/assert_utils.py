"""断言辅助函数"""
from __future__ import annotations

from utils.assertions import assert_response_assertions


def assert_response(response, assertions: dict | list | None = None) -> None:
    """兼容旧版 dict 格式的断言入口。

    Args:
        response: requests.Response 对象
        assertions: 断言配置，可以是 dict 或 list[dict]
    """
    if not assertions:
        return
    if isinstance(assertions, dict):
        # 兼容旧格式：{"status_code": 200, "jsonpath": {...}}
        items = []
        for key, value in assertions.items():
            if key == "status_code":
                items.append({"type": "status_code", "expected": value})
            elif key == "jsonpath":
                for path, expected in value.items():
                    items.append({"type": "jsonpath", "path": path, "expected": expected})
            elif key == "jsonpath_type":
                for path, expected in value.items():
                    items.append({"type": "jsonpath_type", "path": path, "expected": expected})
            elif key == "schema":
                items.append({"type": "schema_basic", "expected": value})
            elif key == "response_time_max":
                items.append({"type": "response_time_max", "expected": value})
            elif key == "content_type":
                items.append({"type": "content_type", "expected": value})
            elif key == "body_not_empty":
                items.append({"type": "body_not_empty", "expected": value})
            elif key == "body_sha256":
                items.append({"type": "body_sha256", "expected": value})
            elif key == "header_exists":
                items.append({"type": "header_exists", "path": value})
            elif key == "body":
                items.append({"type": "body", "expected": value})
        assertions = items
    assert_response_assertions(response, assertions)
