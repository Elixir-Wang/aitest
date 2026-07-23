from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from app.core import settings


IGNORED_NAMES = {".pytest_cache", "__pycache__", "report.json", "stdout.txt", "stderr.txt", "runtime"}


def _repair_root(project_id: str, session_id: str) -> Path:
    root = (
        settings.PROJECT_FILE_STORAGE_ROOT
        / project_id
        / "api_automation"
        / "repairs"
        / f"repair-{session_id}"
    ).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _copy_suite(source: Path, target: Path) -> Path:
    source = source.resolve()
    target = target.resolve()
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return target


def create_attempt_workspace(project_id: str, session_id: str, attempt_number: int, suite_path: Path) -> Path:
    target = _repair_root(project_id, session_id) / "attempts" / f"attempt-{attempt_number:04d}" / "workspace"
    return _copy_suite(suite_path, target)


def create_revision_snapshot(project_id: str, session_id: str, revision: int, suite_path: Path) -> Path:
    target = _repair_root(project_id, session_id) / "revisions" / f"rev-{revision:04d}"
    return _copy_suite(suite_path, target)


def build_manifest(root: Path) -> dict[str, dict[str, Any]]:
    root = root.resolve()
    manifest: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in IGNORED_NAMES for part in relative.parts) or not path.is_file():
            continue
        data = path.read_bytes()
        manifest[relative.as_posix()] = {
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    return manifest
