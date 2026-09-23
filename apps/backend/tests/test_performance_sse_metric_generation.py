import json

import pytest
from pydantic import ValidationError

from app.schemas.performance_test import PerformanceSseMetricGenerateIn
from app.services.performance_testing.sse import SseEvent
from app.services.performance_testing.sse_metric_generation import (
    CapturedSseEvent,
    _scenario_execution_probe,
    _scenario_source_request,
    build_structural_sse_candidates,
    capture_sse_events,
    execute_sse_probe,
    extract_sse_event_facts,
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


def test_scenario_source_request_uses_numbered_method_and_path_instead_of_step_title() -> None:
    snapshot = {
        "steps": [
            {"id": "step-code", "name": "准备参数", "endpoint": {"method": "POST", "path": "/segment-code"}},
            {"id": "step-sse", "name": "对话(SSE)", "endpoint": {"method": "POST", "path": "/chat/sse"}},
        ]
    }

    assert _scenario_source_request(snapshot, "step-sse") == ("step-sse", "02 POST /chat/sse")


def test_event_facts_aggregate_observed_values_without_exposing_content() -> None:
    facts = extract_sse_event_facts(_sample_events())

    answer_fact = next(
        fact
        for fact in facts
        if fact["path"] == "$.data.event_type" and fact["normalized_value"] == "answer"
    )
    assert answer_fact["matched_count"] == 2
    assert answer_fact["first_sequence"] == 3
    assert answer_fact["last_sequence"] == 4
    assert answer_fact["first_offset_ms"] == 2999
    assert answer_fact["last_offset_ms"] == 3071
    assert answer_fact["has_non_empty_content"] is True
    assert answer_fact["metric_id"].startswith("sse_custom_")
    serialized = json.dumps(facts, ensure_ascii=False)
    assert "你好呀" not in serialized
    assert "今天过得怎么样" not in serialized


def test_structural_candidates_use_observed_facts_without_required_metric_ids() -> None:
    facts = extract_sse_event_facts(_sample_events())

    candidates = build_structural_sse_candidates(_sample_events(), facts)

    assert candidates
    assert {
        candidate["match"]["expected"]
        for candidate in candidates
        if "expected" in candidate["match"]
    }.issubset(
        {"start", "call_llm_start", "answer", "call_llm_end", "query_end"}
    )
    assert {candidate["metric_id"] for candidate in candidates}.isdisjoint(
        {"call_llm_start", "first_answer"}
    )
    assert all(candidate["validation"]["matched_count"] > 0 for candidate in candidates)
    assert [candidate["validation"]["first_event_sequence"] for candidate in candidates] == sorted(
        candidate["validation"]["first_event_sequence"] for candidate in candidates
    )
    assert not any(
        candidate["category"] == "first_output" and candidate["match"].get("expected") == "start"
        for candidate in candidates
    )


def test_first_output_candidate_prefers_index_zero_like_reference_client() -> None:
    events = [
        _captured(1, 0, "start", role="assistant", answer="前置内容", index=-1),
        _captured(2, 800, "call_llm_start", role="assistant"),
        _captured(3, 900, "answer", role="assistant", answer="首个有效片段", index=0),
    ]

    candidates = build_structural_sse_candidates(events, extract_sse_event_facts(events))
    first_output = next(candidate for candidate in candidates if candidate["category"] == "first_output")

    assert first_output["match"] == {
        "event_name": "message",
        "source": "data_json",
        "path": "$.data.index",
        "operator": "equals",
        "expected": 0,
    }
    assert first_output["validation"]["first_event_sequence"] == 3


def test_content_bearing_end_event_keeps_completion_semantics() -> None:
    events = [
        _captured(1, 0, "call_llm_start", role="assistant"),
        _captured(2, 1200, "answer", role="assistant", answer="流式片段"),
        _captured(3, 1800, "call_llm_end", role="assistant", answer="完整回答"),
        _captured(4, 1810, "query_end", role="assistant"),
    ]

    candidates = build_structural_sse_candidates(events, extract_sse_event_facts(events))
    by_event_type = {
        candidate["match"]["expected"]: candidate
        for candidate in candidates
        if "expected" in candidate["match"]
    }
    first_output = next(candidate for candidate in candidates if candidate["category"] == "first_output")

    assert first_output["match"]["path"] == "$.data.answer"
    assert by_event_type["call_llm_end"]["category"] == "milestone_end"
    assert by_event_type["call_llm_end"]["name"] == "call_llm 完成时间"
    assert "首次到达" not in by_event_type["call_llm_end"]["name"]
    assert by_event_type["query_end"]["category"] == "completion"
    assert by_event_type["query_end"]["name"] == "query 完成时间"


def test_phase_event_content_does_not_consume_first_output_candidate() -> None:
    events = [
        _captured(1, 0, "call_llm_start", role="assistant", content="调用参数"),
        _captured(2, 900, "answer", role="assistant", answer="首个响应片段"),
        _captured(3, 1200, "call_llm_end", role="assistant"),
    ]

    candidates = build_structural_sse_candidates(events, extract_sse_event_facts(events))
    by_event_type = {
        candidate["match"]["expected"]: candidate
        for candidate in candidates
        if "expected" in candidate["match"]
    }
    first_output = next(candidate for candidate in candidates if candidate["category"] == "first_output")

    assert by_event_type["call_llm_start"]["category"] == "milestone_start"
    assert first_output["match"]["path"] == "$.data.answer"


def test_validation_reports_first_match_and_total_match_count() -> None:
    config = {
        "max_stream_seconds": 60,
        "metrics": [
            {
                "id": "sse_answer_example",
                "name": "首次有效内容到达时间",
                "match": {
                    "event_name": "message",
                    "source": "data_json",
                    "path": "$.data.event_type",
                    "operator": "equals",
                    "expected": "answer",
                },
                "occurrence": "first",
                "missing_policy": "record_null",
            }
        ],
        "end_rule": None,
    }

    result = validate_sse_candidate(_sample_events(), config)

    assert result["valid"] is True
    assert result["metrics"] == [
        {
            "metric_id": "sse_answer_example",
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
    assert result["end_rule"] == {"matched_count": 0, "first_event_sequence": None}


def test_generation_does_not_activate_structural_candidates_when_ai_suggestion_is_invalid() -> None:
    result = generate_sse_metric_candidate(
        _sample_events(),
        max_stream_seconds=60,
        ai_suggester=lambda _: {"candidates": [{"fact_id": "missing", "name": "无效"}]},
    )

    assert result["analysis"]["ai_status"] == "not_used"
    assert result["analysis"]["generation_mode"] == "event_catalog_only"
    assert result["result_status"] == "empty"
    assert result["candidates"] == []
    assert result["event_facts"]
    assert result["messages"] == ["本次样本未发现高可信度性能指标，可从事件目录中手动选择。"]
    assert "candidate_sse" not in result


def test_ai_candidates_are_returned_in_sse_event_order() -> None:
    events = _sample_events()
    facts = extract_sse_event_facts(events)
    end_fact = next(fact for fact in facts if fact["normalized_value"] == "call_llm_end")
    start_fact = next(fact for fact in facts if fact["normalized_value"] == "call_llm_start")

    result = generate_sse_metric_candidate(
        events,
        max_stream_seconds=60,
        ai_suggester=lambda _: {
            "candidates": [
                {"fact_id": end_fact["fact_id"], "name": "LLM 完成", "category": "milestone_end", "confidence": 0.99},
                {"fact_id": start_fact["fact_id"], "name": "LLM 开始", "category": "milestone_start", "confidence": 0.99},
            ]
        },
    )

    sequences = [candidate["validation"]["first_event_sequence"] for candidate in result["candidates"]]
    assert sequences == sorted(sequences)


def test_generated_candidates_bind_timing_to_the_confirmed_sse_request() -> None:
    def suggester(payload):
        fact = next(item for item in payload["facts"] if item["normalized_value"] == "call_llm_start")
        return {
            "candidates": [
                {
                    "fact_id": fact["fact_id"],
                    "name": "LLM 开始",
                    "category": "milestone_start",
                    "confidence": 0.99,
                }
            ]
        }

    result = generate_sse_metric_candidate(
        _sample_events(),
        max_stream_seconds=60,
        ai_suggester=suggester,
        source_request_id="step_sse_chat",
        source_request_name="02 POST /openapi/v1/gw/multi-agent/sse",
    )

    assert result["candidates"]
    for candidate in result["candidates"]:
        assert candidate["timing"] == {
            "scope": "request",
            "start": "request_started",
            "source_request_id": "step_sse_chat",
            "source_request_name": "02 POST /openapi/v1/gw/multi-agent/sse",
        }


def test_generation_allows_empty_result_when_sample_only_contains_heartbeat() -> None:
    events = [_captured(1, 100, "heartbeat"), _captured(2, 200, "heartbeat")]

    result = generate_sse_metric_candidate(events, max_stream_seconds=60, ai_suggester=lambda _: {"candidates": []})

    assert result["candidates"] == []
    assert result["result_status"] == "empty"
    assert result["analysis"]["ai_status"] == "used"
    assert result["messages"] == ["本次样本未发现高可信度性能指标，可从事件目录中手动选择。"]


def test_ai_cannot_promote_role_fact_to_business_metric() -> None:
    def suggester(payload):
        role_fact = next(fact for fact in payload["facts"] if fact["path"] == "$.data.role")
        return {
            "candidates": [
                {
                    "fact_id": role_fact["fact_id"],
                    "name": "助手开始时间",
                    "category": "milestone_start",
                    "confidence": 0.99,
                    "reason": "角色为助手",
                }
            ]
        }

    result = generate_sse_metric_candidate(_sample_events(), max_stream_seconds=60, ai_suggester=suggester)

    assert all(candidate["match"]["path"] != "$.data.role" for candidate in result["candidates"])
    assert result["analysis"]["ai_status"] == "not_used"


def test_ai_cannot_promote_role_fact_to_end_rule() -> None:
    def suggester(payload):
        role_fact = next(fact for fact in payload["facts"] if fact["path"] == "$.data.role")
        return {"candidates": [], "end_rule_candidate_fact_id": role_fact["fact_id"]}

    result = generate_sse_metric_candidate(_sample_events(), max_stream_seconds=60, ai_suggester=suggester)

    assert result["end_rule_candidate"] is None


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
        return {"candidates": []}

    generate_sse_metric_candidate(events, max_stream_seconds=60, ai_suggester=suggester)

    serialized = json.dumps(captured_input, ensure_ascii=False)
    assert "secret-dialog" not in serialized
    assert "secret-trace" not in serialized
    assert "敏感回答正文" not in serialized
    assert captured_input["task"] == "discover_performance_metric_candidates"
    answer_fact = next(fact for fact in captured_input["facts"] if fact["normalized_value"] == "answer")
    assert answer_fact["path"] == "$.data.event_type"
    assert answer_fact["has_non_empty_content"] is True


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


def test_capture_enforces_total_stream_duration() -> None:
    class FakeResponse:
        def iter_lines(self, decode_unicode: bool = False):
            return iter(['data: {"data":{"event_type":"answer"}}', ""])

    with pytest.raises(ValueError, match="sse_stream_timeout"):
        capture_sse_events(
            FakeResponse(),
            started_at=100.0,
            clock=lambda: 102.0,
            max_stream_seconds=1,
        )


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
    scenario_payload = PerformanceSseMetricGenerateIn(
        scenario_id="scenario-1",
        scenario_step_id="step-stream",
        api_environment_id="environment-1",
    )
    assert scenario_payload.scenario_step_id == "step-stream"


def test_scenario_probe_consumes_formal_scenario_execution_result() -> None:
    result = _scenario_execution_probe(
        {
            "status": "passed",
            "scenario_result": {
                "status": "passed",
                "steps": [
                    {
                        "step_id": "stream",
                        "name": "流式回答",
                        "status": "passed",
                        "response": {
                            "status_code": 200,
                            "headers": {"Content-Type": "text/event-stream"},
                            "body": {
                                "streaming": True,
                                "truncated": False,
                                "events": [
                                    {
                                        "event": "message",
                                        "data": {"data": {"event_type": "call_llm_start"}},
                                        "received_offset_ms": 341,
                                    },
                                    {
                                        "event": "message",
                                        "data": {"data": {"event_type": "answer", "answer": "ok"}},
                                        "received_offset_ms": 2999,
                                    },
                                ],
                            },
                        },
                    }
                ],
            },
        },
        "stream",
    )

    assert result["status_code"] == 200
    assert [event.received_offset_ms for event in result["events"]] == [341, 2999]
    assert json.loads(result["events"][1].event.data_text)["data"]["answer"] == "ok"


def test_scenario_probe_surfaces_formal_step_failure_evidence() -> None:
    with pytest.raises(ValueError, match="invalid parameter"):
        _scenario_execution_probe(
            {
                "status": "failed",
                "error_message": "pytest failed",
                "scenario_result": {
                    "status": "failed",
                    "steps": [
                        {
                            "step_id": "prepare",
                            "name": "准备会话",
                            "status": "failed",
                            "error": "未提取到必填变量",
                            "response": {"body": {"code": "400000", "message": "invalid parameter"}},
                        }
                    ],
                },
            },
            "stream",
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
