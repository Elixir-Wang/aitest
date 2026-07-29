from __future__ import annotations

import re
from copy import deepcopy
from urllib.parse import urlparse

from app.agents.page_exploration.utils.element_key import build_element_key
from app.agents.page_exploration.utils.page_id import make_page_id
from app.services.page_exploration.collection_groups import group_collection_items


def normalize_snapshot_artifact(snapshot: dict, existing: dict | None = None) -> dict:
    url = str(snapshot.get("url") or "").strip()
    normalized_path = urlparse(url).path or "/"
    page_id = make_page_id(normalized_path)
    page_key = page_id.removeprefix("page-") or "page"
    context = snapshot.get("state_context") if isinstance(snapshot.get("state_context"), dict) else {}
    state_id = str(context.get("state_id") or f"{page_key}.root").strip()
    state_type = str(context.get("state_type") or "root").strip()
    parent_state_id = str(context.get("parent_state_id") or "").strip()
    overlay = snapshot.get("overlay") if isinstance(snapshot.get("overlay"), dict) else None

    artifact = _base_artifact(existing, page_id, snapshot, normalized_path)
    object_key = page_key if state_type == "root" else _overlay_object_key(overlay, state_id)
    _upsert_object(artifact["objects"], object_key, state_type, snapshot, overlay, page_key)
    _upsert_state(artifact["states"], state_id, state_type, object_key, parent_state_id)

    observed_elements = snapshot.get("elements") if isinstance(snapshot.get("elements"), list) else []
    normalized_elements = _normalize_elements(
        observed_elements,
        object_key=object_key,
        state_id=state_id,
        overlay=overlay,
    )
    _merge_elements(artifact["elements"], normalized_elements)
    _merge_collections(artifact, snapshot.get("collections"))
    _add_transition(artifact, context, state_id)
    _finalize_quality(artifact)
    return _omit_empty_lists(artifact)


def _base_artifact(existing: dict | None, page_id: str, snapshot: dict, normalized_path: str) -> dict:
    if isinstance(existing, dict) and existing.get("schema_version") == "4.0":
        artifact = deepcopy(existing)
        artifact.setdefault("objects", [])
        artifact.setdefault("states", [])
        artifact.setdefault("elements", [])
        artifact.setdefault("quality", {"status": "complete", "unresolved": []})
        return artifact
    return {
        "schema_version": "4.0",
        "page": {
            "id": page_id,
            "title": str(snapshot.get("title") or normalized_path).strip(),
            "normalized_path": normalized_path,
        },
        "objects": [],
        "states": [],
        "elements": [],
        "quality": {"status": "complete", "unresolved": []},
    }


def _upsert_object(
    objects: list[dict],
    key: str,
    state_type: str,
    snapshot: dict,
    overlay: dict | None,
    page_key: str,
) -> None:
    entry = {
        "key": key,
        "type": "page" if state_type == "root" else state_type,
        "name": str((overlay or {}).get("name") or snapshot.get("title") or key).strip(),
    }
    if state_type != "root":
        entry["parent"] = page_key
        locator = _structured_locator((overlay or {}).get("primary_selector"))
        if locator:
            entry["container_locator"] = locator
    _upsert_by_key(objects, entry)


def _upsert_state(
    states: list[dict],
    state_id: str,
    state_type: str,
    object_key: str,
    parent_state_id: str,
) -> None:
    entry = {"id": state_id, "type": state_type, "object": object_key}
    if parent_state_id:
        entry["parent"] = parent_state_id
    _upsert_by_id(states, entry)


def _normalize_elements(
    elements: list,
    *,
    object_key: str,
    state_id: str,
    overlay: dict | None,
) -> list[dict]:
    result: list[dict] = []
    overlay_id = str((overlay or {}).get("id") or "").strip()
    for raw in elements:
        if not isinstance(raw, dict):
            continue
        if overlay is not None and str(raw.get("overlay_id") or "").strip() != overlay_id:
            continue
        role = str(raw.get("role") or "element").strip()
        name = str(raw.get("name") or raw.get("text") or "").strip()
        locator = _structured_locator(raw.get("primary_selector"))
        if not locator:
            locator = _structured_locator(raw.get("fallback_selector"))
        if not name or not locator:
            continue
        key = build_element_key({"role": role, "name": name})
        action = _normalize_action(role, str(raw.get("action_type") or ""))
        entry = {
            "key": key,
            "object": object_key,
            "states": [state_id],
            "role": role,
            "name": name,
            "actions": [action],
            "locator": locator,
        }
        fallback = _structured_locator(raw.get("fallback_selector"))
        if fallback and fallback != locator:
            entry["fallback_locator"] = fallback
        result.append(entry)
    return result


