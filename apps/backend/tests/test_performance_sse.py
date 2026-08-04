import json
import re
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.performance_testing.script_generation.planner import build_default_plan
from app.schemas.performance_test import PerformanceRequestConfig
from app.schemas.performance_test import PerformanceGoal, PerformanceTestCreateIn
from app.services.performance_testing.headless_worker import summarize_sse_measurements
from app.services.performance_testing.script_renderer import _render_sse_helpers, render_locust_script
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

    def iter_lines(self, decode_unicode: bool = True):
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
    namespace: dict[str, object] = {
        "json": json,
        "re": re,
        "time": time,
        "_request_payload_kwargs": lambda _request, headers=None: {"headers": headers or {}},
    }
    exec(_render_sse_helpers(), namespace)
    namespace["SSE_MEASUREMENT_SINK"] = measurements.append
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

    assert "stream=True" in source
    assert "response.iter_lines" in source
    assert "SSE_MEASUREMENT_SINK" in source
    assert "events.request.fire" not in source
    assert "sse_stream_too_large" in source
    assert '"parse_error_count": 0' in source
    assert "reported_missing" in source
    assert 'metric["missing_policy"] != "ignore"' in source
    assert '"missing_metric_ids": reported_missing' in source
    assert 'event_name, data_lines, frame_size, stream_size, ended = "message", [], 0, 0, False' in source
    assert 'event_name, data_lines, frame_size = "message", [], 0' in source
    assert 'event_name = value or "message"' in source


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
    )

    assert failure_reason == ""
    assert response.succeeded is True
    assert set(measurements[0]["metrics"]) == {"llm_start", "first_output"}
    assert measurements[0]["derived_metrics"]["llm_start_to_first_content_ms"] >= 0
    assert measurements[0]["missing_metric_ids"] == []
    assert measurements[0]["frame_count"] == 3
    assert measurements[0]["data_frame_count"] == 3
    assert measurements[0]["parse_error_count"] == 0


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
    derived = next(
        metric for metric in summary["metrics"] if metric["metric_id"] == "derived:llm_start_to_first_content"
    )

    assert summary["attempt_count"] == 3
    assert content["matched_count"] == 3
    assert content["p95_ms"] == 300
    assert tool["matched_count"] == 1
    assert tool["missing_count"] == 2
    assert tool["failure_count"] == 1
    assert derived["matched_count"] == 1
    assert derived["average_ms"] == 80
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
