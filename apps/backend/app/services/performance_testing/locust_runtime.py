from __future__ import annotations


def runtime_locustfile_source() -> str:
    return '''import json
import time
from datetime import datetime, timezone
from pathlib import Path

import gevent
from locust import events
from generated_locustfile import *


RUNTIME = json.loads(Path(__file__).with_name("runtime.json").read_text(encoding="utf-8"))
PLAN["request"]["headers"] = {
    **dict(RUNTIME["environment"].get("headers") or {}),
    **dict(PLAN["request"].get("headers") or {}),
}
PerformanceUser.host = RUNTIME["environment"]["api_base_url"]

EVENT_LOG = Path(__file__).with_name("locust-events.jsonl")
CONTROL_FILE = Path(__file__).with_name("locust-control.json")


def _append_event(payload):
    with EVENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }, ensure_ascii=False) + "\\n")


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
