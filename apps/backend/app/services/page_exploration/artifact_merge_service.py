"""Deterministic merge of goal-exploration deltas into page artifacts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil
from typing import Any

import yaml


_MERGE_COLLECTIONS = ("regions", "elements", "states", "interactions", "blockers")


def merge_page_delta(base: dict[str, Any], delta: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge a verified page delta while preserving unrelated baseline facts."""
    result = deepcopy(base)
    conflicts: list[dict[str, Any]] = []
    added = 0
    updated = 0
    duplicate = 0

    if not _same_page_identity(result, delta):
        return result, {"status": "conflict", "added": 0, "updated": 0, "duplicate": 0, "conflicts": [{"reason": "page_identity_mismatch"}]}

    for collection in _MERGE_COLLECTIONS:
        target = result.setdefault(collection, [])
        incoming = delta.get(collection) or []
        if not isinstance(target, list) or not isinstance(incoming, list):
            conflicts.append({"collection": collection, "reason": "collection_not_list"})
            continue
        index = {_stable_key(item): item for item in target if isinstance(item, dict) and _stable_key(item)}
        for item in incoming:
            if not isinstance(item, dict):
                conflicts.append({"collection": collection, "reason": "invalid_item"})
                continue
            key = _stable_key(item)
            if not key:
                conflicts.append({"collection": collection, "reason": "missing_stable_key", "item": item})
                continue
            existing = index.get(key)
            if existing is None:
                target.append(deepcopy(item))
                index[key] = target[-1]
                added += 1
            elif _compatible(existing, item):
                if existing == item:
                    duplicate += 1
                else:
                    existing.update(deepcopy(item))
                    updated += 1
            else:
                conflicts.append({"collection": collection, "stable_key": key, "reason": "fact_conflict", "base": existing, "delta": item})

    history = result.setdefault("merge_history", [])
    history.append({"delta_run_id": delta.get("run_id", ""), "added": added, "updated": updated, "duplicate": duplicate, "conflict_count": len(conflicts)})
    status = "conflict" if conflicts else "merged"
    return result, {"status": status, "added": added, "updated": updated, "duplicate": duplicate, "conflicts": conflicts}


def capture_page_baseline(project_root: Path, project_id: str, run_id: str) -> Path:
    """Capture existing page artifacts before a goal run can update them."""
    pages_dir = project_root / project_id / "page_exploration" / "pages"
    baseline_dir = project_root / project_id / "page_exploration" / "runs" / run_id / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    if pages_dir.exists():
        for source in pages_dir.glob("*.yaml"):
            if source.name == "pages-index.yaml":
                continue
            shutil.copy2(source, baseline_dir / source.name)
    return baseline_dir


def merge_goal_run_artifacts(project_root: Path, project_id: str, run_id: str) -> dict[str, Any]:
    """Merge current run page snapshots against the pre-run baseline."""
    root = project_root / project_id / "page_exploration"
    baseline_dir = root / "runs" / run_id / "baseline"
    pages_dir = root / "pages"
    summary: dict[str, Any] = {"status": "merged", "pages": [], "conflict_count": 0}
    if not baseline_dir.exists() or not pages_dir.exists():
        return summary

    for current_path in pages_dir.glob("*.yaml"):
        if current_path.name == "pages-index.yaml":
            continue
        baseline_path = baseline_dir / current_path.name
        if not baseline_path.exists():
            continue
        base = _read_yaml(baseline_path)
        delta = _read_yaml(current_path)
        merged, page_summary = merge_page_delta(base, {**delta, "run_id": run_id})
        if page_summary["status"] == "conflict":
            summary["status"] = "conflict"
            summary["conflict_count"] += len(page_summary["conflicts"])
            conflict_path = root / "runs" / run_id / "conflicts" / current_path.name
            conflict_path.parent.mkdir(parents=True, exist_ok=True)
            _write_yaml(conflict_path, {"baseline": base, "delta": delta, "summary": page_summary})
        else:
            _write_yaml(current_path, merged)
        summary["pages"].append({"file": current_path.name, **page_summary})
    return summary


def _same_page_identity(base: dict[str, Any], delta: dict[str, Any]) -> bool:
    base_page = base.get("page") if isinstance(base.get("page"), dict) else base
    delta_page = delta.get("page") if isinstance(delta.get("page"), dict) else delta
    base_key = base_page.get("identity_key") or base_page.get("page_id") or base_page.get("canonical_path")
    delta_key = delta_page.get("identity_key") or delta_page.get("page_id") or delta_page.get("canonical_path")
    return not base_key or not delta_key or base_key == delta_key


def _stable_key(item: dict[str, Any]) -> str:
    return str(item.get("stable_key") or item.get("id") or item.get("element_id") or item.get("state_signature") or "").strip()


def _compatible(base: dict[str, Any], delta: dict[str, Any]) -> bool:
    for key in ("page_id", "region_id", "state_signature", "role"):
        if base.get(key) and delta.get(key) and base[key] != delta[key]:
            return False
    return True


def _read_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
