from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


EVENT_SCHEMA_VERSION = "ui-run-events/v1"
DETAIL_SCHEMA_VERSION = "ui-run-detail/v1"
MAX_EVENT_LINE_BYTES = 256 * 1024
MAX_TEXT_LENGTH = 4000
SENSITIVE_KEY_RE = re.compile(r"(?i)(password|passwd|secret|token|cookie|authorization|api[_-]?key)")
SENSITIVE_VALUE_RE = re.compile(
    r"(?i)(authorization:\s*bearer\s+|token=|password=|cookie:\s*)([^\s]+)"
)

_write_lock = threading.Lock()
_sequence = 0
_sequence_path = ""


def write_event(event_type: str, **payload: Any) -> dict[str, Any] | None:
    path_value = os.getenv("UI_RUN_EVENT_PATH", "").strip()
    if not path_value:
        return None
    path = Path(path_value)
    run_id = os.getenv("UI_RUN_ID", "").strip()
    with _write_lock:
        sequence = _next_sequence(path_value)
        event = redact_payload(
            {
                "schema_version": EVENT_SCHEMA_VERSION,
                "sequence": sequence,
                "type": event_type,
                "run_id": run_id,
                "timestamp": datetime.now(UTC).isoformat(),
                **payload,
            }
        )
        encoded = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        if len(encoded) > MAX_EVENT_LINE_BYTES:
            event = {
                **event,
                "payload_truncated": True,
                "error": {"type": "EventTooLarge", "message": "事件内容超过大小限制。"},
            }
            encoded = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as stream:
            stream.write(encoded)
            stream.flush()
        return event


def read_events(path: Path, *, after: int = 0, limit: int | None = None) -> tuple[list[dict], bool]:
    if not path.exists():
        return [], False
    events: list[dict] = []
    incomplete = False
    with path.open("rb") as stream:
        for raw_line in stream:
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                incomplete = True
                continue
            if int(event.get("sequence", 0)) <= after:
                continue
            events.append(event)
            if limit is not None and len(events) >= limit:
                break
    return events, incomplete


