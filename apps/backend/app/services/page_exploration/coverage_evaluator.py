"""Deterministic completion evaluation for autonomous page exploration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def evaluate_autonomous_coverage(project_root: Path, project_id: str, run_id: str) -> dict[str, Any]:
    """Compare discovered artifact elements with executed click/fill events."""
    root = project_root / project_id / "page_exploration"
    pages_dir = root / "pages"
    run_dir = root / "runs" / run_id
    discovered: set[str] = set()
    for path in pages_dir.glob("*.yaml") if pages_dir.exists() else []:
        if path.name == "pages-index.yaml":
            continue
        payload = _read_yaml(path)
        _collect_element_keys(payload, discovered)

    executed: set[str] = set()
    cleanup_actions = 0
    created_actions = 0
    for event in _read_jsonl(run_dir / "timeline_events.jsonl"):
        if event.get("type") != "agent_tool_completed":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        tool_name = str(payload.get("tool_name") or "")
        if tool_name in {"playwright_click_tool", "playwright_fill_tool"}:
            key = str(payload.get("element_key") or "").strip()
            if key:
                executed.add(key)
                lowered_key = key.lower()
                if any(token in lowered_key for token in ("delete", "删除", "remove", "清空")):
                    cleanup_actions += 1
                if any(token in lowered_key for token in ("create", "创建", "新增", "add")):
                    created_actions += 1

    pending = discovered - executed
    return {
        "discovered": len(discovered),
        "executed": len(executed & discovered),
        "pending": len(pending),
        "pending_keys": sorted(pending),
        "created_actions": created_actions,
        "cleanup_actions": cleanup_actions,
        "cleanup_pending": max(0, created_actions - cleanup_actions),
        "complete": bool(discovered) and not pending and cleanup_actions >= created_actions,
    }


def _collect_element_keys(payload: dict[str, Any], result: set[str]) -> None:
    for element in payload.get("elements", []) if isinstance(payload.get("elements"), list) else []:
        if isinstance(element, dict):
            key = str(element.get("key") or element.get("stable_key") or element.get("element_id") or "").strip()
            if key:
                result.add(key)
    for state in payload.get("states", []) if isinstance(payload.get("states"), list) else []:
        if isinstance(state, dict):
            _collect_element_keys(state, result)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records
