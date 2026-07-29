from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import yaml

from app.services.page_exploration.locking import FileLock


SCHEMA_VERSION = "1.0"


def load_coverage(root: Path, project_id: str) -> dict:
    path = _coverage_path(root, project_id)
    if not path.is_file():
        return _empty_coverage()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return _empty_coverage()
    if not isinstance(payload, dict):
        return _empty_coverage()
    pages = payload.get("pages") if isinstance(payload.get("pages"), dict) else {}
    return {"schema_version": SCHEMA_VERSION, "pages": pages}


def is_page_complete(coverage: dict, page_id: str) -> bool:
    return _page_entry(coverage, page_id).get("status") == "complete"


def is_state_completed(coverage: dict, page_id: str, state_id: str) -> bool:
    states = _page_entry(coverage, page_id).get("states")
    entry = states.get(state_id, {}) if isinstance(states, dict) else {}
    return isinstance(entry, dict) and entry.get("status") == "completed"


def is_action_completed(
    coverage: dict,
    page_id: str,
    element_key: str,
    action: str,
) -> bool:
    actions = _page_entry(coverage, page_id).get("actions")
    key = _action_key(element_key, action)
    entry = actions.get(key, {}) if isinstance(actions, dict) else {}
    return isinstance(entry, dict) and entry.get("status") == "completed"


def is_collection_group_completed(
    coverage: dict,
    page_id: str,
    collection_key: str,
    group_key: str,
) -> bool:
    collections = _page_entry(coverage, page_id).get("collections")
    collection = collections.get(collection_key, {}) if isinstance(collections, dict) else {}
    groups = collection.get("groups") if isinstance(collection, dict) else {}
    entry = groups.get(group_key, {}) if isinstance(groups, dict) else {}
    return isinstance(entry, dict) and entry.get("status") == "completed"


def build_autonomous_coverage_summary(coverage: dict) -> dict:
    summary = {
        "completed_pages": [],
        "completed_states": [],
        "completed_actions": [],
        "completed_collection_groups": [],
        "pending_collection_groups": [],
    }
    pages = coverage.get("pages") if isinstance(coverage.get("pages"), dict) else {}
    for page_id in sorted(pages):
        page = pages[page_id]
        if not isinstance(page, dict):
            continue
        if page.get("status") == "complete":
            summary["completed_pages"].append(page_id)
        states = page.get("states") if isinstance(page.get("states"), dict) else {}
        summary["completed_states"].extend(
            state_id
            for state_id, entry in sorted(states.items())
            if isinstance(entry, dict) and entry.get("status") == "completed"
        )
        actions = page.get("actions") if isinstance(page.get("actions"), dict) else {}
        summary["completed_actions"].extend(
            action_key
            for action_key, entry in sorted(actions.items())
            if isinstance(entry, dict) and entry.get("status") == "completed"
        )
        collections = page.get("collections") if isinstance(page.get("collections"), dict) else {}
        for collection_key, collection in sorted(collections.items()):
            groups = collection.get("groups") if isinstance(collection, dict) else {}
            for group_key, entry in sorted(groups.items()):
                if not isinstance(entry, dict):
                    continue
                item = _collection_group_summary(collection_key, group_key)
                target = (
                    summary["completed_collection_groups"]
                    if entry.get("status") == "completed"
                    else summary["pending_collection_groups"]
                )
                target.append(item)
    return summary


