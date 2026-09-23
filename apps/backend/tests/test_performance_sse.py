from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.performance_testing.script_generation.planner import build_default_plan
from app.schemas.performance_test import PerformanceRequestConfig
from app.schemas.performance_test import PerformanceGoal, PerformanceTestCreateIn
from app.services.performance_testing.headless_worker import summarize_sse_measurements
from app.services.performance_testing.script_renderer import render_locust_script, runtime_module_source
from app.services.performance_testing.sse import event_matches, parse_sse_events, validate_metric_rule


def _sse_config() -> dict:
    return {
        "max_stream_seconds": 10,
        "end_rule": {"source": "data_text", "operator": "equals", "expected": "[DONE]"},
        "metrics": [
            {
                "id": "first_content",
                "name": "首内容",
                "match": {
                    "source": "data_json",
                    "path": "$.choices[*].delta.content",
                    "operator": "non_empty",
                },
            },
            {
                "id": "first_tool_call",
                "name": "首次工具调用",
                "match": {
                    "source": "data_json",
                    "path": "$.choices[*].delta.tool_calls[*]",
                    "operator": "exists",
                },
            },
        ],
    }


class _FakeSseResponse:
    def __init__(self, lines: list[str], *, content_type: str = "text/event-stream") -> None:
        self.status_code = 200
        self.headers = {"Content-Type": content_type}
        self._lines = lines
        self.failure_reason = ""
        self.succeeded = False

    def __enter__(self) -> "_FakeSseResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def iter_lines(self, chunk_size: int = 512, decode_unicode: bool = True):
        assert chunk_size == 1
        assert decode_unicode is True
        return iter(self._lines)

    def failure(self, reason: str) -> None:
        self.failure_reason = reason

    def success(self) -> None:
        self.succeeded = True


class _FakeSseClient:
    def __init__(self, response: _FakeSseResponse) -> None:
        self.response = response

    def request(self, **_kwargs: object) -> _FakeSseResponse:
        return self.response


class _FakeSseUser:
    def __init__(self, response: _FakeSseResponse) -> None:
        self.client = _FakeSseClient(response)


def _rendered_sse_runtime(measurements: list[dict]) -> dict[str, object]:
    source = runtime_module_source()
    source = source[:source.index("def execute_plan")]
    source = source.replace("from locust import HttpUser, LoadTestShape, between, events, task\n", "")
    namespace: dict[str, object] = {}
    exec(source, namespace)
    namespace["SSE_MEASUREMENT_SINK"] = measurements.append

    def execute_sse_request(user, request, path, measurement_context=None):
        context = measurement_context or {}
        step = {
            "id": context.get("scenario_step_id") or "",
            "name": context.get("scenario_step_name") or request.get("name") or "",
        }
        try:
            namespace["_execute_sse"](user, request, path, step, measurement_context=context)
        except AssertionError as exc:
            return str(exc)
        return ""

    namespace["_execute_sse_request"] = execute_sse_request
    return namespace


def _runtime_sse_request() -> dict:
    return {
        "method": "POST",
        "name": "POST /chat",
        "headers": {},
        "query_parameters": {},
        "timeout_seconds": 30,
        "sse": {
            "max_stream_seconds": 10,
            "end_rule": None,
            "metrics": [
                {
                    "id": "llm_start",
                    "match": {
                        "event_name": "message",
                        "source": "data_json",
                        "path": "$.data.event_type",
                        "operator": "equals",
                        "expected": "call_llm_start",
                    },
                    "missing_policy": "record_null",
                },
                {
                    "id": "first_output",
                    "match": {
                        "event_name": "message",
                        "source": "data_json",
                        "path": "$.data.answer",
                        "operator": "non_empty",
                    },
                    "missing_policy": "record_null",
                },
            ],
        },
    }


def test_sse_parser_preserves_multiline_data_and_matches_wildcard_path() -> None:
    events = parse_sse_events(
        [
            ": keepalive\n",
            "event: message\n",
            'data: {"choices":[{"delta":\n',
            'data: {"content":"hello"}}]}\n',
            "\n",
        ]
    )
    assert len(events) == 1
    assert events[0].event_name == "message"
    assert event_matches(
        events[0],
        {"event_name": "message", "source": "data_json", "path": "$.choices[*].delta.content", "operator": "non_empty"},
    )


