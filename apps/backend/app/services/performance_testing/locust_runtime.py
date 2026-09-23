def standalone_runtime_support_source(*, enable_sse: bool = True) -> str:
    """Return platform hooks appended to every self-contained locustfile."""
    return '''
import os
from datetime import datetime, timezone
from pathlib import Path

import gevent
from locust.exception import StopTest


RUNTIME_PATH = Path(os.environ.get("PERFORMANCE_RUNTIME_FILE", Path(__file__).with_name("runtime.json")))
RUNTIME = json.loads(RUNTIME_PATH.read_text(encoding="utf-8")) if RUNTIME_PATH.is_file() else {"environment": {}}
RUNTIME_ENVIRONMENT = dict(RUNTIME.get("environment") or {})


def _resolve_environment_placeholders(value):
    if isinstance(value, dict):
        for key in list(value):
            value[key] = _resolve_environment_placeholders(value[key])
        return value
    if isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = _resolve_environment_placeholders(item)
        return value
    if isinstance(value, str) and value.startswith("${ENV:") and value.endswith("}"):
        variable_name = value[6:-1]
        REQUIRED_ENVIRONMENT_VARIABLES.add(variable_name)
        return os.environ.get(variable_name, value)
    return value


REQUIRED_ENVIRONMENT_VARIABLES = set()
PLAN = _resolve_environment_placeholders(PLAN)
if PLAN.get("target_type") == "scenario" and RUNTIME_ENVIRONMENT:
    scenario_variables = PLAN.setdefault("scenario_variables", {})
    scenario_variables.update(dict(RUNTIME_ENVIRONMENT.get("variables") or {}))
    scenario_variables.update(dict(RUNTIME_ENVIRONMENT.get("headers") or {}))
    for step in PLAN.get("steps") or []:
        request = step.get("request")
        if request is not None:
            request["headers"] = {
                **dict(request.get("headers") or {}),
                **dict(RUNTIME_ENVIRONMENT.get("headers") or {}),
            }
elif PLAN.get("target_type") == "endpoint" and RUNTIME_ENVIRONMENT:
    PLAN["request"]["headers"] = {
        **dict(PLAN["request"].get("headers") or {}),
        **dict(RUNTIME_ENVIRONMENT.get("headers") or {}),
    }
if RUNTIME_ENVIRONMENT.get("api_base_url"):
    PerformanceUser.host = str(RUNTIME_ENVIRONMENT["api_base_url"]).rstrip("/")


@events.test_start.add_listener
def _validate_standalone_environment(environment, **kwargs):
    if RUNTIME_ENVIRONMENT:
        return
    missing = sorted(name for name in REQUIRED_ENVIRONMENT_VARIABLES if not os.environ.get(name))
    if missing:
        raise StopTest("Missing required environment variables: " + ", ".join(missing))

EVENT_LOG = Path(__file__).with_name("locust-events.jsonl")
SSE_MEASUREMENTS = Path(__file__).with_name("sse-measurements.jsonl")
SSE_MEASUREMENT_META = Path(__file__).with_name("sse-measurements.meta.json")
SSE_MEASUREMENT_MAX_BYTES = 64 * 1024 * 1024
CONTROL_FILE = Path(__file__).with_name("locust-control.json")


def _append_event(payload):
    with EVENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }, ensure_ascii=False) + "\\n")


def _append_sse_measurement(payload):
    # Measurements intentionally contain only timings, IDs, and failure reasons.
    if SSE_MEASUREMENTS.exists() and SSE_MEASUREMENTS.stat().st_size >= SSE_MEASUREMENT_MAX_BYTES:
        SSE_MEASUREMENT_META.write_text(json.dumps({
            "schema_version": "v1",
            "truncated": True,
            "max_bytes": SSE_MEASUREMENT_MAX_BYTES,
        }), encoding="utf-8")
        return
    with SSE_MEASUREMENTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "schema_version": "v1",
            **payload,
        }, ensure_ascii=False, separators=(",", ":")) + "\\n")


__SSE_SINK_SETUP__


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
    except (TypeError, ValueError, RuntimeError):
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
                    SSE_MEASUREMENT_META.unlink(missing_ok=True)
                    last_command = command_id
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        gevent.sleep(0.25)


@events.init.add_listener
def _on_init(environment, runner, **kwargs):
    gevent.spawn(_control_loop, environment)


@events.request.add_listener
def _on_request(request_type, name, response_time, response_length, response=None, context=None, exception=None, **kwargs):
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


# Fixed load example:
# locust -f locustfile.py --headless -u 50 -r 5 -t 5m --host https://api.example.com --html report.html --csv results
# Staged load example (the shape controls users and spawn rate):
# locust -f locustfile.py --headless --host https://api.example.com --html report.html --csv results
'''.replace(
        "__SSE_SINK_SETUP__",
        "set_sse_measurement_sink(_append_sse_measurement)" if enable_sse else "",
    )


__all__ = ["standalone_runtime_support_source"]
