# apps/backend/app/services/page_exploration/run_detail.py

import json
import sys
from pathlib import Path
from typing import Any

from app.core import settings


def _service_attr(name: str, default):
    service_module = sys.modules.get("app.services.page_exploration.service")
    return getattr(service_module, name, default)


def _project_file_storage_root() -> Path:
    service_settings = _service_attr("settings", settings)
    return getattr(service_settings, "PROJECT_FILE_STORAGE_ROOT", settings.PROJECT_FILE_STORAGE_ROOT)


def _data_dir() -> Path:
    service_settings = _service_attr("settings", settings)
    return getattr(service_settings, "DATA_DIR", settings.DATA_DIR)


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
    except OSError:
        return []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _modules_from_artifacts(run: dict) -> list[dict]:
    """Build frontend module progress from v2 artifact files when DB pages are empty."""
    artifact_root = _artifact_root_path(run)
    if not artifact_root:
        return []

    state = _read_json_file(artifact_root / "live" / "state.json")
    if state:
        modules = _modules_from_live_state(run, state)
        if modules:
            return modules

    progress = _read_json_file(artifact_root / "live" / "progress.json")
    if progress:
        modules = _modules_from_progress_json(run, progress)
        if modules:
            return modules

    summary = _read_yaml_file(artifact_root / "summary.yaml")
    page_artifacts = _read_page_artifacts(artifact_root / "pages")
    return _modules_from_summary_and_pages(run, summary, page_artifacts)


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


def _artifact_root_path(run: dict) -> Path | None:
    raw_root = str(run.get("artifact_root") or "").strip()
    if not raw_root:
        return None
    root = Path(raw_root)
    candidates = [root]
    if not root.is_absolute():
        candidates.extend([
            _project_file_storage_root() / raw_root,
            _data_dir() / "projects" / raw_root,
            _data_dir() / raw_root,
        ])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_yaml_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import yaml

        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (ImportError, OSError):
        return {}
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_page_artifacts(pages_dir: Path) -> list[dict]:
    if not pages_dir.exists():
        return []
    pages = []
    for path in sorted(pages_dir.glob("*.yaml")):
        artifact = _read_yaml_file(path)
        if artifact:
            artifact["_artifact_path"] = str(path)
            pages.append(artifact)
    return pages


def _modules_from_live_state(run: dict, state: dict) -> list[dict]:
    summary_modules = ((state.get("summary") or {}).get("modules") or [])
    pages = state.get("pages") or []
    if not isinstance(pages, list):
        pages = []

    modules_by_key = {
        _string(module.get("module_key") or module.get("module_name") or f"module-{index + 1}"): _module_shell(run, module, index)
        for index, module in enumerate(summary_modules)
        if isinstance(module, dict)
    }

    progress_pages = _progress_pages_from_state(state)
    for page in pages:
        if not isinstance(page, dict):
            continue
        frontend_page = _page_from_live_state(page)
        page_content = page.get("content") if isinstance(page.get("content"), dict) else {}
        page_info = page_content.get("page") if isinstance(page_content.get("page"), dict) else page
        module_key = _artifact_module_key(
            modules_by_key,
            _string(page.get("module_key") or page_info.get("module_key") or page_info.get("module") or frontend_page["title"] or "main"),
        )
        module = modules_by_key.setdefault(module_key, _module_shell(run, {"module_key": module_key, "module_name": module_key}, len(modules_by_key)))
        module["pages"].append(frontend_page)

    for module_key, pages_by_id in progress_pages.items():
        module = modules_by_key.setdefault(module_key, _module_shell(run, {"module_key": module_key, "module_name": module_key}, len(modules_by_key)))
        existing_ids = {page["id"] for page in module["pages"]}
        for page in pages_by_id.values():
            if page["id"] in existing_ids:
                continue
            module["pages"].append(page)

    _refresh_module_counts(modules_by_key.values())
    return list(modules_by_key.values())


def _modules_from_progress_json(run: dict, progress: dict) -> list[dict]:
    modules = []
    raw_modules = progress.get("modules") or {}
    if not isinstance(raw_modules, dict):
        return []
    for index, (module_key, module_progress) in enumerate(raw_modules.items()):
        module = _module_shell(run, {"module_key": module_key, "module_name": module_key}, index)
        pages_by_id = ((module_progress or {}).get("pages") or {}) if isinstance(module_progress, dict) else {}
        if isinstance(pages_by_id, dict):
            module["pages"] = [_normalize_progress_page(page_id, page) for page_id, page in pages_by_id.items() if isinstance(page, dict)]
        modules.append(module)
    _refresh_module_counts(modules)
    return modules


def _modules_from_summary_and_pages(run: dict, summary: dict, page_artifacts: list[dict]) -> list[dict]:
    summary_modules = summary.get("modules") or []
    modules_by_key = {
        _string(module.get("module_key") or module.get("module_name") or f"module-{index + 1}"): _module_shell(run, module, index)
        for index, module in enumerate(summary_modules)
        if isinstance(module, dict)
    }

    for page_artifact in page_artifacts:
        page_info = page_artifact.get("page") or {}
        if not isinstance(page_info, dict):
            continue
        module_key = _string(page_info.get("module") or page_info.get("module_key") or "main")
        module = modules_by_key.setdefault(module_key, _module_shell(run, {"module_key": module_key, "module_name": module_key}, len(modules_by_key)))
        module["pages"].append(_page_from_page_artifact(page_artifact))

    _refresh_module_counts(modules_by_key.values())
    return list(modules_by_key.values())


