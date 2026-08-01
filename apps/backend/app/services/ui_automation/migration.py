from __future__ import annotations

import filecmp
import json
import re
import shutil
import sqlite3
from pathlib import Path

from app.agents.ui_automation.pytest_playwright.renderer import initialize_suite
from app.agents.ui_automation.pytest_playwright.suite import (
    legacy_shared_suite_path,
    project_suite_path,
)
from app.core import settings


def migrate_legacy_project_suite(db: sqlite3.Connection, project_id: str) -> dict:
    legacy_root = legacy_shared_suite_path().resolve()
    target_root = project_suite_path(project_id).resolve()
    report = {
        "project_id": project_id,
        "legacy_suite_path": str(legacy_root),
        "suite_path": str(target_root),
        "migrated": False,
        "copied_paths": [],
        "conflicting_paths": [],
        "run_ids": [],
    }
    if target_root == legacy_root or not legacy_root.is_dir():
        initialize_suite(target_root)
        return report

    generation_rows = db.execute(
        "SELECT suite_path FROM ui_automation_generation_runs WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    asset_rows = db.execute(
        "SELECT suite_path FROM ui_automation_assets WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    execution_rows = db.execute(
        "SELECT * FROM ui_automation_execution_runs WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    initialize_suite(target_root)
    project_key = _slugify(project_id)
    project_sources = (
        (legacy_root / "pages" / "generated" / project_key, target_root / "pages" / "generated" / project_key),
        (
            legacy_root / "testcases" / "generated" / project_key,
            target_root / "testcases" / "generated" / project_key,
        ),
        (
            legacy_root / "data" / "projects" / project_key,
            target_root / "data" / "projects" / project_key,
        ),
    )
    for source, target in project_sources:
        if source.is_dir():
            copied, conflicts = _copy_tree_missing(source, target)
            report["copied_paths"].extend(str(path) for path in copied)
            report["conflicting_paths"].extend(str(path) for path in conflicts)

    for row in execution_rows:
        report["run_ids"].append(row["id"])
        source_run = legacy_root / "runs" / row["id"]
        target_run = target_root / "runs" / row["id"]
        if source_run.is_dir():
            copied, conflicts = _copy_tree_missing(source_run, target_run)
            report["copied_paths"].extend(str(path) for path in copied)
            report["conflicting_paths"].extend(str(path) for path in conflicts)
        _update_execution_paths(db, row, legacy_root=legacy_root, target_root=target_root)

    stored_target = _store_path(target_root)
    db.execute(
        "UPDATE ui_automation_generation_runs SET suite_path = ? WHERE project_id = ? AND suite_path != ''",
        (stored_target, project_id),
    )
    db.execute(
        "UPDATE ui_automation_assets SET suite_path = ? WHERE project_id = ?",
        (stored_target, project_id),
    )
    had_legacy_database_paths = any(
        _path_is_within(row["suite_path"], legacy_root) for row in (*generation_rows, *asset_rows)
    ) or any(_path_is_within(row["run_dir"], legacy_root) for row in execution_rows)
    report["migrated"] = bool(report["copied_paths"] or had_legacy_database_paths)
    return report


def remove_migrated_legacy_project_files(project_id: str, run_ids: list[str]) -> list[str]:
    legacy_root = legacy_shared_suite_path().resolve()
    target_root = project_suite_path(project_id).resolve()
    project_key = _slugify(project_id)
    targets = [
        (
            legacy_root / "pages" / "generated" / project_key,
            target_root / "pages" / "generated" / project_key,
        ),
        (
            legacy_root / "testcases" / "generated" / project_key,
            target_root / "testcases" / "generated" / project_key,
        ),
        (
            legacy_root / "data" / "projects" / project_key,
            target_root / "data" / "projects" / project_key,
        ),
        *((legacy_root / "runs" / run_id, target_root / "runs" / run_id) for run_id in run_ids),
    ]
    removed = []
    for source, target in targets:
        if source.is_dir() and _tree_is_migrated(source, target):
            shutil.rmtree(source)
            removed.append(str(source))
    _remove_empty_directories(legacy_root)
    return removed


def _update_execution_paths(
    db: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    legacy_root: Path,
    target_root: Path,
) -> None:
    target_run = target_root / "runs" / row["id"]
    replacements = {
        "run_dir": _relocate_path(row["run_dir"], legacy_root, target_root, default=target_run),
        "stdout_path": _relocate_path(row["stdout_path"], legacy_root, target_root),
        "stderr_path": _relocate_path(row["stderr_path"], legacy_root, target_root),
        "screenshot_paths_json": _relocate_json(row["screenshot_paths_json"], legacy_root, target_root, []),
        "result_json": _relocate_json(row["result_json"], legacy_root, target_root, {}),
    }
    db.execute(
        """UPDATE ui_automation_execution_runs
           SET run_dir = ?, stdout_path = ?, stderr_path = ?,
               screenshot_paths_json = ?, result_json = ?
           WHERE id = ?""",
        (
            replacements["run_dir"],
            replacements["stdout_path"],
            replacements["stderr_path"],
            replacements["screenshot_paths_json"],
            replacements["result_json"],
            row["id"],
        ),
    )


def _relocate_json(value: str, legacy_root: Path, target_root: Path, default) -> str:
    try:
        payload = json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        payload = default
    relocated = _walk_json(payload, legacy_root, target_root)
    return json.dumps(relocated, ensure_ascii=False)


def _walk_json(value, legacy_root: Path, target_root: Path):
    if isinstance(value, dict):
        return {key: _walk_json(item, legacy_root, target_root) for key, item in value.items()}
    if isinstance(value, list):
        return [_walk_json(item, legacy_root, target_root) for item in value]
    if isinstance(value, str):
        return _relocate_path(value, legacy_root, target_root)
    return value


def _relocate_path(value: str, legacy_root: Path, target_root: Path, *, default: Path | None = None) -> str:
    if not value:
        return _store_path(default) if default is not None else ""
    path = _resolve_stored_path(value)
    try:
        relative = path.resolve().relative_to(legacy_root)
    except ValueError:
        return value
    return _store_path(target_root / relative)


def _resolve_stored_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else settings.PROJECT_FILE_STORAGE_ROOT / path


def _path_is_within(value: str, root: Path) -> bool:
    if not value:
        return False
    try:
        _resolve_stored_path(value).resolve().relative_to(root)
        return True
    except ValueError:
        return False


def _store_path(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(settings.PROJECT_FILE_STORAGE_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _copy_tree_missing(source: Path, target: Path) -> tuple[list[Path], list[Path]]:
    copied = []
    conflicts = []
    target.mkdir(parents=True, exist_ok=True)
    for source_path in sorted(source.rglob("*")):
        if _is_ignored(source_path, source):
            continue
        target_path = target / source_path.relative_to(source)
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
        elif source_path.is_file() and not target_path.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            copied.append(target_path)
        elif source_path.is_file() and (
            not target_path.is_file() or not filecmp.cmp(source_path, target_path, shallow=False)
        ):
            conflicts.append(target_path)
    return copied, conflicts


def _tree_is_migrated(source: Path, target: Path) -> bool:
    if not target.is_dir():
        return False
    for source_path in source.rglob("*"):
        if not source_path.is_file() or _is_ignored(source_path, source):
            continue
        target_path = target / source_path.relative_to(source)
        if not target_path.is_file() or not filecmp.cmp(source_path, target_path, shallow=False):
            return False
    return True


def _is_ignored(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return path.suffix == ".pyc" or any(part in {"__pycache__", ".pytest_cache"} for part in relative.parts)


def _remove_empty_directories(root: Path) -> None:
    if not root.is_dir():
        return
    for path in sorted((item for item in root.rglob("*") if item.is_dir()), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass
    try:
        root.rmdir()
    except OSError:
        pass


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    return re.sub(r"_+", "_", slug) or "generated_case"


__all__ = ["migrate_legacy_project_suite", "remove_migrated_legacy_project_files"]
