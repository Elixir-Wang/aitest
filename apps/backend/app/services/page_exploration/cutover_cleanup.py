from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


_LEGACY_FILES = {"operations.yaml", "operations.yaml.lock", "subgoals.yaml"}


def build_legacy_cleanup_manifest(root: Path, project_id: str | None = None) -> dict:
    storage_root = Path(root).resolve()
    projects = _project_roots(storage_root, project_id)
    manifest_projects = []
    for current_project_id, project_root in projects:
        exploration_root = project_root / "page_exploration"
        delete: list[dict] = []
        preserve: list[dict] = []
        warnings: list[str] = []
        if not exploration_root.is_dir():
            manifest_projects.append(
                {"project_id": current_project_id, "delete": [], "preserve": [], "warnings": []}
            )
            continue

        for name in sorted(_LEGACY_FILES):
            candidate = exploration_root / name
            if candidate.exists():
                delete.append(_entry(storage_root, candidate, "legacy_file"))

        replay_runs = exploration_root / "replay-runs"
        if replay_runs.exists():
            delete.append(_entry(storage_root, replay_runs, "legacy_directory"))

        pages_root = exploration_root / "pages"
        if pages_root.is_dir():
            for page_path in sorted(pages_root.glob("*.yaml")):
                artifact = _read_yaml(page_path)
                if str(artifact.get("schema_version")) in {"2.0", "3.0"}:
                    delete.append(_entry(storage_root, page_path, "legacy_schema_page"))
                elif str(artifact.get("schema_version")) == "4.0":
                    preserve.append(_entry(storage_root, page_path, "schema_4_page"))
                else:
                    warnings.append(f"未识别页面格式，保留不删: {page_path}")

        runs_root = exploration_root / "runs"
        if runs_root.is_dir():
            preserve.extend(
                _entry(storage_root, path, "run_evidence")
                for path in sorted(runs_root.rglob("*"))
                if path.is_file()
            )

        manifest_projects.append(
            {
                "project_id": current_project_id,
                "delete": delete,
                "preserve": preserve,
                "warnings": warnings,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "storage_root": str(storage_root),
        "projects": manifest_projects,
        "summary": {
            "projects": len(manifest_projects),
            "delete_files": sum(
                entry["kind"] != "legacy_directory"
                for project in manifest_projects
                for entry in project["delete"]
            ),
            "delete_directories": sum(
                entry["kind"] == "legacy_directory"
                for project in manifest_projects
                for entry in project["delete"]
            ),
            "preserve_files": sum(len(project["preserve"]) for project in manifest_projects),
            "warnings": sum(len(project["warnings"]) for project in manifest_projects),
        },
    }


def apply_legacy_cleanup_manifest(root: Path, manifest: dict) -> dict:
    storage_root = Path(root).resolve()
    if Path(str(manifest.get("storage_root", ""))).resolve() != storage_root:
        raise ValueError("manifest storage root mismatch")

    entries = [
        entry
        for project in manifest.get("projects", [])
        for entry in project.get("delete", [])
    ]
    for entry in entries:
        _resolve_manifest_path(storage_root, entry)

    deleted: list[str] = []
    skipped: list[str] = []
    for entry in entries:
        target = _resolve_manifest_path(storage_root, entry)
        relative = str(entry["path"])
        if not target.exists():
            skipped.append(relative)
            continue
        if _fingerprint(target) != entry.get("sha256"):
            raise ValueError(f"manifest fingerprint changed: {relative}")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        deleted.append(relative)
    return {"deleted": deleted, "skipped": skipped, "errors": []}


def _project_roots(storage_root: Path, project_id: str | None) -> list[tuple[str, Path]]:
    if project_id:
        project_root = (storage_root / project_id).resolve()
        _require_within(project_root, storage_root)
        return [(project_id, project_root)]
    if not storage_root.is_dir():
        return []
    return sorted(
        (path.name, path.resolve())
        for path in storage_root.iterdir()
        if path.is_dir()
    )


def _entry(storage_root: Path, path: Path, kind: str) -> dict:
    return {
        "path": path.resolve().relative_to(storage_root).as_posix(),
        "kind": kind,
        "size": _size(path),
        "sha256": _fingerprint(path),
    }


def _read_yaml(path: Path) -> dict:
    import yaml

    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(child.read_bytes())
    return digest.hexdigest()


def _resolve_manifest_path(storage_root: Path, entry: dict) -> Path:
    target = (storage_root / str(entry.get("path", ""))).resolve()
    _require_within(target, storage_root)
    return target


def _require_within(path: Path, parent: Path) -> None:
    try:
        path.relative_to(parent)
    except ValueError as exc:
        raise ValueError(f"path escapes storage root: {path}") from exc


__all__ = ["apply_legacy_cleanup_manifest", "build_legacy_cleanup_manifest"]