def test_sse_parser_and_regex_rules_enforce_resource_safety_limits() -> None:
    with pytest.raises(ValueError, match="sse_stream_too_large"):
        parse_sse_events(["data: 123456\n", "\n"], max_stream_bytes=8)

    with pytest.raises(ValueError, match="高风险结构"):
        validate_metric_rule(
            {
                "id": "unsafe_regex",
                "match": {"source": "data_text", "operator": "matches", "expected": "(a+)+"},
            }
        )

def test_sse_config_rejects_invalid_path_and_duplicate_metric_id() -> None:
    config = _sse_config()
    config["metrics"].append({**config["metrics"][0], "name": "重复"})
    with pytest.raises(ValidationError, match="不能重复"):
        PerformanceRequestConfig(transport="sse", sse=config)

    invalid = _sse_config()
    invalid["metrics"][0]["match"]["path"] = "$.choices[?(@.x)]"
    with pytest.raises(ValidationError, match="JSONPath"):
        PerformanceRequestConfig(transport="sse", sse=invalid)


def test_sse_config_allows_no_event_metrics() -> None:
    request = PerformanceRequestConfig(
        transport="sse",
        sse={"max_stream_seconds": 10, "end_rule": None, "metrics": []},
    )

    assert request.sse is not None
    assert request.sse.metrics == []


def test_sse_config_validates_explicit_metric_timing_dependency() -> None:
    request = PerformanceRequestConfig(
        transport="sse",
        sse={
            "metrics": [
                {
                    "id": "llm_start",
                    "name": "LLM 开始",
                    "match": {
                        "source": "data_json",
                        "path": "$.data.event_type",
                        "operator": "equals",
                        "expected": "call_llm_start",
                    },
                },
                {
                    "id": "first_content_after_llm",
                    "name": "LLM 后首内容",
                    "timing": {"start": "metric_matched", "start_metric_id": "llm_start"},
                    "match": {
                        "source": "data_json",
                        "path": "$.data.index",
                        "operator": "equals",
                        "expected": 0,
                    },
                },
            ]
        },
    )

    assert request.sse is not None
    assert request.sse.metrics[1].timing.start == "metric_matched"

    with pytest.raises(ValidationError, match="不存在的起点指标"):
        PerformanceRequestConfig(
            transport="sse",
            sse={
                "metrics": [
                    {
                        "id": "first_content_after_llm",
                        "name": "LLM 后首内容",
                        "timing": {"start": "metric_matched", "start_metric_id": "missing"},
                        "match": {
                            "source": "data_json",
                            "path": "$.data.index",
                            "operator": "equals",
                            "expected": 0,
                        },
                    }
                ]
            },
        )


def test_sse_metric_timing_defaults_to_current_request_and_rejects_other_scenario_step() -> None:
    request = PerformanceRequestConfig(
        transport="sse",
        scenario_step_id="step_sse_chat",
        sse=_sse_config(),
    )

    metric = request.sse.metrics[0]
    assert metric.category == "custom_event"
    assert metric.timing.scope == "request"
    assert metric.timing.start == "request_started"
    assert metric.timing.source_request_id is None

    invalid = _sse_config()
    invalid["metrics"][0]["timing"] = {
        "scope": "request",
        "start": "request_started",
        "source_request_id": "step_gen_segment_code",
    }
    with pytest.raises(ValidationError, match="当前 SSE 场景步骤"):
        PerformanceRequestConfig(
            transport="sse",
            scenario_step_id="step_sse_chat",
            sse=invalid,
        )


def test_sse_metric_goals_are_unique_and_reference_configured_metrics() -> None:
    with pytest.raises(ValidationError, match="只能配置一个"):
        PerformanceGoal(
            sse_metric_goals=[
                {"metric_id": "first_content", "percentile": "p95", "target_ms": 1000},
                {"metric_id": "first_content", "percentile": "p95", "target_ms": 1200},
            ]
        )

    with pytest.raises(ValidationError, match="不存在的指标"):
        PerformanceTestCreateIn(
            name="SSE test",
            endpoint_id="endpoint-1",
            api_environment_id="env-1",
            request_config={"transport": "sse", "sse": _sse_config()},
            performance_goal={
                "sse_metric_goals": [
                    {"metric_id": "unknown_metric", "percentile": "p95", "target_ms": 1000}
                ]
            },
        )


