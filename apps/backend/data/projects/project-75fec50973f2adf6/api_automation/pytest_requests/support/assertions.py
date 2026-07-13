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
