# apps/backend/app/services/page_exploration/run_detail.py

import json
import logging
import sys
from pathlib import Path
from typing import Any

from app.core import settings

logger = logging.getLogger(__name__)


def _service_attr(name: str, default):
    service_module = sys.modules.get("app.services.page_exploration.service")
    return getattr(service_module, name, default)


def _project_file_storage_root() -> Path:
    service_settings = _service_attr("settings", settings)
    return getattr(service_settings, "PROJECT_FILE_STORAGE_ROOT", settings.PROJECT_FILE_STORAGE_ROOT)


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_recent_timeline_events(run: dict) -> list[dict]:
    """Read all persisted UI timeline events for exploration detail restoration."""
    project_id = _string(run.get("project_id"))
    run_id = _string(run.get("id"))
    if not project_id or not run_id:
        return []
    events_path = (
        _project_file_storage_root()
        / project_id
        / "page_exploration"
        / "runs"
        / run_id
        / "timeline_events.jsonl"
    )
    if not events_path.exists():
        return []
    events: list[dict] = []
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("failed to read exploration timeline events: path=%s error=%s", events_path, exc)
        return []
    for line_number, line in enumerate(lines, start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning(
                "skipped invalid exploration timeline event: path=%s line=%s error=%s",
                events_path,
                line_number,
                exc,
            )
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _modules_from_db_pages(run: dict, pages: list[dict]) -> list[dict]:
    """Build frontend module progress from registered exploration_pages rows."""
    modules_by_key: dict[str, dict] = {}
    for page in pages:
        module_key = _string(page.get("module_key") or "main")
        module = modules_by_key.setdefault(
            module_key,
            _module_shell(
                run,
                {
                    "module_key": module_key,
                    "module_name": module_key,
                    "entry_path": run.get("scope", ""),
                    "planned_page_count": run.get("max_pages", 0),
                },
                len(modules_by_key),
            ),
        )
        module["pages"].append(_page_from_db_page(page))

    _refresh_module_counts(modules_by_key.values())
    return list(modules_by_key.values())


def _normalize_exploration_run_detail(run: dict) -> dict:
    """Use the linked environment as the display source for mutable environment fields."""
    environment_login_strategy = run.get("environment_login_strategy")
    if environment_login_strategy:
        run["login_strategy"] = environment_login_strategy
    return run


def _module_shell(run: dict, source: dict, index: int) -> dict:
    module_key = _string(source.get("module_key") or source.get("module_name") or f"module-{index + 1}")
    return {
        "id": module_key,
        "module_key": module_key,
        "module_name": _string(source.get("module_name") or module_key),
        "entry_path": _string(source.get("entry_path") or run.get("scope")),
        "planned_page_count": _int(source.get("planned_page_count")),
        "explored_page_count": _int(source.get("explored_page_count")),
        "blocked_page_count": _int(source.get("blocked_page_count")),
        "action_count": _int(source.get("action_count")),
        "field_count": _int(source.get("field_count")),
        "state_transition_count": _int(source.get("state_transition_count")),
        "completion_status": _string(source.get("completion_status") or source.get("status") or run.get("status") or "pending"),
        "completion_summary": _string(source.get("completion_summary") or source.get("summary") or run.get("result_summary")),
        "pages": [],
        "elements": [],
        "blockers": [],
    }


def _page_from_db_page(page: dict) -> dict:
    return {
        "id": _string(page.get("id")),
        "title": _string(page.get("title")),
        "url": _string(page.get("url")),
        "entry_path": _string(page.get("entry_path")),
        "yaml_path": _string(page.get("snapshot_path")),
        "status": _string(page.get("status") or "completed"),
        "blocker_reason": "",
        "recent_event": "",
        "structure_summary": _string(page.get("structure_summary")),
        "steps": [],
    }


def _refresh_module_counts(modules) -> None:
    for module in modules:
        page_count = len(module["pages"])
        if page_count:
            module["explored_page_count"] = max(module["explored_page_count"], page_count)
            module["planned_page_count"] = max(module["planned_page_count"], page_count)
