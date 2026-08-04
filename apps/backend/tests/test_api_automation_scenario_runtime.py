import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from app.agents.api_automation.pytest_requests import renderer
from app.services.api_automation.runner import collect_script_suite, run_script_suite


def test_generated_scenario_runtime_extracts_sse_event_json_by_event_and_path() -> None:
    namespace = {}
    exec(renderer._scenario_py(), namespace)

    class FakeSseResponse:
        status_code = 200
        headers = {"content-type": "text/event-stream"}

        def iter_lines(self, decode_unicode=False):
            yield b"event: message"
            yield b'data: {"data":{"dialog_id":"dialog-1"}}'
            yield b""
            yield b"event: done"
            yield b'data: {"finish_reason":"stop"}'

    assert namespace["_extract"](
        FakeSseResponse(),
        [
            {
                "name": "dialog_id",
                "source": "sse_event_json",
                "event": "message",
                "path": "/data/dialog_id",
            }
        ],
    ) == {"dialog_id": "dialog-1"}


def test_generated_scenario_runtime_extracts_all_matching_sse_event_values() -> None:
    namespace = {}
    exec(renderer._scenario_py(), namespace)

    class FakeSseResponse:
        status_code = 200
        headers = {"content-type": "text/event-stream"}

        def iter_lines(self, decode_unicode=False):
            yield b"event: token"
            yield b'data: {"text":"hello"}'
            yield b""
            yield b"event: token"
            yield b'data: {"text":" world"}'

    assert namespace["_extract"](
        FakeSseResponse(),
        [
            {
                "name": "tokens",
                "source": "sse_event_json",
                "event": "token",
                "path": "/text",
                "occurrence": "all",
            }
        ],
    ) == {"tokens": ["hello", " world"]}


def test_generated_scenario_runtime_reads_json_pointer_assertion_path(monkeypatch) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")

    def assert_response(response, assertions):
        assertion = assertions[0]
        path = assertion["path"]
        actual = response.json().get(path.removeprefix("$."))
        assert actual == assertion["expected"], (
            f"路径 {path}: 期望 {assertion['expected']!r}, 实际 {actual!r}"
        )

    assertions_module.assert_response_assertions = assert_response
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    namespace = {}
    exec(renderer._scenario_py(), namespace)

    class FakeClient:
        def request(self, request_data, test_data):
            return SimpleNamespace(
                status_code=200,
                headers={},
                json=lambda: {"code": "400000", "message": "invalid parameter: MessageSource"},
            )

    with pytest.raises(
        AssertionError,
        match=r"路径 /code: 期望 '000000', 实际 '400000'",
    ):
        namespace["run_scenario"](
            FakeClient(),
            {
                "steps": [
                    {
                        "id": "segment-code",
                        "endpoint": {"method": "POST", "path": "/segment-code"},
                        "assertions": [
                            {"type": "jsonpath_equals", "path": "/code", "expected": "000000"}
                        ],
                    }
                ]
            },
        )


def test_generated_scenario_runtime_rejects_missing_required_sse_event_values() -> None:
    namespace = {}
    exec(renderer._scenario_py(), namespace)

    class FakeSseResponse:
        status_code = 200
        headers = {"content-type": "text/event-stream"}

        def iter_lines(self, decode_unicode=False):
            yield b"event: done"
            yield b'data: {"finish_reason":"stop"}'

    with pytest.raises(AssertionError, match="未提取到必填变量: tokens"):
        namespace["_extract"](
            FakeSseResponse(),
            [
                {
                    "name": "tokens",
                    "source": "sse_event_json",
                    "event": "token",
                    "path": "/text",
                    "occurrence": "all",
                }
            ],
        )


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


def test_generated_scenario_runtime_normalizes_json_request_body(monkeypatch) -> None:
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
                    "id": "segment-code",
                    "name": "生成 SegmentCode",
                    "endpoint": {"method": "POST", "path": "/segment-code/gen"},
                    "request_overrides": {"request": {"json": {"message_source": "web_share"}}},
                    "assertions": [{"type": "status_code", "expected": 200}],
                }
            ],
        },
    )

    assert requests == [
        (
            {
                "method": "POST",
                "path": "/segment-code/gen",
                "body": {"message_source": "web_share"},
            },
            {},
        )
    ]