def test_sse_renderer_streams_and_keeps_measurements_separate() -> None:
    plan = build_default_plan(
        {
            "id": "perftest-sse",
            "endpoint_method": "POST",
            "endpoint_path": "/chat",
            "request_config": {"transport": "sse", "sse": _sse_config(), "headers": {}, "body": {"q": "hi"}},
            "load_config": {"mode": "fixed", "wait_time_min_seconds": 1, "wait_time_max_seconds": 2, "request_timeout_seconds": 15},
            "data_config": {"source": "fixed", "selection_strategy": "sequential_loop", "json_rows": []},
            "success_rules": [{"kind": "status_code", "status_codes": [200]}],
        }
    )

    source = render_locust_script(plan)

    assert "class EndpointUser(HttpUser):" in source
    assert "'transport': 'sse'" in source
    assert '"metrics"' in source


def test_rendered_sse_runtime_rejects_json_business_error_disguised_as_stream() -> None:
    measurements: list[dict] = []
    runtime = _rendered_sse_runtime(measurements)
    response = _FakeSseResponse(
        ['{"code":"500001","data":{},"msg":"Internal Cache Error:websocket: bad handshake"}']
    )

    failure_reason = runtime["_execute_sse_request"](
        _FakeSseUser(response),
        _runtime_sse_request(),
        "/chat",
        measurement_context={
            "scenario_step_id": "step_sse_chat",
            "scenario_step_name": "02 POST /openapi/v1/gw/multi-agent/sse",
        },
    )

    assert failure_reason == "sse_business_error:500001"
    assert response.failure_reason == failure_reason
    assert response.succeeded is False
    assert len(measurements) == 1
    assert measurements[0]["failure_reason"] == "sse_business_error:500001"
    assert measurements[0]["line_count"] == 1
    assert measurements[0]["data_frame_count"] == 0
    assert measurements[0]["content_type"] == "text/event-stream"
    assert measurements[0]["response_error_code"] == "500001"


def test_rendered_sse_runtime_parses_raw_frames_and_flushes_final_frame() -> None:
    measurements: list[dict] = []
    runtime = _rendered_sse_runtime(measurements)
    response = _FakeSseResponse(
        [
            'data: {"data":{"event_type":"answer","answer":"模型调用前的内容"}}',
            "",
            'data: {"data":\r',
            'data: {"event_type":"call_llm_start"}}\r',
            "\r",
            'data: {"data":{"event_type":"answer","answer":""}}',
            "",
            'data: {"data":{"event_type":"answer","answer":"有效内容"}}',
        ]
    )

    failure_reason = runtime["_execute_sse_request"](
        _FakeSseUser(response),
        _runtime_sse_request(),
        "/chat",
        measurement_context={
            "scenario_step_id": "step_sse_chat",
            "scenario_step_name": "02 POST /openapi/v1/gw/multi-agent/sse",
        },
    )

    assert failure_reason == ""
    assert response.succeeded is True
    assert set(measurements[0]["metrics"]) == {"llm_start", "first_output"}
    assert measurements[0]["metrics"]["first_output"] >= measurements[0]["metrics"]["llm_start"]
    assert measurements[0]["connection_ms"] <= measurements[0]["metrics"]["llm_start"]
    assert measurements[0]["source_request_id"] == "step_sse_chat"
    assert measurements[0]["source_request_name"] == "02 POST /openapi/v1/gw/multi-agent/sse"
    assert "derived_metrics" not in measurements[0]
    assert measurements[0]["missing_metric_ids"] == []
    assert measurements[0]["frame_count"] == 4
    assert measurements[0]["data_frame_count"] == 4
    assert measurements[0]["parse_error_count"] == 0


