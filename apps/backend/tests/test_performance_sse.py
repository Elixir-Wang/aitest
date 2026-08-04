from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.performance_testing.script_generation.planner import build_default_plan
from app.schemas.performance_test import PerformanceRequestConfig
from app.schemas.performance_test import PerformanceGoal, PerformanceTestCreateIn
from app.services.performance_testing.headless_worker import summarize_sse_measurements
from app.services.performance_testing.script_renderer import render_locust_script
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
    assert 'quality = {"parse_error_count": 0}' in source


def test_sse_measurement_summary_keeps_missing_and_percentiles(tmp_path: Path) -> None:
    path = tmp_path / "sse-measurements.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"metrics":{"first_content":100,"first_tool_call":200},"missing_metric_ids":[],"failure_reason":""}',
                '{"metrics":{"first_content":300},"missing_metric_ids":["first_tool_call"],"failure_reason":""}',
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
