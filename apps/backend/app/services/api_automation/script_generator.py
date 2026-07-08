import json
import re
from pathlib import Path
from typing import Any


def generate_pytest_suite(*, project_id: str, suite_id: str, cases: list[dict[str, Any]], output_root: Path) -> dict:
    suite_path = output_root / project_id / "api_automation" / "generated" / suite_id
    tests_dir = suite_path / "tests"
    data_dir = suite_path / "data"
    support_dir = suite_path / "support"
    tests_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    support_dir.mkdir(parents=True, exist_ok=True)

    slug = _slug(cases[0]["title"] if cases else suite_id)
    test_file = tests_dir / f"test_api_{slug}.py"
    data_file = data_dir / f"test_api_{slug}.json"

    (suite_path / "pyproject.toml").write_text(_pyproject(), encoding="utf-8")
    (suite_path / "pytest.ini").write_text(_pytest_ini(), encoding="utf-8")
    (suite_path / "conftest.py").write_text(_conftest(), encoding="utf-8")
    (support_dir / "__init__.py").write_text("", encoding="utf-8")
    (support_dir / "client.py").write_text(_client_py(), encoding="utf-8")
    (support_dir / "auth.py").write_text(_auth_py(), encoding="utf-8")
    (support_dir / "assertions.py").write_text(_assertions_py(), encoding="utf-8")
    (suite_path / "README.md").write_text(_readme(), encoding="utf-8")
    data_file.write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    test_file.write_text(_test_py(data_file.name), encoding="utf-8")

    return {
        "suite_path": suite_path,
        "test_file_path": test_file,
        "data_file_path": data_file,
        "script_name": f"test_api_{slug}",
    }


def _slug(value: str) -> str:
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
    return '''import json
from pathlib import Path

import pytest

from support.client import ApiClient


@pytest.fixture(scope="session")
def api_client():
    return ApiClient.from_environment()


@pytest.fixture(scope="session")
def case_dataset():
    data_files = sorted((Path(__file__).parent / "data").glob("test_api_*.json"))
    cases = []
    for data_file in data_files:
        cases.extend(json.loads(data_file.read_text(encoding="utf-8")).get("cases", []))
    return cases
'''


def _client_py() -> str:
    return '''import os

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

    def request(self, request_data: dict):
        method = request_data.get("method", "GET")
        path = request_data.get("path", "")
        url = f"{self.base_url}{path}"
        return self.session.request(
            method,
            url,
            params=request_data.get("query") or None,
            json=request_data.get("body") if "body" in request_data else None,
            headers=request_data.get("headers") or None,
            timeout=self.timeout,
        )
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
    return '''def assert_json_assertions(response, assertions: list[dict]) -> None:
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
    return '''from support.assertions import assert_json_assertions


def test_api_case_execution(api_client, case_dataset):
    for case_data in case_dataset:
        response = api_client.request(case_data["request"])
        assert_json_assertions(response, case_data["assertions"])
'''


def _readme() -> str:
    return """# Generated API Automation Suite

This suite is generated by the AI Testing System. Runtime environment values are injected by the backend runner.
"""