def build_coverage_view(coverage: dict, *, checkpoint: dict | None = None) -> dict:
    pages_source = coverage.get("pages") if isinstance(coverage.get("pages"), dict) else {}
    checkpoint = checkpoint if isinstance(checkpoint, dict) else {}
    visited_states = checkpoint.get("visited_states") if isinstance(checkpoint.get("visited_states"), dict) else {}
    frontier = checkpoint.get("frontier") if isinstance(checkpoint.get("frontier"), list) else []
    page_ids = set(pages_source)
    page_ids.update(
        str(entry.get("page_key") or "").strip()
        for entry in visited_states.values()
        if isinstance(entry, dict) and str(entry.get("page_key") or "").strip()
    )
    page_ids.update(
        str(item.get("page_key") or "").strip()
        for item in frontier
        if isinstance(item, dict) and str(item.get("page_key") or "").strip()
    )

    pages: list[dict] = []
    action_counts = {"completed": 0, "pending": 0, "blocked": 0, "failed": 0}
    discovered_states: set[str] = set()
    completed_states: set[str] = set()
    next_action = None
    current_state_key = str(checkpoint.get("current_state_key") or "").strip()

    for page_id in sorted(page_ids):
        durable_page = pages_source.get(page_id, {})
        durable_page = durable_page if isinstance(durable_page, dict) else {}
        state_entries = durable_page.get("states") if isinstance(durable_page.get("states"), dict) else {}
        states: dict[str, str] = {
            str(state_id): "completed" if isinstance(entry, dict) and entry.get("status") == "completed" else "pending"
            for state_id, entry in state_entries.items()
        }
        for state_id, entry in visited_states.items():
            if not isinstance(entry, dict) or str(entry.get("page_key") or "") != page_id:
                continue
            states.setdefault(str(state_id), "pending")
        discovered_states.update(states)
        completed_states.update(state_id for state_id, status in states.items() if status == "completed")

        actions: list[dict] = []
        seen_actions: set[tuple[str, str]] = set()
        for item in frontier:
            if not isinstance(item, dict) or str(item.get("page_key") or "") != page_id:
                continue
            element_key = str(item.get("element_key") or "").strip()
            action_type = str(item.get("action_type") or "").strip()
            if not element_key or not action_type:
                continue
            status = _coverage_action_status(str(item.get("status") or "pending"))
            action = {
                "element_key": element_key,
                "action_type": action_type,
                "state_key": str(item.get("state_key") or ""),
                "status": status,
            }
            actions.append(action)
            seen_actions.add((element_key, action_type))
            action_counts[status] += 1
            if next_action is None and status == "pending":
                next_action = {
                    "element_key": element_key,
                    "action_type": action_type,
                    "state_key": action["state_key"],
                    "page_id": page_id,
                }

        durable_actions = durable_page.get("actions") if isinstance(durable_page.get("actions"), dict) else {}
        for action_key, entry in durable_actions.items():
            element_key, separator, action_type = str(action_key).rpartition(":")
            if not separator or (element_key, action_type) in seen_actions:
                continue
            status = "completed" if isinstance(entry, dict) and entry.get("status") == "completed" else "pending"
            actions.append(
                {
                    "element_key": element_key,
                    "action_type": action_type,
                    "state_key": str(entry.get("from_state") or "") if isinstance(entry, dict) else "",
                    "status": status,
                }
            )
            action_counts[status] += 1

        path = str(durable_page.get("path") or "").strip()
        if not path:
            state_url = next(
                (
                    str(entry.get("url") or "")
                    for entry in visited_states.values()
                    if isinstance(entry, dict) and str(entry.get("page_key") or "") == page_id
                ),
                "",
            )
            path = urlparse(state_url).path or "/"
        pages.append(
            {
                "page_id": page_id,
                "path": path,
                "status": "completed" if durable_page.get("status") == "complete" else "partial",
                "states": [{"state_key": key, "status": value} for key, value in sorted(states.items())],
                "actions": actions,
            }
        )

    current_page_id = str(visited_states.get(current_state_key, {}).get("page_key") or "") if current_state_key else ""
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "pages_discovered": len(pages),
            "pages_completed": sum(page["status"] == "completed" for page in pages),
            "states_discovered": len(discovered_states),
            "states_completed": len(completed_states),
            "actions_discovered": sum(action_counts.values()),
            "actions_completed": action_counts["completed"],
            "actions_pending": action_counts["pending"],
            "actions_blocked": action_counts["blocked"],
            "actions_failed": action_counts["failed"],
        },
        "resume": {
            "available": next_action is not None,
            "run_id": str(checkpoint.get("run_id") or ""),
            "state_key": current_state_key,
            "page_id": current_page_id,
            "next_action": next_action,
        },
        "pages": pages,
    }


def _coverage_action_status(status: str) -> str:
    return {
        "verified": "completed",
        "executing": "pending",
        "blocked": "blocked",
        "failed": "failed",
    }.get(status, "pending")


def coverage_updates_from_artifacts(root: Path, project_id: str) -> dict:
    updates = {
        "pages": [],
        "completed_actions": [],
        "collection_groups": [],
    }
    pages_dir = Path(root) / project_id / "page_exploration" / "pages"
    if not pages_dir.is_dir():
        return updates

    for artifact_path in sorted(pages_dir.glob("*.yaml")):
        artifact = _read_schema_4_artifact(artifact_path)
        if artifact is None:
            continue
        page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
        page_id = str(page.get("id") or "").strip()
        if not page_id:
            continue
        states = [
            str(state.get("id") or "").strip()
            for state in artifact.get("states") or []
            if isinstance(state, dict) and str(state.get("id") or "").strip()
        ]
        quality = artifact.get("quality") if isinstance(artifact.get("quality"), dict) else {}
        unresolved = quality.get("unresolved") if isinstance(quality.get("unresolved"), list) else []
        page_status = "complete" if quality.get("status") == "complete" and not unresolved else "partial"
        updates["pages"].append(
            {
                "page_id": page_id,
                "path": str(page.get("normalized_path") or "").strip(),
                "artifact": f"pages/{artifact_path.name}",
                "status": page_status,
                "states": states,
            }
        )

        if not unresolved:
            for transition in artifact.get("transitions") or []:
                if not isinstance(transition, dict):
                    continue
                target = str(transition.get("target") or "").strip()
                action = str(transition.get("action") or "").strip()
                if not target or not action:
                    continue
                action_update = {
                    "page_id": page_id,
                    "element_key": target,
                    "action": action,
                }
                _copy_nonempty(action_update, transition, "from_state", "to_state")
                updates["completed_actions"].append(action_update)

        for collection in artifact.get("collections") or []:
            if not isinstance(collection, dict):
                continue
            collection_key = str(collection.get("key") or "").strip()
            if not collection_key:
                continue
            for group in collection.get("groups") or []:
                if not isinstance(group, dict):
                    continue
                group_key = str(group.get("key") or "").strip()
                if not group_key:
                    continue
                group_update = {
                    "page_id": page_id,
                    "collection_key": collection_key,
                    "group_key": group_key,
                    "status": "pending",
                }
                _copy_nonempty(group_update, group, "representative")
                updates["collection_groups"].append(group_update)
    return updates


