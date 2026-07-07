# apps/backend/app/services/page_exploration/event_log.py

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.core import settings
from app.services.page_exploration import event_bus
from app.services.page_exploration.event_payload import _compact_event_payload, _status_display


def _string(value) -> str:
    return "" if value is None else str(value)


def _project_file_storage_root() -> Path:
    service_module = sys.modules.get("app.services.page_exploration.service")
    service_settings = getattr(service_module, "settings", None)
    return getattr(service_settings, "PROJECT_FILE_STORAGE_ROOT", settings.PROJECT_FILE_STORAGE_ROOT)


def _publish_run_terminal_event(project_id: str, run_id: str, event_type: str, payload: dict) -> dict:
    result_summary = _compact_event_payload(payload.get("result_summary"))
    fallback_summary = {
        "run_completed": "探索任务已完成。",
        "run_failed": "探索任务失败。",
        "run_cancelled": "探索任务已停止。",
    }.get(event_type, "探索任务已结束。")
    display = _status_display("agent_run", _terminal_event_title(event_type), result_summary or fallback_summary)
    timeline_event = (
        _ExplorationEventLog(
            project_id=project_id,
            run_id=run_id,
            filename="timeline_events.jsonl",
        ).append(event_type, payload, display=display)
        if project_id
        else {}
    )
    try:
        event_bus.publish(
            run_id,
            event_type,
            payload,
            display=display,
            timeline_event_id=timeline_event.get("event_id"),
        )
    except TypeError:
        event_bus.publish(run_id, event_type, payload)
    return timeline_event


def _terminal_event_title(event_type: str) -> str:
    if event_type == "run_completed":
        return "探索完成"
    if event_type == "run_failed":
        return "探索失败"
    if event_type == "run_cancelled":
        return "探索停止"
    return "探索结束"


class _ExplorationEventLog:
    def __init__(self, *, project_id: str, run_id: str, filename: str) -> None:
        self.project_id = project_id
        self.run_id = run_id
        self.filename = filename
        self.path = self._resolve_path()
        self.sequence = self._last_sequence()

    def append(self, event_type: str, payload: dict, *, display: dict | None = None) -> dict:
        if self.path is None:
            return {}
        self.sequence += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "event_id": f"evt-{self.sequence:06d}",
            "run_id": self.run_id,
            "type": event_type,
            "payload": payload,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        if display:
            event["display"] = display
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def ensure_exists(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def _resolve_path(self) -> Path | None:
        if not self.project_id or not self.run_id:
            return None
        return (
            _project_file_storage_root()
            / self.project_id
            / "page_exploration"
            / "runs"
            / self.run_id
            / self.filename
        )

    def _last_sequence(self) -> int:
        if self.path is None or not self.path.exists():
            return 0
        last_sequence = 0
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                event_id = _string(event.get("event_id"))
                if event_id.startswith("evt-"):
                    last_sequence = max(last_sequence, int(event_id.removeprefix("evt-")))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return last_sequence
        return last_sequence