def test_generated_scenario_runtime_captures_sse_events_once(monkeypatch) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")
    assertions_module.assert_response_assertions = lambda response, assertions: None
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    namespace = {}
    exec(renderer._scenario_py(), namespace)
    reads = 0

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "text/event-stream"}

        def iter_lines(self, decode_unicode=True):
            nonlocal reads
            reads += 1
            lines = [
                b"event: message",
                'data: {"code":"000000","data":{"answer":"你好"}}'.encode(),
                b"",
                b"event: done",
                b"data: [DONE]",
                b"",
            ]
            if decode_unicode:
                return iter(line.decode("latin-1") for line in lines)
            return iter(lines)

    response = FakeResponse()
    endpoint = {
        "responses": {"200": {"content": {"text/event-stream": {"schema": {"type": "string"}}}}}
    }

    snapshot = namespace["_response_snapshot"](response, endpoint)
    extracted = namespace["_extract"](
        response,
        [{"name": "code", "source": "sse_event_json", "event": "message", "path": "/code"}],
    )

    assert reads == 1
    assert snapshot["body"] == {
        "streaming": True,
        "captured": True,
        "event_count": 2,
        "truncated": False,
        "events": [
            {
                "event": "message",
                "data": {"code": "000000", "data": {"answer": "你好"}},
                "received_offset_ms": 0,
            },
            {"event": "done", "data": "[DONE]", "received_offset_ms": 0},
        ],
    }
    assert extracted == {"code": "000000"}


def test_generated_scenario_runtime_applies_fixed_endpoint_parameters(monkeypatch) -> None:
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
            requests.append(request_data)
            return SimpleNamespace(status_code=200, headers={}, json=lambda: {"ok": True})

    namespace["run_scenario"](
        FakeClient(),
        {
            "variables": {},
            "steps": [
                {
                    "id": "chat",
                    "endpoint": {
                        "method": "POST",
                        "path": "/sse",
                        "parameters": [
                            {
                                "name": "SSE-Backend-Type",
                                "in": "header",
                                "required": True,
                                "schema": {"type": "string", "enum": ["sse"]},
                            },
                            {
                                "name": "cybertron-app-id",
                                "in": "header",
                                "required": True,
                                "schema": {"type": "string", "default": "multi-agent-server"},
                            },
                        ],
                    },
                    "assertions": [{"type": "status_code", "expected": 200}],
                }
            ],
        },
    )

    assert requests[0]["headers"] == {
        "SSE-Backend-Type": "sse",
        "cybertron-app-id": "multi-agent-server",
    }


def test_generated_scenario_runtime_builds_dynamic_multipart_json(monkeypatch) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")
    assertions_module.assert_response_assertions = lambda response, assertions: None
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    monkeypatch.setenv("API_SCENARIO_INPUT_QUESTION", "很有问题")
    monkeypatch.setenv("API_SCENARIO_INPUT_USERNAME", "chen.li2")
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
                    "id": "chat",
                    "name": "SSE 对话",
                    "endpoint": {"method": "POST", "path": "/sse"},
                    "bindings": [
                        {
                            "target": "/request/multipart_form/username",
                            "source": {"type": "user_input", "name": "username"},
                            "required": True,
                        },
                        {
                            "target": "/request/multipart_form/data",
                            "source": {
                                "type": "object",
                                "properties": {
                                    "agent_node_id": {"type": "literal", "value": ""},
                                    "question": {"type": "user_input", "name": "question"},
                                    "stream": {"type": "literal", "value": True},
                                },
                            },
                            "required": True,
                            "transform": "json_encode",
                        },
                    ],
                    "assertions": [{"type": "status_code", "expected": 200}],
                }
            ],
        },
    )

    request = requests[0][0]
    assert request["multipart_form"]["username"] == "chen.li2"
    assert json.loads(request["multipart_form"]["data"]) == {
        "agent_node_id": "",
        "question": "很有问题",
        "stream": True,
    }


def test_generated_scenario_runtime_applies_pre_and_post_variable_actions(monkeypatch) -> None:
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
            requests.append(request_data)
            return SimpleNamespace(status_code=200, headers={}, json=lambda: {"ok": True})

    outputs = namespace["run_scenario"](
        FakeClient(),
        {
            "variables": {},
            "steps": [
                {
                    "id": "create",
                    "name": "创建订单",
                    "endpoint": {"method": "POST", "path": "/orders"},
                    "control_config": {
                        "pre_request": {
                            "actions": [
                                {"type": "set_variable", "name": "tenant", "source": {"type": "literal", "value": "acme"}}
                            ]
                        },
                        "post_response": {
                            "actions": [
                                {"type": "set_variable", "name": "completed", "source": {"type": "literal", "value": True}}
                            ]
                        },
                    },
                    "bindings": [
                        {
                            "target": "/request/headers/X-Tenant",
                            "source": {"type": "scenario", "name": "tenant"},
                        }
                    ],
                }
            ],
        },
    )

    assert requests[0]["headers"]["X-Tenant"] == "acme"
    assert outputs["create"]["completed"] is True