def update_coverage(
    root: Path,
    project_id: str,
    *,
    run_id: str,
    mode: str,
    pages: list[dict],
    completed_actions: list[dict],
    collection_groups: list[dict],
) -> dict:
    path = _coverage_path(root, project_id)
    with FileLock(path):
        coverage = load_coverage(root, project_id)
        entries = coverage["pages"]
        for page_update in pages:
            page_id = str(page_update.get("page_id") or "").strip()
            if not page_id:
                continue
            page = entries.setdefault(page_id, {})
            _copy_nonempty(page, page_update, "path", "artifact")
            page["status"] = "complete" if page_update.get("status") == "complete" else "partial"
            states = page.setdefault("states", {})
            for state_id in page_update.get("states") or []:
                state_key = str(state_id or "").strip()
                if state_key:
                    states[state_key] = _completed_entry(run_id, mode)

        for action_update in completed_actions:
            page_id = str(action_update.get("page_id") or "").strip()
            element_key = str(action_update.get("element_key") or "").strip()
            action = str(action_update.get("action") or "").strip()
            if not page_id or not element_key or not action:
                continue
            page = entries.setdefault(page_id, {"status": "partial"})
            actions = page.setdefault("actions", {})
            entry = _completed_entry(run_id, mode)
            _copy_nonempty(entry, action_update, "from_state", "to_state")
            actions[_action_key(element_key, action)] = entry

        for group_update in collection_groups:
            page_id = str(group_update.get("page_id") or "").strip()
            collection_key = str(group_update.get("collection_key") or "").strip()
            group_key = str(group_update.get("group_key") or "").strip()
            if not page_id or not collection_key or not group_key:
                continue
            page = entries.setdefault(page_id, {"status": "partial"})
            collections = page.setdefault("collections", {})
            groups = collections.setdefault(collection_key, {}).setdefault("groups", {})
            existing = groups.get(group_key)
            requested_status = (
                "completed" if group_update.get("status") == "completed" else "pending"
            )
            if (
                isinstance(existing, dict)
                and existing.get("status") == "completed"
                and requested_status == "pending"
            ):
                continue
            entry = {"status": requested_status}
            representative = str(group_update.get("representative") or "").strip()
            if representative:
                entry["representative"] = representative
            if requested_status == "completed":
                entry.update({"run_id": run_id, "mode": mode})
            groups[group_key] = entry

        _write_coverage(path, coverage)
        return coverage


def clear_page_coverage(root: Path, project_id: str, page_id: str) -> None:
    path = _coverage_path(root, project_id)
    with FileLock(path):
        coverage = load_coverage(root, project_id)
        coverage["pages"].pop(page_id, None)
        _write_coverage(path, coverage)


def _coverage_path(root: Path, project_id: str) -> Path:
    return Path(root) / project_id / "page_exploration" / "exploration-coverage.yaml"


def _empty_coverage() -> dict:
    return {"schema_version": SCHEMA_VERSION, "pages": {}}


def _page_entry(coverage: dict, page_id: str) -> dict:
    pages = coverage.get("pages") if isinstance(coverage.get("pages"), dict) else {}
    entry = pages.get(page_id, {})
    return entry if isinstance(entry, dict) else {}


def _action_key(element_key: str, action: str) -> str:
    return f"{element_key.strip()}:{action.strip()}"


def _completed_entry(run_id: str, mode: str) -> dict:
    return {"status": "completed", "run_id": run_id, "mode": mode}


def _copy_nonempty(target: dict, source: dict, *keys: str) -> None:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            target[key] = value


def _collection_group_summary(collection_key: str, group_key: str) -> dict:
    parts = group_key.split(":")
    return {
        "collection": collection_key,
        "type": parts[0] if parts else "",
        "status": parts[1] if len(parts) > 1 else "",
    }


def _write_coverage(path: Path, coverage: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        yaml.safe_dump(coverage, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def _read_schema_4_artifact(path: Path) -> dict | None:
    try:
        artifact = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(artifact, dict) or str(artifact.get("schema_version")) != "4.0":
        return None
    return artifact


__all__ = [
    "build_autonomous_coverage_summary",
    "clear_page_coverage",
    "coverage_updates_from_artifacts",
    "is_action_completed",
    "is_collection_group_completed",
    "is_page_complete",
    "is_state_completed",
    "load_coverage",
    "update_coverage",
]
