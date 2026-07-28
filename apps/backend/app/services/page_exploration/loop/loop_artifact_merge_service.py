"""Deterministic merge for Loop exploration deltas."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
import shutil

import yaml


MERGE_COLLECTIONS = ("regions", "elements", "states", "interactions", "blockers")


def capture_loop_baseline(*, root: Path, run_id: str) -> Path:
    """Capture pages and page edges before a Loop run writes project artifacts."""
    baseline = root / "runs" / run_id / "baseline"
    baseline.mkdir(parents=True, exist_ok=True)
    pages_dir = root / "pages"
    if pages_dir.exists():
        for path in pages_dir.glob("*.yaml"):
            if path.name != "pages-index.yaml":
                shutil.copy2(path, baseline / path.name)
    edges = root / "page_edges.yaml"
    if edges.exists():
        shutil.copy2(edges, baseline / edges.name)
    return baseline


def merge_page_delta(base: dict[str, Any], delta: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    result = deepcopy(base)
    conflicts: list[dict[str, Any]] = []
    counts = {"added": 0, "updated": 0, "duplicate": 0}
    if not _same_page_identity(result, delta):
        return result, {"status": "conflict", **counts, "conflicts": [{"reason": "page_identity_mismatch"}]}
    for collection in MERGE_COLLECTIONS:
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
                conflicts.append({"collection": collection, "reason": "missing_stable_key"})
                continue
            existing = index.get(key)
            if existing is None:
                target.append(deepcopy(item))
                index[key] = target[-1]
                counts["added"] += 1
            elif existing == item:
                counts["duplicate"] += 1
            elif _compatible(existing, item):
                existing.update(deepcopy(item))
                counts["updated"] += 1
            else:
                conflicts.append({"collection": collection, "stable_key": key, "reason": "fact_conflict", "base": existing, "delta": item})
    return result, {"status": "conflict" if conflicts else "merged", **counts, "conflicts": conflicts}


def merge_loop_page_artifacts(*, pages_dir: Path, baseline_dir: Path, conflicts_dir: Path, run_id: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"status": "merged", "pages": [], "conflict_count": 0}
    if not pages_dir.exists():
        return summary
    for current_path in sorted(pages_dir.glob("*.yaml")):
        if current_path.name == "pages-index.yaml":
            continue
        baseline_path = baseline_dir / current_path.name
        if not baseline_path.exists():
            summary["pages"].append({"file": current_path.name, "status": "added", "added": 1})
            continue
        base = _read_yaml(baseline_path)
        delta = _read_yaml(current_path)
        merged, page_summary = merge_page_delta(base, {**delta, "run_id": run_id})
        if page_summary["status"] == "conflict":
            summary["status"] = "conflict"
            summary["conflict_count"] += len(page_summary["conflicts"])
            target = conflicts_dir / current_path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(yaml.safe_dump({"baseline": base, "delta": delta, "summary": page_summary}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        else:
            current_path.write_text(yaml.safe_dump(merged, allow_unicode=True, sort_keys=False), encoding="utf-8")
        summary["pages"].append({"file": current_path.name, **page_summary})
    _merge_edges(
        current_path=pages_dir.parent / "page_edges.yaml",
        baseline_path=baseline_dir / "page_edges.yaml",
        summary=summary,
    )
    return summary


def _merge_edges(*, current_path: Path, baseline_path: Path, summary: dict[str, Any]) -> None:
    if not current_path.exists() or not baseline_path.exists():
        return
    current = _read_yaml(current_path)
    baseline = _read_yaml(baseline_path)
    current_edges = current.get("edges") if isinstance(current.get("edges"), list) else []
    baseline_edges = baseline.get("edges") if isinstance(baseline.get("edges"), list) else []
    index = {str(edge.get("id")): edge for edge in baseline_edges if isinstance(edge, dict) and edge.get("id")}
    for edge in current_edges:
        if not isinstance(edge, dict) or not edge.get("id"):
            continue
        key = str(edge["id"])
        if key in index:
            index[key] = {**index[key], **edge}
            summary.setdefault("edge_updated", 0)
            summary["edge_updated"] += 1
        else:
            index[key] = edge
            summary.setdefault("edge_added", 0)
            summary["edge_added"] += 1
    current_path.write_text(yaml.safe_dump({"edges": list(index.values())}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _stable_key(item: dict[str, Any]) -> str:
    return str(item.get("stable_key") or item.get("id") or item.get("element_id") or item.get("state_signature") or "").strip()


def _same_page_identity(base: dict[str, Any], delta: dict[str, Any]) -> bool:
    left = base.get("page") if isinstance(base.get("page"), dict) else base
    right = delta.get("page") if isinstance(delta.get("page"), dict) else delta
    left_key = left.get("identity_key") or left.get("page_id") or left.get("canonical_path")
    right_key = right.get("identity_key") or right.get("page_id") or right.get("canonical_path")
    return not left_key or not right_key or left_key == right_key


def _compatible(base: dict[str, Any], delta: dict[str, Any]) -> bool:
    return all(not base.get(key) or not delta.get(key) or base[key] == delta[key] for key in ("page_id", "region_id", "state_signature", "role"))


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}