def test_rendered_sse_runtime_matches_llm_start_before_first_output_in_same_frame() -> None:
    measurements: list[dict] = []
    runtime = _rendered_sse_runtime(measurements)
    response = _FakeSseResponse(
        ['data: {"data":{"event_type":"call_llm_start","answer":"首字"}}', ""]
    )
    request = _runtime_sse_request()
    request["sse"]["metrics"].reverse()

    failure_reason = runtime["_execute_sse_request"](
        _FakeSseUser(response),
        request,
        "/chat",
    )

    assert failure_reason == ""
    assert set(measurements[0]["metrics"]) == {"llm_start", "first_output"}
    assert measurements[0]["metrics"]["first_output"] == measurements[0]["metrics"]["llm_start"]
    assert "derived_metrics" not in measurements[0]


def test_rendered_sse_runtime_does_not_measure_unconfigured_metrics() -> None:
    measurements: list[dict] = []
    runtime = _rendered_sse_runtime(measurements)
    response = _FakeSseResponse(['data: [DONE]', ""])
    request = _runtime_sse_request()
    request["sse"]["metrics"] = []

    failure_reason = runtime["_execute_sse_request"](_FakeSseUser(response), request, "/chat")

    assert failure_reason == ""
    assert measurements[0]["metrics"] == {}
    assert measurements[0]["missing_metric_ids"] == []
    assert measurements[0]["non_json_frame_count"] == 1
    assert measurements[0]["parse_error_count"] == 0
    assert "derived_metrics" not in measurements[0]


def test_rendered_sse_runtime_calculates_explicit_metric_interval_only_when_configured() -> None:
    measurements: list[dict] = []
    runtime = _rendered_sse_runtime(measurements)
    response = _FakeSseResponse(
        [
            'data: {"data":{"event_type":"call_llm_start"}}',
            "",
            'data: {"data":{"event_type":"answer","index":0,"answer":"首内容"}}',
            "",
        ]
    )
    request = _runtime_sse_request()
    request["sse"]["metrics"][1]["timing"] = {"start": "metric_matched", "start_metric_id": "llm_start"}

    failure_reason = runtime["_execute_sse_request"](_FakeSseUser(response), request, "/chat")

    assert failure_reason == ""
    assert measurements[0]["metrics"]["first_output"] >= 0
    assert measurements[0]["metrics"]["first_output"] < 1
    assert "derived_metrics" not in measurements[0]


def test_sse_measurement_summary_keeps_missing_and_percentiles(tmp_path: Path) -> None:
    path = tmp_path / "sse-measurements.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"metrics":{"first_content":100,"first_tool_call":200},"missing_metric_ids":[],"failure_reason":""}',
                '{"metrics":{"first_content":300},"derived_metrics":{"llm_start_to_first_content_ms":80},"missing_metric_ids":["first_tool_call"],"failure_reason":""}',
                '{"metrics":{"first_content":500},"missing_metric_ids":["first_tool_call"],"failure_reason":"sse_stream_timeout","parse_error_count":2}',
            ]
        ),
        encoding="utf-8",
    )

    summary = summarize_sse_measurements(path)
    content = next(metric for metric in summary["metrics"] if metric["metric_id"] == "first_content")
    tool = next(metric for metric in summary["metrics"] if metric["metric_id"] == "first_tool_call")
    assert summary["attempt_count"] == 3
    assert content["matched_count"] == 3
    assert content["p95_ms"] == 300
    assert tool["matched_count"] == 1
    assert tool["missing_count"] == 2
    assert tool["failure_count"] == 1
    assert all(not metric["metric_id"].startswith("derived:") for metric in summary["metrics"])
    assert summary["schema_version"] == "v1"
    assert summary["checksum"].startswith("sha256:")
    assert summary["failure_reasons"] == {"sse_stream_timeout": 1}
    assert summary["parse_error_count"] == 2
    assert summary["timeout_count"] == 1


def test_sse_measurement_summary_reports_truncated_storage(tmp_path: Path) -> None:
    path = tmp_path / "sse-measurements.jsonl"
    path.write_text('{"schema_version":"v1","metrics":{},"missing_metric_ids":[]}\n', encoding="utf-8")
    path.with_name("sse-measurements.meta.json").write_text(
        '{"schema_version":"v1","truncated":true}', encoding="utf-8"
    )

    summary = summarize_sse_measurements(path)

    assert summary["truncated"] is True
    assert summary["attempt_count"] == 1