def reduce_events(
    events: Iterable[dict],
    *,
    run_id: str = "",
    run_status: str = "",
    incomplete: bool = False,
) -> dict[str, Any]:
    iterations: dict[str, dict[str, Any]] = {}
    ordered_ids: list[str] = []
    last_sequence = 0
    for event in events:
        last_sequence = max(last_sequence, int(event.get("sequence", 0)))
        iteration_id = str(event.get("iteration_id", ""))
        if not iteration_id:
            continue
        iteration = iterations.get(iteration_id)
        if iteration is None:
            iteration = {
                "iteration_id": iteration_id,
                "pytest_node_id": str(event.get("pytest_node_id", "")),
                "index": int(event.get("index", len(ordered_ids))),
                "parameters": dict(event.get("parameters") or {}),
                "attempt": 1,
                "status": "pending",
                "started_at": None,
                "finished_at": None,
                "duration_ms": None,
                "current_step_id": "",
                "failed_step_id": "",
                "error": None,
                "steps": [],
            }
            iterations[iteration_id] = iteration
            ordered_ids.append(iteration_id)
        event_type = event.get("type")
        if event_type == "iteration_collected":
            iteration["pytest_node_id"] = str(event.get("pytest_node_id", ""))
            iteration["index"] = int(event.get("index", iteration["index"]))
            iteration["parameters"] = dict(event.get("parameters") or {})
        elif event_type == "iteration_started":
            iteration["status"] = "running"
            iteration["started_at"] = event.get("timestamp")
        elif event_type == "steps_defined":
            for definition in event.get("steps") or []:
                step_id = str(definition.get("step_id", ""))
                if not step_id or _find_step(iteration, step_id) is not None:
                    continue
                iteration["steps"].append(
                    {
                        "step_id": step_id,
                        "title": str(definition.get("title", "")),
                        "visible": bool(definition.get("visible", True)),
                        "operation_ids": list(definition.get("operation_ids") or []),
                        "status": "pending",
                        "started_at": None,
                        "finished_at": None,
                        "duration_ms": None,
                        "error": None,
                        "artifacts": [],
                    }
                )
        elif event_type == "step_started":
            step = _find_step(iteration, str(event.get("step_id", "")))
            if step is None:
                step = {
                    "step_id": str(event.get("step_id", "")),
                    "title": str(event.get("title", "")),
                    "visible": bool(event.get("visible", True)),
                    "operation_ids": list(event.get("operation_ids") or []),
                    "status": "running",
                    "started_at": event.get("timestamp"),
                    "finished_at": None,
                    "duration_ms": None,
                    "error": None,
                    "artifacts": [],
                }
                iteration["steps"].append(step)
            else:
                step["status"] = "running"
                step["started_at"] = event.get("timestamp")
            iteration["current_step_id"] = step["step_id"]
        elif event_type == "step_finished":
            step = _find_step(iteration, str(event.get("step_id", "")))
            if step is None:
                step = {
                    "step_id": str(event.get("step_id", "")),
                    "title": str(event.get("title", "")),
                    "visible": bool(event.get("visible", True)),
                    "operation_ids": list(event.get("operation_ids") or []),
                    "started_at": None,
                    "artifacts": [],
                }
                iteration["steps"].append(step)
            step.update(
                status=str(event.get("status", "failed")),
                finished_at=event.get("timestamp"),
                duration_ms=event.get("duration_ms"),
                error=event.get("error"),
                artifacts=list(event.get("artifacts") or []),
            )
            iteration["current_step_id"] = ""
            if step["status"] == "failed":
                iteration["failed_step_id"] = step["step_id"]
        elif event_type == "iteration_finished":
            iteration.update(
                status=str(event.get("status", "failed")),
                finished_at=event.get("timestamp"),
                duration_ms=event.get("duration_ms"),
                current_step_id="",
                error=event.get("error"),
            )

    terminal_status = _iteration_terminal_status(run_status)
    for iteration in iterations.values():
        if iteration["status"] in {"pending", "running"} and terminal_status:
            iteration["status"] = terminal_status
        for step in iteration["steps"]:
            if step.get("status") == "running" and terminal_status:
                step["status"] = "cancelled" if terminal_status == "cancelled" else "failed"
                if step["status"] == "failed" and not iteration["failed_step_id"]:
                    iteration["failed_step_id"] = step["step_id"]
            elif step.get("status") == "pending" and iteration["status"] in {
                "failed",
                "infrastructure_error",
                "skipped",
            }:
                step["status"] = "skipped"
            elif step.get("status") == "pending" and iteration["status"] == "cancelled":
                step["status"] = "cancelled"

    ordered = sorted((iterations[item_id] for item_id in ordered_ids), key=lambda item: item["index"])
    counts = {
        status: sum(1 for item in ordered if item["status"] == status)
        for status in ("pending", "running", "passed", "failed", "skipped", "cancelled", "infrastructure_error")
    }
    return {
        "schema_version": DETAIL_SCHEMA_VERSION,
        "detail_available": bool(ordered),
        "run_id": run_id,
        "run_status": run_status,
        "incomplete": bool(incomplete),
        "last_sequence": last_sequence,
        "summary": {"total": len(ordered), **counts},
        "iterations": ordered,
    }


def build_detail(events_path: Path, *, run_id: str, run_status: str) -> dict[str, Any]:
    events, incomplete = read_events(events_path)
    return reduce_events(events, run_id=run_id, run_status=run_status, incomplete=incomplete)


def write_detail(path: Path, detail: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def redact_payload(value: Any, *, key: str = "") -> Any:
    if SENSITIVE_KEY_RE.search(key):
        return "***"
    if isinstance(value, dict):
        return {str(item_key): redact_payload(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        redacted = SENSITIVE_VALUE_RE.sub(lambda match: f"{match.group(1)}***", value)
        return redacted[:MAX_TEXT_LENGTH]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:MAX_TEXT_LENGTH]


def safe_parameters(params: dict[str, Any]) -> dict[str, Any]:
    return {str(key): redact_payload(value, key=str(key)) for key, value in params.items()}


def _next_sequence(path_value: str) -> int:
    global _sequence, _sequence_path
    if _sequence_path != path_value:
        _sequence_path = path_value
        _sequence = 0
    _sequence += 1
    return _sequence


def _find_step(iteration: dict[str, Any], step_id: str) -> dict[str, Any] | None:
    return next((step for step in iteration["steps"] if step["step_id"] == step_id), None)


def _iteration_terminal_status(run_status: str) -> str:
    if run_status == "cancelled":
        return "cancelled"
    if run_status == "failed":
        return "failed"
    return ""


__all__ = [
    "DETAIL_SCHEMA_VERSION",
    "EVENT_SCHEMA_VERSION",
    "build_detail",
    "read_events",
    "redact_payload",
    "reduce_events",
    "safe_parameters",
    "write_detail",
    "write_event",
]
