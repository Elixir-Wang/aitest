from __future__ import annotations


def runtime_locustfile_source() -> str:
    return '''import json
import time
from datetime import datetime, timezone
from pathlib import Path

import gevent
from locust import events
import generated_locustfile as generated
from generated_locustfile import *


RUNTIME = json.loads(Path(__file__).with_name("runtime.json").read_text(encoding="utf-8"))
PLAN["request"]["headers"] = {
    **dict(PLAN["request"].get("headers") or {}),
    **dict(RUNTIME["environment"].get("headers") or {}),
}
PerformanceUser.host = str(RUNTIME["environment"]["api_base_url"]).rstrip("/")

EVENT_LOG = Path(__file__).with_name("locust-events.jsonl")
SSE_MEASUREMENTS = Path(__file__).with_name("sse-measurements.jsonl")
CONTROL_FILE = Path(__file__).with_name("locust-control.json")


def _append_event(payload):
    with EVENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }, ensure_ascii=False) + "\\n")


def _append_sse_measurement(payload):
    # Measurements intentionally contain only timings, IDs, and failure reasons.
    with SSE_MEASUREMENTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\\n")


generated.SSE_MEASUREMENT_SINK = _append_sse_measurement


def _redact_response_value(value, key=""):
    normalized = str(key).lower().replace("-", "_")
    if any(marker in normalized for marker in ("password", "secret", "token", "api_key", "credential")):
        return "***"
    if normalized == "key" or normalized.endswith("_key") or normalized == "authorization":
        return "***"
    if isinstance(value, dict):
        return {str(item_key): _redact_response_value(item, item_key) for item_key, item in value.items()}
    if isinstance(value, list):
        return [_redact_response_value(item) for item in value[:20]]
    if isinstance(value, str):
        return value[:1000]
    return value


def _response_excerpt(response):
    if response is None:
        return ""
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return ""
    if isinstance(payload, dict):
        payload = {key: payload[key] for key in ("code", "message", "type", "error", "detail") if key in payload}
    return json.dumps(_redact_response_value(payload), ensure_ascii=False)[:2000]


def _trace_headers(response):
    if response is None:
        return {}
    return {
        key: response.headers[key]
        for key in ("log-id", "x-trace-id", "traceparent")
        if response.headers.get(key)
    }


def _control_loop(environment):
    last_command = ""
    while True:
        try:
            if CONTROL_FILE.exists():
                command = json.loads(CONTROL_FILE.read_text(encoding="utf-8"))
                command_id = str(command.get("id") or "")
                if command_id and command_id != last_command and command.get("action") == "reset_stats":
                    if environment.runner is not None:
                        environment.runner.stats.reset_all()
                        environment.runner.exceptions = {}
                    SSE_MEASUREMENTS.write_text("", encoding="utf-8")
                    last_command = command_id
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        gevent.sleep(0.25)


@events.init.add_listener
def _on_init(environment, runner, **kwargs):
    gevent.spawn(_control_loop, environment)


@events.request.add_listener
def _on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    if exception or (response is not None and response.status_code >= 400):
        _append_event({
            "kind": "failure",
            "request_type": request_type or "",
            "name": name or "",
            "response_time": response_time,
            "status_code": getattr(response, "status_code", None),
            "reason": str(exception or getattr(response, "reason", "HTTP failure"))[:1000],
            "response_excerpt": _response_excerpt(response),
            "response_headers": _trace_headers(response),
        })


@events.user_error.add_listener
def _on_user_error(user_instance, exception, tb, **kwargs):
    _append_event({
        "kind": "exception",
        "name": "",
        "exception_type": type(exception).__name__,
        "message": str(exception)[:2000],
    })
'''