def _progress_pages_from_state(state: dict) -> dict[str, dict[str, dict]]:
    modules = (state.get("live_progress") or state.get("progress") or {}).get("modules") if isinstance(state.get("live_progress") or state.get("progress"), dict) else None
    if not modules:
        modules = state.get("modules")
    if not isinstance(modules, dict):
        return {}
    result: dict[str, dict[str, dict]] = {}
    for module_key, module_progress in modules.items():
        pages = module_progress.get("pages") if isinstance(module_progress, dict) else None
        if not isinstance(pages, dict):
            continue
        result[_string(module_key)] = {
            _string(page_id): _normalize_progress_page(_string(page_id), page)
            for page_id, page in pages.items()
            if isinstance(page, dict)
        }
    return result


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


def _page_from_live_state(page: dict) -> dict:
    content = page.get("content") if isinstance(page.get("content"), dict) else {}
    page_info = content.get("page") if isinstance(content.get("page"), dict) else page
    return {
        "id": _string(page_info.get("id") or page.get("id") or page.get("page_id")),
        "title": _string(page_info.get("semantic_title") or page_info.get("title") or page.get("title") or page_info.get("id") or "探索页面"),
        "url": _string(page_info.get("url") or page.get("page_url") or page.get("url")),
        "entry_path": _string(page_info.get("entry_path") or page_info.get("normalized_url") or page_info.get("normalized_path")),
        "yaml_path": _string(page.get("file_path") or page_info.get("yaml_path") or page.get("yaml_path") or page.get("_artifact_path")),
        "status": _string(page_info.get("status") or page.get("status") or "completed"),
        "blocker_reason": _string(page_info.get("blocker_reason") or page.get("blocker_reason")),
        "recent_event": _string(page_info.get("recent_event") or page.get("recent_event")),
        "structure_summary": _string(page_info.get("structure_summary") or page.get("structure_summary")),
        "steps": _normalize_steps(content.get("steps") or page.get("steps")),
    }


def _page_from_page_artifact(artifact: dict) -> dict:
    page = artifact.get("page") or {}
    actions = artifact.get("actions")
    return {
        "id": _string(page.get("id") or "page"),
        "title": _string(page.get("semantic_title") or page.get("title") or page.get("id") or "探索页面"),
        "url": _string(page.get("url")),
        "entry_path": _string(page.get("normalized_url") or page.get("normalized_path")),
        "yaml_path": _string(artifact.get("_artifact_path")),
        "status": _string(page.get("status") or "completed"),
        "blocker_reason": "",
        "recent_event": "",
        "structure_summary": _string(page.get("structure_summary")),
        "steps": _steps_from_actions(actions),
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


def _normalize_progress_page(page_id: str, page: dict) -> dict:
    return {
        "id": _string(page.get("id") or page_id),
        "title": _string(page.get("title") or page_id),
        "url": _string(page.get("url")),
        "entry_path": _string(page.get("entry_path")),
        "yaml_path": _string(page.get("yaml_path")),
        "status": _string(page.get("status") or "running"),
        "blocker_reason": _string(page.get("blocker_reason")),
        "recent_event": _string(page.get("recent_event")),
        "structure_summary": _string(page.get("structure_summary")),
        "steps": _normalize_steps(page.get("steps")),
    }


def _steps_from_actions(actions: Any) -> list[dict]:
    if not isinstance(actions, list):
        return []
    steps = []
    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            continue
        steps.append({
            "id": _string(action.get("id") or f"action-{index:03d}"),
            "type": _string(action.get("type") or "action"),
            "title": _string(action.get("target") or action.get("title") or action.get("type") or "探索动作"),
            "detail": _string(action.get("result") or action.get("detail")),
            "status": _string(action.get("status") or "completed"),
            "occurred_at": action.get("occurred_at"),
            "artifact_path": _string(action.get("artifact_path")),
            "source": _string(action.get("source")),
        })
    return steps


def _normalize_steps(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    steps = []
    for index, step in enumerate(value, start=1):
        if not isinstance(step, dict):
            continue
        steps.append({
            "id": _string(step.get("id") or step.get("step_id") or f"step-{index:03d}"),
            "type": _string(step.get("type") or step.get("action_type") or "event"),
            "title": _string(step.get("title") or step.get("description") or "探索步骤"),
            "detail": _string(step.get("detail") or step.get("message") or step.get("expected_result")),
            "status": _string(step.get("status") or "pending"),
            "occurred_at": step.get("occurred_at") or step.get("completed_at") or step.get("started_at"),
            "artifact_path": _string(step.get("artifact_path")),
            "source": _string(step.get("source")),
        })
    return steps


def _refresh_module_counts(modules) -> None:
    for module in modules:
        page_count = len(module["pages"])
        if page_count:
            module["explored_page_count"] = max(module["explored_page_count"], page_count)
            module["planned_page_count"] = max(module["planned_page_count"], page_count)


def _artifact_module_key(modules_by_key: dict[str, dict], raw_key: str) -> str:
    if raw_key in modules_by_key:
        return raw_key
    if len(modules_by_key) == 1:
        return next(iter(modules_by_key))
    return raw_key
