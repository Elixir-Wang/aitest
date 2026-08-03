import json

import pytest
from pydantic import ValidationError

from app.schemas.performance_test import PerformanceSseMetricGenerateIn
from app.services.performance_testing.sse import SseEvent
from app.services.performance_testing.sse_metric_generation import (
    CapturedSseEvent,
    build_deterministic_sse_config,
    capture_sse_events,
    execute_sse_probe,
    generate_sse_metric_candidate,
    validate_sse_candidate,
)


def _captured(sequence: int, offset_ms: int, event_type: str, **data) -> CapturedSseEvent:
    payload = {
        "code": "000000",
        "data": {"event_type": event_type, **data},
        "type": "multi_agent",
    }
    return CapturedSseEvent(
        sequence=sequence,
        received_offset_ms=offset_ms,
        event=SseEvent(event_name="message", data_text=json.dumps(payload, ensure_ascii=False)),
    )


def _sample_events() -> list[CapturedSseEvent]:
    return [
        _captured(1, 0, "start", role="user", answer="你好"),
        _captured(2, 341, "call_llm_start", role="assistant"),
        _captured(3, 2999, "answer", role="assistant", answer="你好呀！"),
        _captured(4, 3071, "answer", role="assistant", answer="今天过得怎么样？"),
        _captured(5, 3717, "call_llm_end", role="assistant"),
        _captured(6, 3717, "query_end", role="assistant"),
    ]


def test_deterministic_config_uses_single_frame_event_type_path() -> None:
    config = build_deterministic_sse_config(_sample_events(), max_stream_seconds=60)

    assert config["metrics"][0]["match"] == {
        "event_name": "message",
        "source": "data_json",
        "path": "$.data.event_type",
        "operator": "equals",
        "expected": "call_llm_start",
    }
    assert config["metrics"][1]["match"]["expected"] == "answer"
    assert config["end_rule"]["expected"] == "query_end"
    assert "body.events" not in json.dumps(config)


def test_validation_reports_first_match_and_total_match_count() -> None:
    config = build_deterministic_sse_config(_sample_events(), max_stream_seconds=60)

    result = validate_sse_candidate(_sample_events(), config)

    assert result["valid"] is True
    assert result["metrics"] == [
        {
            "metric_id": "call_llm_start",
            "matched_count": 1,
            "first_event_sequence": 2,
            "sample_elapsed_ms": 341,
            "sample_event": {
                "event": "message",
                "event_type": "call_llm_start",
                "role": "assistant",
            },
        },
        {
            "metric_id": "first_answer",
            "matched_count": 2,
            "first_event_sequence": 3,
            "sample_elapsed_ms": 2999,
            "sample_event": {
                "event": "message",
                "event_type": "answer",
                "role": "assistant",
                "answer": "你好呀！",
            },
        },
    ]
    assert result["end_rule"] == {"matched_count": 1, "first_event_sequence": 6}


def test_generation_falls_back_when_ai_suggestion_is_invalid() -> None:
    result = generate_sse_metric_candidate(
        _sample_events(),
        max_stream_seconds=60,
        ai_suggester=lambda _: {
            "metrics": [
                {
                    "id": "first_answer",
                    "name": "首次回答时间",
                    "match": {
                        "event_name": "message",
                        "source": "data_json",
                        "path": "$.wrong.path",
                        "operator": "equals",
                        "expected": "answer",
                    },
                    "occurrence": "first",
                    "missing_policy": "fail_request",
                }
            ],
            "end_rule": None,
        },
    )

    assert result["generation_source"] == "deterministic_fallback"
    assert result["validation"]["valid"] is True
    assert [metric["id"] for metric in result["candidate_sse"]["metrics"]] == [
        "call_llm_start",
        "first_answer",
    ]
    assert result["warnings"] == ["AI 生成的指标规则未通过样本回放，已使用确定性识别结果。"]


