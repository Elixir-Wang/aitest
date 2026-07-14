import sys
import shutil
import json
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


def test_generated_scenario_runtime_builds_request_from_endpoint_snapshot(monkeypatch) -> None:
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
            return SimpleNamespace(status_code=200, headers={}, json=lambda: {"ok": True})

    namespace["run_scenario"](
        FakeClient(),
        {
            "variables": {},
            "steps": [
                {
                    "id": "profile",
                    "name": "查询资料",
                    "endpoint": {"method": "GET", "path": "/profile"},
                    "request_overrides": {"request": {"query": {"expand": "roles"}}},
                    "assertions": [{"type": "status_code", "expected": 200}],
                }
            ],
        },
    )

    assert requests == [({"method": "GET", "path": "/profile", "query": {"expand": "roles"}}, {})]


def test_generated_scenario_runtime_executes_assign_condition_wait_and_poll(monkeypatch) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")
    poll_attempts = []

    def assert_response(response, assertions):
        if assertions and assertions[0].get("type") == "poll_ready":
            poll_attempts.append(response.json()["ready"])
            assert response.json()["ready"] is True

    assertions_module.assert_response_assertions = assert_response
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    namespace = {}
    exec(renderer._scenario_py(), namespace)
    sleeps = []
    namespace["time"].sleep = lambda seconds: sleeps.append(seconds)
    requests = []

    class FakeClient:
        def request(self, request_data, test_data):
            requests.append(request_data["path"])
            ready = requests.count("/status") >= 2
            return SimpleNamespace(status_code=200, headers={}, json=lambda: {"ready": ready})

    outputs = namespace["run_scenario"](
        FakeClient(),
        {
            "variables": {},
            "steps": [
                {
                    "id": "assign",
                    "name": "设置租户",
                    "step_type": "assign",
                    "control_config": {"name": "tenant", "source": {"type": "literal", "value": "acme"}},
                },
                {
                    "id": "condition",
                    "name": "租户守卫",
                    "step_type": "condition",
                    "control_config": {
                        "source": {"type": "step_output", "step_id": "assign", "variable": "tenant"},
                        "operator": "equals",
                        "expected": "acme",
                    },
                },
                {"id": "wait", "name": "固定等待", "step_type": "wait", "control_config": {"duration_ms": 20}},
                {
                    "id": "poll",
                    "name": "轮询状态",
                    "step_type": "poll",
                    "endpoint": {"method": "GET", "path": "/status"},
                    "control_config": {"interval_ms": 10, "timeout_ms": 100},
                    "assertions": [{"type": "poll_ready"}],
                },
            ],
        },
    )

    assert outputs["assign"] == {"tenant": "acme"}
    assert poll_attempts == [False, True]
    assert requests == ["/status", "/status"]
    assert sleeps == [0.02, 0.01]


def test_generated_scenario_runtime_runs_cleanup_after_stopped_failure(monkeypatch) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")
    assertions_module.assert_response_assertions = lambda response, assertions: (_ for _ in ()).throw(AssertionError("boom")) if assertions else None
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    namespace = {}
    exec(renderer._scenario_py(), namespace)
    requests = []

    class FakeClient:
        def request(self, request_data, test_data):
            requests.append(request_data["path"])
            return SimpleNamespace(status_code=200, headers={}, json=lambda: {})

    with pytest.raises(AssertionError, match="boom"):
        namespace["run_scenario"](
            FakeClient(),
            {
                "steps": [
                    {
                        "id": "fail",
                        "name": "失败步骤",
                        "endpoint": {"method": "GET", "path": "/fail"},
                        "assertions": [{"type": "forced_failure"}],
                    },
                    {"id": "skip", "name": "跳过步骤", "endpoint": {"method": "GET", "path": "/skip"}},
                    {
                        "id": "cleanup",
                        "name": "清理步骤",
                        "endpoint": {"method": "DELETE", "path": "/cleanup"},
                        "on_failure": "always_run",
                    },
                ]
            },
        )

    assert requests == ["/fail", "/cleanup"]


def test_generated_scenario_runtime_writes_redacted_partial_failure_result(monkeypatch, tmp_path) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")
    assertions_module.assert_response_assertions = lambda response, assertions: (_ for _ in ()).throw(AssertionError("boom")) if assertions else None
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    result_path = tmp_path / "scenario-result.json"
    monkeypatch.setenv("API_SCENARIO_RESULT_PATH", str(result_path))
    namespace = {}
    exec(renderer._scenario_py(), namespace)

    class FakeClient:
        def request(self, request_data, test_data):
            path = request_data["path"]
            return SimpleNamespace(
                status_code=200,
                headers={"Set-Cookie": "session=secret-cookie"},
                content=b'{"token":"secret-token"}',
                json=lambda: {"token": "secret-token", "path": path},
            )

    with pytest.raises(AssertionError, match="boom"):
        namespace["run_scenario"](
            FakeClient(),
            {
                "id": "scenario-1",
                "steps": [
                    {
                        "id": "fail",
                        "name": "失败步骤",
                        "endpoint": {"method": "POST", "path": "/fail"},
                        "request_overrides": {
                            "request": {"headers": {"Authorization": "Bearer secret-auth"}},
                            "test_data": {"password": "secret-password"},
                        },
                        "assertions": [{"type": "forced_failure"}],
                    },
                    {"id": "skip", "name": "跳过步骤", "endpoint": {"method": "GET", "path": "/skip"}},
                    {
                        "id": "cleanup",
                        "name": "清理步骤",
                        "endpoint": {"method": "DELETE", "path": "/cleanup"},
                        "on_failure": "always_run",
                    },
                ],
            },
        )

    result = json.loads(result_path.read_text(encoding="utf-8"))
    serialized = json.dumps(result, ensure_ascii=False)
    assert result["status"] == "failed"
    assert [step["status"] for step in result["steps"]] == ["failed", "skipped", "passed"]
    assert "secret-auth" not in serialized
    assert "secret-password" not in serialized
    assert "secret-cookie" not in serialized
    assert "secret-token" not in serialized


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
