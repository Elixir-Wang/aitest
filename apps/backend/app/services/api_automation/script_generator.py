import json
import re
from pathlib import Path
from typing import Any

from app.services.api_automation.script_workspace import write_atomic


def generate_pytest_suite(*, project_id: str, suite_id: str, cases: list[dict[str, Any]], output_root: Path) -> dict:
    """Create or update the single pytest + Requests suite owned by a project."""
    suite_path = output_root / project_id / "api_automation" / "pytest_requests"
    tests_dir = suite_path / "tests"
    data_dir = suite_path / "data"
    support_dir = suite_path / "support"
    tests_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    support_dir.mkdir(parents=True, exist_ok=True)

    write_atomic(suite_path / "pyproject.toml", _pyproject())
    write_atomic(suite_path / "pytest.ini", _pytest_ini())
    write_atomic(suite_path / "conftest.py", _conftest())
    write_atomic(support_dir / "__init__.py", "")
    write_atomic(support_dir / "client.py", _client_py())
    write_atomic(support_dir / "auth.py", _auth_py())
    write_atomic(support_dir / "assertions.py", _assertions_py())
    write_atomic(suite_path / "README.md", _readme())

    cases_by_endpoint: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        endpoint_id = str(case.get("endpoint_id") or "unassigned")
        cases_by_endpoint.setdefault(endpoint_id, []).append(case)

    artifacts = []
    for endpoint_id, endpoint_cases in cases_by_endpoint.items():
        request = endpoint_cases[0].get("request") or {}
        endpoint_slug = slugify(f'{request.get("method", "api")}_{request.get("path", endpoint_id)}_{endpoint_id}')
        test_file = tests_dir / f"test_{endpoint_slug}.py"
        data_file = data_dir / f"test_{endpoint_slug}.json"
        write_atomic(data_file, json.dumps({"cases": endpoint_cases}, ensure_ascii=False, indent=2))
        write_atomic(test_file, _test_py(data_file.name))
        artifacts.append(
            {
                "endpoint_id": None if endpoint_id == "unassigned" else endpoint_id,
                "test_file_path": test_file,
                "data_file_path": data_file,
                "script_name": f"test_{endpoint_slug}",
            }
        )

    first = artifacts[0] if artifacts else {
        "test_file_path": tests_dir / "test_generated.py",
        "data_file_path": data_dir / "test_generated.json",
        "script_name": "test_generated",
    }

    return {
        "suite_path": suite_path,
        **first,
        "artifacts": artifacts,
    }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    return slug or "generated"


def _pyproject() -> str:
    return """[project]
name = "generated-api-automation-suite"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pytest", "requests", "pytest-json-report"]
"""


def _pytest_ini() -> str:
    return """[pytest]
addopts = --import-mode=importlib
testpaths = tests
"""


def _conftest() -> str:
    return '''import pytest

from support.client import ApiClient


@pytest.fixture(scope="session")
def api_client():
    return ApiClient.from_environment()


'''


def _client_py() -> str:
    return '''import os
import re
from pathlib import Path
from urllib.parse import quote

import requests

from support.auth import build_auth_headers


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(build_auth_headers())

    @classmethod
    def from_environment(cls):
        base_url = os.environ.get("API_BASE_URL", "")
        if not base_url:
            raise RuntimeError("API_BASE_URL is required.")
        timeout = int(os.environ.get("API_TIMEOUT_SECONDS", "30"))
        return cls(base_url=base_url, timeout=timeout)

    def request(self, request_data: dict, test_data: dict | None = None):
        method = request_data.get("method", "GET")
        path = _expand_path(request_data.get("path", ""), test_data or {})
        url = f"{self.base_url}{path}"
        query = _expand_environment(request_data.get("query") or {})
        headers = _expand_environment(request_data.get("headers") or {})
        body = _expand_environment(request_data.get("body")) if "body" in request_data else None
        files, handles = _build_files(request_data.get("files") or {})
        try:
            return self.session.request(
                method,
                url,
                params=query or None,
                data=body if files else None,
                json=None if files else body,
                files=files or None,
                headers=headers or None,
                timeout=self.timeout,
            )
        finally:
            for handle in handles:
                handle.close()


_ENV_PATTERN = re.compile(r"\\$\\{([A-Za-z_][A-Za-z0-9_]*)\\}")
_PATH_PATTERN = re.compile(r"\\{([A-Za-z_][A-Za-z0-9_]*)\\}")


def _expand_path(path: str, test_data: dict) -> str:
    values = {
        key: value.get("value") if isinstance(value, dict) and "value" in value else value
        for key, value in test_data.items()
    }
    expanded = _expand_environment(path)
    return _PATH_PATTERN.sub(
        lambda match: quote(str(_expand_environment(values.get(match.group(1), match.group(0)))), safe=""),
        expanded,
    )


def _expand_environment(value):
    if isinstance(value, dict):
        return {key: _expand_environment(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment(item) for item in value]
    if not isinstance(value, str):
        return value
    full_match = _ENV_PATTERN.fullmatch(value)
    if full_match:
        return os.environ.get(full_match.group(1), "")
    return _ENV_PATTERN.sub(lambda match: os.environ.get(match.group(1), ""), value)


def _build_files(file_specs: dict):
    files = []
    handles = []
    try:
        for field_name, raw_specs in file_specs.items():
            specs = raw_specs if isinstance(raw_specs, list) else [raw_specs]
            for raw_spec in specs:
                spec = raw_spec if isinstance(raw_spec, dict) else {"path": raw_spec}
                file_path = Path(_expand_environment(spec.get("path", ""))).expanduser()
                if not str(file_path) or not file_path.is_file():
                    raise RuntimeError(f"Upload file does not exist for field {field_name}: {file_path}")
                handle = file_path.open("rb")
                handles.append(handle)
                filename = _expand_environment(spec.get("filename")) or file_path.name
                content_type = _expand_environment(spec.get("content_type")) or "application/octet-stream"
                files.append((field_name, (filename, handle, content_type)))
        return files, handles
    except Exception:
        for handle in handles:
            handle.close()
        raise
'''


def _auth_py() -> str:
    return '''import os


def build_auth_headers() -> dict:
    headers = {}
    bearer = os.environ.get("API_AUTH_BEARER", "")
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    for key, value in os.environ.items():
        if key.startswith("API_HEADER_") and value:
            header_name = key.removeprefix("API_HEADER_").replace("_", "-")
            headers[header_name] = value
    return headers
'''


def _assertions_py() -> str:
    return '''import hashlib


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
'''


def _test_py(data_filename: str) -> str:
    return f'''import json
from pathlib import Path

import pytest

from support.assertions import assert_response_assertions


CASES = json.loads(
    (Path(__file__).parents[1] / "data" / "{data_filename}").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case_data", CASES, ids=lambda case: case.get("title", "api-case"))
def test_api_case_execution(api_client, case_data):
    response = api_client.request(case_data["request"], case_data.get("test_data", {{}}))
    assert_response_assertions(response, case_data["assertions"])
'''


def _readme() -> str:
    return """# Generated API Automation Suite

This suite is generated by the AI Testing System. Runtime environment values are injected by the backend runner.
"""
