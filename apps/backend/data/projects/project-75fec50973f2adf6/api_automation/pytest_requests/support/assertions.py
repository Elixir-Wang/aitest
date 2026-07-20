import hashlib


def assert_response_assertions(response, assertions: list[dict]) -> None:
    for idx, assertion in enumerate(assertions):
        assertion_type = assertion.get("type")
        path = assertion.get("path", "")
        expected = assertion.get("expected")
        location = f"[断言{idx + 1}] {assertion_type}" + (f" path={path}" if path else "")

        if assertion_type == "status_code":
            assert response.status_code == expected, (
                f"{location} 失败\n"
                f"  期望状态码: {expected}\n"
                f"  实际状态码: {response.status_code}\n"
                f"  响应体: {response.text[:200]}"
            )
        elif assertion_type == "jsonpath_exists":
            body = response.json()
            actual = _read_path(body, path)
            assert actual is not None, (
                f"{location} 失败\n"
                f"  路径: {path}\n"
                f"  实际值: {actual}\n"
                f"  说明: 期望该路径存在且值不为 None"
            )
        elif assertion_type == "jsonpath_equals":
            body = response.json()
            actual = _read_path(body, path)
            # 确保错误消息在一行内包含关键对比信息
            assert actual == expected, (
                f"路径 {path}: 期望 {expected!r}, 实际 {actual!r}"
            )
        elif assertion_type == "jsonpath_type":
            body = response.json()
            actual = _read_path(body, path)
            expected_type = assertion.get("expected")
            assert _json_type(actual) == expected_type, (
                f"{location} 失败\n"
                f"  路径: {path}\n"
                f"  期望类型: {expected_type}\n"
                f"  实际类型: {_json_type(actual)}\n"
                f"  实际值: {actual!r}"
            )
        elif assertion_type == "response_time_max":
            elapsed_ms = response.elapsed.total_seconds() * 1000
            threshold = float(assertion.get("expected", 0))
            assert elapsed_ms <= threshold, (
                f"{location} 失败\n"
                f"  期望响应时间: ≤{threshold}ms\n"
                f"  实际响应时间: {elapsed_ms:.2f}ms"
            )
        elif assertion_type == "schema_basic":
            _assert_basic_schema(response.json(), assertion.get("expected") or assertion.get("schema") or {})
        elif assertion_type == "content_type":
            expected_ct = str(assertion.get("expected") or "").lower()
            actual_ct = response.headers.get("Content-Type", "").lower()
            assert expected_ct in actual_ct, (
                f"{location} 失败\n"
                f"  期望 Content-Type: {expected_ct}\n"
                f"  实际 Content-Type: {actual_ct}"
            )
        elif assertion_type == "header_exists":
            header_name = assertion.get("path", "")
            assert header_name in response.headers, (
                f"{location} 失败\n"
                f"  期望响应头存在: {header_name}\n"
                f"  实际响应头: {list(response.headers.keys())}"
            )
        elif assertion_type == "header_equals":
            header_name = assertion.get("path", "")
            expected_h = assertion.get("expected")
            actual_h = response.headers.get(header_name)
            assert actual_h == expected_h, (
                f"{location} 失败\n"
                f"  响应头: {header_name}\n"
                f"  期望值: {expected_h!r}\n"
                f"  实际值: {actual_h!r}"
            )
        elif assertion_type == "body_not_empty":
            expected_bool = bool(assertion.get("expected", True))
            assert bool(response.content) is expected_bool, (
                f"{location} 失败\n"
                f"  期望响应体为空: {not expected_bool}\n"
                f"  实际响应体长度: {len(response.content)}"
            )
        elif assertion_type == "body_sha256":
            actual_hash = hashlib.sha256(response.content).hexdigest()
            expected_hash = assertion.get("expected")
            assert actual_hash == expected_hash, (
                f"{location} 失败\n"
                f"  期望 SHA256: {expected_hash}\n"
                f"  实际 SHA256: {actual_hash}"
            )
        else:
            raise AssertionError(f"Unsupported assertion type: {assertion_type}")


assert_json_assertions = assert_response_assertions


def _json_type(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _assert_basic_schema(value, schema: dict, path: str = "$") -> None:
    expected_type = schema.get("type")
    if expected_type:
        assert _json_type(value) == expected_type, f"{path} expected {expected_type}, got {_json_type(value)}"
    if isinstance(value, dict):
        for name in schema.get("required", []):
            assert name in value, f"{path} missing required property: {name}"
        for name, child_schema in schema.get("properties", {}).items():
            if name in value:
                _assert_basic_schema(value[name], child_schema, f"{path}.{name}")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            _assert_basic_schema(item, schema["items"], f"{path}[{index}]")


def _read_path(data, path: str):
    if not path or path == "$":
        return data
    current = data
    for part in path.removeprefix("$.").split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current
