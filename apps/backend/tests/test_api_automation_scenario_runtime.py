import sys
import shutil
from types import ModuleType, SimpleNamespace

import pytest

from app.agents.api_automation.pytest_requests import renderer
from app.services.api_automation.runner import collect_script_suite


def test_generated_scenario_runtime_passes_step_output_to_later_request(monkeypatch) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")
    assertions_module.assert_response_assertions = lambda response, assertions: None
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    namespace = {}
    exec(renderer._scenario_py(), namespace)
    requests = []

    class FakeClient:
        def request(self, request_data, test_data):
            requests.append((request_data, test_data))
            if len(requests) == 1:
                return SimpleNamespace(status_code=200, headers={}, json=lambda: {"data": {"id": "user-42"}})
            return SimpleNamespace(status_code=200, headers={}, json=lambda: {"ok": True})

    namespace["run_scenario"](
        FakeClient(),
        {
            "variables": {},
            "steps": [
                {
                    "id": "login",
                    "name": "登录",
                    "case": {"request": {"method": "POST", "path": "/login"}, "test_data": {}, "assertions": []},
                    "extractors": [{"name": "user_id", "source": "response.body", "expression": "$.data.id"}],
                },
                {
                    "id": "profile",
                    "name": "查询资料",
                    "case": {
                        "request": {"method": "GET", "path": "/profile/{user_id}"},
                        "test_data": {"user_id": {"value": "placeholder"}},
                        "assertions": [],
                    },
                    "bindings": [
                        {
                            "target": "/test_data/user_id/value",
                            "source": {"type": "step_output", "step_id": "login", "variable": "user_id"},
                        }
                    ],
                },
            ],
        },
    )

    assert requests[1][1]["user_id"]["value"] == "user-42"


def test_generated_scenario_suite_collects_with_pytest(tmp_path) -> None:
    if not shutil.which("uv"):
        pytest.skip("uv is not installed")
    files = renderer.render_scenario_files(
        "profile_flow_apiscn_1",
        {
            "id": "apiscn-1",
            "name": "资料查询",
            "variables": {},
            "steps": [
                {
                    "id": "apistep-1",
                    "name": "查询资料",
                    "case": {
                        "request": {"method": "GET", "path": "/profile"},
                        "test_data": {},
                        "assertions": [{"type": "status_code", "expected": 200}],
                    },
                }
            ],
        },
    )
    for file_key, content in files.items():
        path = tmp_path / file_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    result = collect_script_suite(
        suite_path=tmp_path,
        timeout=120,
        test_paths=["scenarios/profile_flow_apiscn_1/test_scenario.py"],
    )

    assert result["ok"], result["stderr"] or result["stdout"]