def test_generated_scenario_runtime_retries_request_failures(monkeypatch) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")
    assertions_module.assert_response_assertions = lambda response, assertions: None
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    namespace = {}
    exec(renderer._scenario_py(), namespace)
    attempts = []

    class FakeClient:
        def request(self, request_data, test_data):
            attempts.append(request_data)
            if len(attempts) == 1:
                raise RuntimeError("temporary failure")
            return SimpleNamespace(status_code=200, headers={}, json=lambda: {"ok": True})

    namespace["run_scenario"](
        FakeClient(),
        {
            "variables": {},
            "steps": [
                {
                    "id": "retry",
                    "name": "重试请求",
                    "endpoint": {"method": "GET", "path": "/retry"},
                    "control_config": {"retries": 1, "retry_interval_ms": 0},
                }
            ],
        },
    )

    assert len(attempts) == 2


def test_generated_scenario_runtime_dispatches_multipart_as_requests_parts(monkeypatch) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")
    assertions_module.assert_response_assertions = lambda response, assertions: None
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    namespace = {}
    exec(renderer._scenario_py(), namespace)
    calls = []

    class FakeSession:
        def request(self, *args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(status_code=200, headers={}, json=lambda: {"ok": True}, close=lambda: None)

    class FakeClient:
        base_url = "https://example.test"
        timeout = 30
        session = FakeSession()

        def request(self, request_data, test_data):
            raise AssertionError("multipart 请求不应进入旧客户端路径")

    namespace["run_scenario"](
        FakeClient(),
        {
            "variables": {},
            "steps": [
                {
                    "id": "chat",
                    "name": "SSE 对话",
                    "endpoint": {
                        "method": "POST",
                        "path": "/sse",
                        "responses": {"200": {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
                    },
                    "bindings": [
                        {
                            "target": "/request/headers/Content-Type",
                            "source": {"type": "literal", "value": "multipart/form-data"},
                        },
                        {
                            "target": "/request/multipart_form/segment_code",
                            "source": {"type": "literal", "value": "736851571937116162"},
                        },
                        {
                            "target": "/request/multipart_form/message_source",
                            "source": {"type": "literal", "value": "web_share"},
                        },
                    ],
                    "assertions": [{"type": "status_code", "expected": 200}],
                }
            ],
        },
    )

    args, kwargs = calls[0]
    assert args == ("POST", "https://example.test/sse")
    assert kwargs["files"] == [
        ("segment_code", (None, "736851571937116162")),
        ("message_source", (None, "web_share")),
    ]
    assert not kwargs["headers"] or "Content-Type" not in kwargs["headers"]
    assert kwargs["stream"] is True


def test_generated_segment_code_sse_flow_dispatches_dependency_and_dynamic_data(monkeypatch) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")
    assertions_module.assert_response_assertions = lambda response, assertions: None
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    monkeypatch.setenv("API_SCENARIO_INPUT_QUESTION", "很有问题")
    monkeypatch.setenv("API_SCENARIO_INPUT_USERNAME", "chen.li2")
    namespace = {}
    exec(renderer._scenario_py(), namespace)
    calls = []

    class FakeSession:
        def request(self, *args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(status_code=200, headers={}, json=lambda: {"ok": True}, close=lambda: None)

    class FakeClient:
        base_url = "https://example.test"
        timeout = 30
        session = FakeSession()

        def request(self, request_data, test_data):
            assert request_data["path"] == "/segment-code/gen"
            return SimpleNamespace(
                status_code=200,
                headers={},
                json=lambda: {"code": "000000", "data": {"segment_code": "segment-123"}},
            )

    outputs = namespace["run_scenario"](
        FakeClient(),
        {
            "variables": {},
            "steps": [
                {
                    "id": "generate",
                    "name": "生成 SegmentCode",
                    "endpoint": {"method": "POST", "path": "/segment-code/gen"},
                    "extractors": [{"name": "segment_code", "source": "json_body", "path": "/data/segment_code"}],
                },
                {
                    "id": "chat",
                    "name": "SSE 对话",
                    "endpoint": {
                        "method": "POST",
                        "path": "/sse",
                        "responses": {"200": {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
                    },
                    "bindings": [
                        {
                            "target": "/request/multipart_form/segment_code",
                            "source": {"type": "step_output", "step_id": "generate", "variable": "segment_code"},
                        },
                        {
                            "target": "/request/multipart_form/username",
                            "source": {"type": "user_input", "name": "username"},
                        },
                        {
                            "target": "/request/multipart_form/data",
                            "source": {
                                "type": "object",
                                "properties": {
                                    "agent_node_id": {"type": "literal", "value": ""},
                                    "question": {"type": "user_input", "name": "question"},
                                    "stream": {"type": "literal", "value": True},
                                },
                            },
                            "transform": "json_encode",
                        },
                    ],
                    "assertions": [{"type": "status_code", "expected": 200}],
                },
            ],
        },
    )

    assert outputs["generate"]["segment_code"] == "segment-123"
    parts = dict(calls[0][1]["files"])
    assert parts["segment_code"] == (None, "segment-123")
    assert parts["username"] == (None, "chen.li2")
    assert json.loads(parts["data"][1]) == {
        "agent_node_id": "",
        "question": "很有问题",
        "stream": True,
    }
    assert calls[0][1]["stream"] is True


def test_generated_scenario_probe_reuses_secret_headers_and_stops_after_target(monkeypatch) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")
    assertions_module.assert_response_assertions = lambda response, assertions: None
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    monkeypatch.setenv("API_HEADER_CYBERTRON_ROBOT_TOKEN", "token-value")
    monkeypatch.setenv("API_SCENARIO_PROBE_TARGET_STEP_ID", "stream")
    monkeypatch.setenv("API_SCENARIO_PROBE_MAX_EVENTS", "10")
    namespace = {}
    exec(renderer._scenario_py(), namespace)
    calls = []

    class FakeSseResponse:
        status_code = 200
        headers = {"Content-Type": "text/event-stream"}

        def iter_lines(self, decode_unicode=False):
            return iter([b"event: message", b'data: {"data":{"event_type":"answer"}}', b""])

    class FakeClient:
        def request(self, request_data, test_data):
            calls.append(request_data)
            return FakeSseResponse()

    outputs = namespace["run_scenario"](
        FakeClient(),
        {
            "steps": [
                {
                    "id": "stream",
                    "endpoint": {
                        "method": "POST",
                        "path": "/sse",
                        "responses": {"200": {"content": {"text/event-stream": {}}}},
                    },
                    "bindings": [
                        {
                            "target": "/request/headers/cybertron-robot-token",
                            "source": {"type": "secret", "key": "cybertron_robot_token"},
                        }
                    ],
                    "assertions": [{"type": "status_code", "expected": 200}],
                },
                {"id": "must-not-run", "endpoint": {"method": "GET", "path": "/unexpected"}},
            ]
        },
    )

    assert calls == [
        {
            "method": "POST",
            "path": "/sse",
            "headers": {"cybertron-robot-token": "token-value"},
        }
    ]
    assert outputs == {"stream": {}}


def test_generated_scenario_runtime_executes_assign_condition_and_wait(monkeypatch) -> None:
    support_module = ModuleType("support")
    assertions_module = ModuleType("support.assertions")

    def assert_response(response, assertions):
        return None

    assertions_module.assert_response_assertions = assert_response
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.assertions", assertions_module)
    namespace = {}
    exec(renderer._scenario_py(), namespace)
    sleeps = []
    namespace["time"].sleep = lambda seconds: sleeps.append(seconds)

    outputs = namespace["run_scenario"](
        object(),
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
            ],
        },
    )

    assert outputs["assign"] == {"tenant": "acme"}
    assert sleeps == [0.02]


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
    failed_step = result["steps"][0]
    assert isinstance(result["duration_ms"], float)
    assert isinstance(failed_step["duration_ms"], float)
    assert failed_step["step_type"] == "api_request"
    assert failed_step["request"]["request"]["headers"]["Authorization"] == "******"
    assert failed_step["response"]["status_code"] == 200
    assert failed_step["response"]["body"]["token"] == "******"
    assert failed_step["assertions"] == [{"type": "forced_failure"}]
    assert failed_step["attempts"][0]["status"] == "failed"
    assert result["steps"][1]["skip_reason"] == "前序步骤失败，执行链路已停止。"
    assert "secret-auth" not in serialized
    assert "secret-password" not in serialized
    assert "secret-cookie" not in serialized
    assert "secret-token" not in serialized


def test_generated_scenario_suite_collects_with_pytest(tmp_path) -> None:
    files = renderer.render_scenario_files(
        "profile_flow_apiscn_1",
        {
            "id": "apiscn-1",
            "name": "资料查询",
            "variables": {},
            "steps": [],
        },
    )
    assert renderer.SCENARIO_TEST_FILE in files
    assert "scenarios/profile_flow_apiscn_1/test_scenario.py" not in files
    assert "scenarios/profile_flow_apiscn_1/scenario.py" not in files
    for file_key, content in files.items():
        path = tmp_path / file_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\naddopts = --import-mode=importlib\npythonpath = .\ntestpaths = testcases\n",
        encoding="utf-8",
    )
    (tmp_path / "conftest.py").write_text(
        "import pytest\n\n@pytest.fixture\ndef api_client():\n    return object()\n",
        encoding="utf-8",
    )

    result = collect_script_suite(
        suite_path=tmp_path,
        timeout=120,
        test_paths=[renderer.SCENARIO_TEST_FILE],
    )

    assert result["ok"], result["stderr"] or result["stdout"]

    execution = run_script_suite(
        run_id="apirun-1",
        project_id="project-1",
        suite_path=tmp_path,
        run_dir=tmp_path / "run",
        environment={"api_base_url": "https://api.example.test"},
        timeout=120,
        test_paths=[renderer.SCENARIO_TEST_FILE],
        scenario_file="scenarios/profile_flow_apiscn_1/scenario.json",
    )

    assert execution["status"] == "passed", execution["error_message"]
    assert json.loads(Path(execution["scenario_result_path"]).read_text(encoding="utf-8"))["status"] == "passed"


def test_generated_scenario_suite_runs_in_sse_probe_mode(tmp_path) -> None:
    files = renderer.render_scenario_files(
        "probe_apiscn_1",
        {
            "id": "apiscn-1",
            "name": "SSE 探测",
            "variables": {},
            "steps": [
                {
                    "id": "stream",
                    "name": "流式回答",
                    "endpoint": {
                        "method": "POST",
                        "path": "/stream",
                        "responses": {"200": {"content": {"text/event-stream": {}}}},
                    },
                    "bindings": [
                        {
                            "target": "/request/headers/cybertron-robot-token",
                            "source": {"type": "secret", "key": "cybertron_robot_token"},
                        }
                    ],
                    "assertions": [{"type": "status_code", "expected": 200}],
                },
                {"id": "after", "name": "不应执行", "endpoint": {"method": "GET", "path": "/after"}},
            ],
        },
    )
    for file_key, content in files.items():
        path = tmp_path / file_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\naddopts = --import-mode=importlib\npythonpath = .\ntestpaths = testcases\n",
        encoding="utf-8",
    )
    (tmp_path / "conftest.py").write_text(
        """
import pytest

class Response:
    status_code = 200
    headers = {"Content-Type": "text/event-stream"}
    def iter_lines(self, decode_unicode=False):
        return iter([b"event: message", b'data: {"data":{"event_type":"answer"}}', b""])

class Client:
    def request(self, request_data, test_data):
        assert request_data["headers"]["cybertron-robot-token"] == "secret-token"
        return Response()

@pytest.fixture
def api_client():
    return Client()
""".lstrip(),
        encoding="utf-8",
    )

    execution = run_script_suite(
        run_id="probe-1",
        project_id="project-1",
        suite_path=tmp_path,
        run_dir=tmp_path / "run",
        environment={
            "api_base_url": "https://api.example.test",
            "headers": {"cybertron-robot-token": "secret-token"},
        },
        timeout=120,
        test_paths=[renderer.SCENARIO_TEST_FILE],
        scenario_file="scenarios/probe_apiscn_1/scenario.json",
        scenario_probe_target_step_id="stream",
        scenario_probe_max_stream_seconds=60,
    )

    assert execution["status"] == "passed", execution["error_message"]
    result = json.loads(Path(execution["scenario_result_path"]).read_text(encoding="utf-8"))
    assert [step["step_id"] for step in result["steps"]] == ["stream"]
    event = result["steps"][0]["response"]["body"]["events"][0]
    assert event["data"]["data"]["event_type"] == "answer"
    assert event["received_offset_ms"] >= 0


def test_generated_scenario_test_uses_shared_runtime_and_selected_data_file() -> None:
    source = renderer._test_scenario_py()

    assert "from support.scenario import run_scenario" in source
    assert 'os.environ.get("API_SCENARIO_FILE"' in source
    assert "pytestmark = pytest.mark.skipif(" in source
    assert "from scenario import run_scenario" not in source
