import json

from app.api.v1.performance_runs import format_run_sse_event


def test_format_run_sse_event_emits_json_payload() -> None:
    assert format_run_sse_event("stats", {"request_count": 10}) == (
        "event: stats\n"
        "data: " + json.dumps({"request_count": 10}, ensure_ascii=False, separators=(",", ":")) + "\n\n"
    )
