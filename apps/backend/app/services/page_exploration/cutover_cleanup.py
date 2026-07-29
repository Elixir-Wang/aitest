from __future__ import annotations

import shutil
from pathlib import Path


_LEGACY_TARGETS = (
    "pages",
    "runs",
    "page_edges.yaml",
    "operations.yaml",
    "operations.yaml.lock",
    "subgoals.yaml",
    "exploration-coverage.yaml",
)


def clear_legacy_exploration_artifacts(root: Path, project_id: str) -> dict:
    storage_root = Path(root).resolve()
    project_root = (storage_root / project_id).resolve()
    _require_within(project_root, storage_root)
    exploration_root = (project_root / "page_exploration").resolve()
    _require_within(exploration_root, project_root)

    deleted: list[str] = []
    missing = 0
    for name in _LEGACY_TARGETS:
        target = (exploration_root / name).resolve()
        _require_within(target, exploration_root)
        if not target.exists():
            missing += 1
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        deleted.append(name)
    return {"deleted": deleted, "missing": missing}


def _require_within(path: Path, parent: Path) -> None:
    try:
        path.relative_to(parent)
    except ValueError as exc:
        raise ValueError(f"清理路径越界: {path}") from exc


__all__ = ["clear_legacy_exploration_artifacts"]
