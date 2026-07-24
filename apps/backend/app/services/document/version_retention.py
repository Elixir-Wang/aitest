"""需求版本文件保留策略。"""
from __future__ import annotations

from pathlib import Path

from app.core.storage import resolve_stored_path
from app.repositories import document_repo

MAX_REQUIREMENT_VERSIONS = 5


def prune_document_versions(db, document_id: str) -> list[Path]:
    """删除超额的最老版本记录，并返回提交后需要删除的文件路径。"""
    versions = document_repo.find_versions_by_document(db, document_id)
    obsolete_versions = versions[MAX_REQUIREMENT_VERSIONS:]
    obsolete_paths: list[Path] = []
    for version in obsolete_versions:
        path = resolve_stored_path(version["file_path"]) or Path(version["file_path"])
        obsolete_paths.append(path)
        document_repo.delete_version(db, version["id"])
    return obsolete_paths


def delete_pruned_version_files(paths: list[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)
