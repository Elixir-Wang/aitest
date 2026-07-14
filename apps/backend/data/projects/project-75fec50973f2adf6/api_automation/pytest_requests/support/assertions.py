import hashlib


def assert_response_assertions(response, assertions: list[dict]) -> None:
    for assertion in assertions:
        assertion_type = assertion.get("type")
        if assertion_type == "status_code":
            assert response.status_code == assertion.get("expected")
        elif assertion_type == "jsonpath_exists":
            body = response.json()
            assert _read_path(body, assertion.get("path", "")) is not None
        elif assertion_type == "jsonpath_equals":
            body = response.json()
            assert _read_path(body, assertion.get("path", "")) == assertion.get("expected")
        elif assertion_type == "jsonpath_type":
            body = response.json()
            actual = _read_path(body, assertion.get("path", ""))
            assert _json_type(actual) == assertion.get("expected")
        elif assertion_type == "response_time_max":
            elapsed_ms = response.elapsed.total_seconds() * 1000
            assert elapsed_ms <= float(assertion.get("expected", 0))
        elif assertion_type == "schema_basic":
            _assert_basic_schema(response.json(), assertion.get("expected") or assertion.get("schema") or {})
        elif assertion_type == "content_type":
            expected = str(assertion.get("expected") or "").lower()
            actual = response.headers.get("Content-Type", "").lower()
            assert expected in actual
        elif assertion_type == "header_exists":
            assert assertion.get("path", "") in response.headers
        elif assertion_type == "header_equals":
            assert response.headers.get(assertion.get("path", "")) == assertion.get("expected")
        elif assertion_type == "body_not_empty":
            assert bool(response.content) is bool(assertion.get("expected", True))
        elif assertion_type == "body_sha256":
            actual = hashlib.sha256(response.content).hexdigest()
            assert actual == assertion.get("expected")
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