def _structured_locator(selector) -> dict | None:
    if not _is_verified_selector(selector):
        return None
    code = str(selector.get("code") or "").strip().removeprefix("page.")
    role_matches = re.findall(
        r"getByRole\(['\"]([^'\"]+)['\"],\s*\{[^}]*name:\s*['\"]([^'\"]+)['\"]",
        code,
    )
    if role_matches:
        role, name = role_matches[-1]
        return {
            "strategy": "role",
            "role": role,
            "name": name,
            "exact": not bool(re.search(r"exact:\s*false", code)),
        }
    for method, strategy in (
        ("getByLabel", "label"),
        ("getByPlaceholder", "placeholder"),
        ("getByTestId", "test_id"),
        ("getByText", "text"),
    ):
        match = re.search(rf"{method}\(['\"]([^'\"]+)['\"]", code)
        if match:
            locator = {"strategy": strategy, "value": match.group(1)}
            if strategy == "text":
                locator["exact"] = not bool(re.search(r"exact:\s*false", code))
            return locator
    css_match = re.search(r"locator\(['\"]([^'\"]+)['\"]\)", code)
    if css_match:
        value = css_match.group(1)
        return {
            "strategy": "xpath" if value.startswith(("//", "xpath=")) else "css",
            "value": value,
        }
    return None


def _is_verified_selector(selector) -> bool:
    if not isinstance(selector, dict) or not selector.get("code"):
        return False
    verification = selector.get("verification")
    return bool(
        isinstance(verification, dict)
        and verification.get("checked") is True
        and verification.get("unique") is True
        and verification.get("visible") is True
    )


def _normalize_action(role: str, action: str) -> str:
    value = action.strip().lower()
    if value:
        return value
    if role in {"textbox", "searchbox", "combobox", "spinbutton"}:
        return "fill"
    if role in {"button", "link", "checkbox", "radio", "tab", "menuitem", "option"}:
        return "click"
    return "assert_visible"


def _merge_elements(existing: list[dict], observed: list[dict]) -> None:
    for entry in observed:
        current = next((item for item in existing if item.get("key") == entry["key"]), None)
        if current is None:
            existing.append(entry)
            continue
        states = current.setdefault("states", [])
        for state_id in entry["states"]:
            if state_id not in states:
                states.append(state_id)
        actions = current.setdefault("actions", [])
        for action in entry["actions"]:
            if action not in actions:
                actions.append(action)
        current.update({key: value for key, value in entry.items() if key not in {"states", "actions"}})


def _merge_collections(artifact: dict, value) -> None:
    if not isinstance(value, list):
        return
    collections = artifact.setdefault("collections", [])
    for raw in value:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("key") or "").strip()
        items = raw.get("items") if isinstance(raw.get("items"), list) else []
        if not key or not items:
            continue
        entry = {
            "key": key,
            "item_element": str(raw.get("item_element") or "").strip(),
            "group_by": ["type", "status"],
            "groups": group_collection_items(items),
        }
        _upsert_by_key(collections, entry)


def _add_transition(artifact: dict, context: dict, state_id: str) -> None:
    trigger = context.get("triggered_by") if isinstance(context.get("triggered_by"), dict) else None
    if not trigger:
        return
    target = str(trigger.get("element_key") or "").strip()
    if not any(element.get("key") == target for element in artifact["elements"]):
        _add_unresolved(
            artifact,
            {
                "id": f"{state_id}:trigger",
                "type": "missing_trigger_element",
                "reason": target,
            },
        )
        return
    action = str(trigger.get("action") or "click").strip()
    transition = {
        "id": f"{trigger.get('from_state')}--{action}--{target}",
        "from_state": str(trigger.get("from_state") or "").strip(),
        "action": action,
        "target": target,
        "to_state": state_id,
        "url_changed": bool(trigger.get("url_changed")),
    }
    transitions = artifact.setdefault("transitions", [])
    _upsert_by_id(transitions, transition)


def _add_unresolved(artifact: dict, entry: dict) -> None:
    quality = artifact.setdefault("quality", {"status": "complete", "unresolved": []})
    unresolved = quality.setdefault("unresolved", [])
    _upsert_by_id(unresolved, entry)


def _finalize_quality(artifact: dict) -> None:
    quality = artifact.setdefault("quality", {})
    unresolved = quality.get("unresolved") if isinstance(quality.get("unresolved"), list) else []
    quality["status"] = "partial" if unresolved else "complete"
    if unresolved:
        quality["unresolved"] = unresolved
    else:
        quality.pop("unresolved", None)


def _overlay_object_key(overlay: dict | None, state_id: str) -> str:
    value = str((overlay or {}).get("id") or "").strip()
    if value:
        return value.replace("-", "_")
    return state_id.replace(".", "_")


def _upsert_by_key(items: list[dict], entry: dict) -> None:
    current = next((item for item in items if item.get("key") == entry.get("key")), None)
    if current is None:
        items.append(entry)
    else:
        current.clear()
        current.update(entry)


def _upsert_by_id(items: list[dict], entry: dict) -> None:
    current = next((item for item in items if item.get("id") == entry.get("id")), None)
    if current is None:
        items.append(entry)
    else:
        current.clear()
        current.update(entry)


def _omit_empty_lists(value: dict) -> dict:
    return {
        key: item
        for key, item in value.items()
        if not (isinstance(item, list) and not item)
    }


__all__ = ["normalize_snapshot_artifact"]