def test_ai_input_preserves_match_shape_but_redacts_unrelated_business_data() -> None:
    events = [
        CapturedSseEvent(
            sequence=1,
            received_offset_ms=12,
            event=SseEvent(
                event_name="message",
                data_text=json.dumps(
                    {
                        "code": "000000",
                        "data": {
                            "event_type": "answer",
                            "role": "assistant",
                            "answer": "敏感回答正文",
                            "dialog_id": "secret-dialog",
                        },
                        "meta_data": {"trace_id": "secret-trace"},
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    ]
    captured_input = {}

    def suggester(payload):
        captured_input.update(payload)
        return build_deterministic_sse_config(events, max_stream_seconds=60)

    generate_sse_metric_candidate(events, max_stream_seconds=60, ai_suggester=suggester)

    serialized = json.dumps(captured_input, ensure_ascii=False)
    assert "secret-dialog" not in serialized
    assert "secret-trace" not in serialized
    assert "敏感回答正文" not in serialized
    assert captured_input["events"][0]["data_json"]["data"] == {
        "event_type": "answer",
        "role": "assistant",
        "answer": "<non-empty>",
    }


def test_capture_uses_client_receive_offsets_and_stops_on_event_limit() -> None:
    class FakeResponse:
        def iter_lines(self, decode_unicode: bool = False):
            assert decode_unicode is True
            return iter(
                [
                    "event: message",
                    'data: {"data":{"event_type":"call_llm_start"}}',
                    "",
                    "event: message",
                    'data: {"data":{"event_type":"answer","answer":"ok"}}',
                    "",
                    "event: message",
                    'data: {"data":{"event_type":"query_end"}}',
                    "",
                ]
            )

    clock_values = iter([100.341, 102.999, 103.717])

    events, truncated = capture_sse_events(
        FakeResponse(),
        started_at=100.0,
        clock=lambda: next(clock_values),
        max_events=2,
    )

    assert [event.received_offset_ms for event in events] == [341, 2999]
    assert [event.event.event_name for event in events] == ["message", "message"]
    assert truncated is True


def test_generation_input_accepts_unsaved_request_values_and_bounds_stream_time() -> None:
    payload = PerformanceSseMetricGenerateIn(
        endpoint_id="endpoint-1",
        api_environment_id="environment-1",
        path_parameters={"dialog_id": "123"},
        query_parameters={"stream": True},
        headers={"X-Tenant": "demo"},
        body={"message": "你好"},
        max_stream_seconds=60,
    )

    assert payload.query_parameters == {"stream": True}
    with pytest.raises(ValidationError):
        PerformanceSseMetricGenerateIn(
            endpoint_id="endpoint-1",
            api_environment_id="environment-1",
            max_stream_seconds=601,
        )


def test_execute_probe_streams_current_unsaved_request_configuration() -> None:
    calls = []

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "text/event-stream; charset=utf-8"}

        def iter_lines(self, decode_unicode: bool = False):
            return iter(
                [
                    "event: message",
                    'data: {"data":{"event_type":"call_llm_start"}}',
                    "",
                    "event: message",
                    'data: {"data":{"event_type":"answer","answer":"ok"}}',
                    "",
                ]
            )

        def close(self):
            calls.append("closed")

    def requester(**kwargs):
        calls.append(kwargs)
        return FakeResponse()

    clock_values = iter([100.0, 100.2, 101.5])
    result = execute_sse_probe(
        {
            "method": "POST",
            "url": "https://example.test/chat/123",
            "query_parameters": {"stream": True},
            "headers": {"X-Tenant": "demo"},
            "body": {"message": "你好"},
            "timeout_seconds": 10,
            "verify_ssl": True,
        },
        max_stream_seconds=60,
        requester=requester,
        clock=lambda: next(clock_values),
    )

    assert calls[0]["stream"] is True
    assert calls[0]["params"] == {"stream": True}
    assert calls[0]["json"] == {"message": "你好"}
    assert calls[-1] == "closed"
    assert result["status_code"] == 200
    assert [event.received_offset_ms for event in result["events"]] == [200, 1500]
