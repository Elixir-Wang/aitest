import json
import re

from app.agents.api_automation.pytest_requests.schemas import GeneratedCodeFile, PytestRequestsGenerationInput


def render_pytest_requests_files(input_data: PytestRequestsGenerationInput) -> list[GeneratedCodeFile]:
    endpoint = input_data.endpoint
    endpoint_key = slugify(f"{endpoint.method}_{endpoint.path}_{endpoint.id}")
    endpoint_dir = f"endpoints/{endpoint_key}"
    data_key = f"{endpoint_dir}/cases.json"
    test_key = f"{endpoint_dir}/test_api.py"
    files = [
        GeneratedCodeFile(key="pyproject.toml", kind="config", language="toml", content=_pyproject()),
        GeneratedCodeFile(key="pytest.ini", kind="config", language="ini", content=_pytest_ini()),
        GeneratedCodeFile(key="conftest.py", kind="config", language="python", content=_conftest()),
        GeneratedCodeFile(key="support/__init__.py", kind="support", language="python", content=""),
        GeneratedCodeFile(key="support/client.py", kind="support", language="python", content=_client_py()),
        GeneratedCodeFile(key="support/auth.py", kind="support", language="python", content=_auth_py()),
        GeneratedCodeFile(key="support/assertions.py", kind="support", language="python", content=_assertions_py()),
        GeneratedCodeFile(key="README.md", kind="documentation", language="markdown", content=_readme()),
        GeneratedCodeFile(
            key=data_key,
            kind="data",
            language="json",
            content=json.dumps({"cases": input_data.cases}, ensure_ascii=False, indent=2),
        ),
        GeneratedCodeFile(
            key=test_key,
            kind="test",
            language="python",
            content=_test_py(),
        ),
    ]
    return files


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
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
pythonpath = .
testpaths = endpoints
python_files = test_*.py
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


def _test_py() -> str:
    return '''import json
from pathlib import Path

import pytest

from support.assertions import assert_response_assertions


CASES = json.loads(
    Path(__file__).with_name("cases.json").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case_data", CASES, ids=lambda case: case.get("title", "api-case"))
def test_api_case_execution(api_client, case_data):
    response = api_client.request(case_data["request"], case_data.get("test_data", {}))
    assert_response_assertions(response, case_data["assertions"])
'''


def _readme() -> str:
    return """# Generated API Automation Suite

This suite is generated by the AI Testing System. Runtime environment values are injected by the backend runner.
"""
