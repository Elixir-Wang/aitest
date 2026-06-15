"""Batch import local markdown files into a company knowledge base vault."""

from __future__ import annotations

import asyncio
import sys
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db import connect
from app.repositories import global_knowledge_repo
from app.services.knowledge import global_service

SOURCE_DIR = Path(r"D:\project\bairong_history_export\exported_docs\产品手册")
BASE_ID = "gkb-e59ec77300ea783d"
ACTOR = {
    "id": "u-admin",
    "role": "admin",
    "nickname": "管理员",
    "username": "admin",
    "project_scope": "全部项目",
}


def _upload(path: Path) -> UploadFile:
    content = path.read_bytes()
    return UploadFile(file=BytesIO(content), filename=path.name)


def _existing_folder_names(base_id: str, parent_id: str) -> dict[str, str]:
    with connect() as db:
        folders = global_knowledge_repo.list_folders_by_base(db, base_id)
    return {
        row["name"]: row["id"]
        for row in folders
        if row["parent_id"] == parent_id
    }


def _existing_file_names(base_id: str, folder_id: str) -> set[str]:
    with connect() as db:
        files = global_knowledge_repo.list_files_by_folder(db, folder_id)
    return {row["display_name"] for row in files}


def _ensure_folder(base_id: str, parent_id: str, name: str, cache: dict[tuple[str, str], str]) -> str:
    key = (parent_id, name)
    if key in cache:
        return cache[key]
    existing = _existing_folder_names(base_id, parent_id)
    if name in existing:
        folder_id = existing[name]
    else:
        folder = global_service.create_folder(base_id, parent_id=parent_id, name=name, actor=ACTOR)
        folder_id = folder["id"]
        print(f"  [folder] {name} -> {folder_id}")
    cache[key] = folder_id
    return folder_id


async def _upload_file(base_id: str, folder_id: str, file_path: Path) -> None:
    existing = _existing_file_names(base_id, folder_id)
    if file_path.name in existing:
        print(f"  [skip] {file_path.name} (already exists)")
        return
    await global_service.upload_files_to_folder(base_id, folder_id, [_upload(file_path)], ACTOR)
    print(f"  [file] {file_path.relative_to(SOURCE_DIR)}")


async def main() -> None:
    if not SOURCE_DIR.is_dir():
        raise SystemExit(f"Source directory not found: {SOURCE_DIR}")

    with connect() as db:
        base = global_knowledge_repo.find_base(db, BASE_ID)
        if not base:
            raise SystemExit(f"Knowledge base not found: {BASE_ID}")
        root_folder_id = base["root_folder_id"]

    folder_cache: dict[tuple[str, str], str] = {}
    import_root_id = root_folder_id

    md_files = sorted(SOURCE_DIR.rglob("*.md"))
    print(f"Importing {len(md_files)} markdown files into base '{base['name']}'")

    for file_path in md_files:
        rel_dir = file_path.parent.relative_to(SOURCE_DIR)
        parent_id = import_root_id
        if rel_dir.parts:
            for part in rel_dir.parts:
                parent_id = _ensure_folder(BASE_ID, parent_id, part, folder_cache)
        await _upload_file(BASE_ID, parent_id, file_path)

    tree = global_service.get_base_tree(BASE_ID, ACTOR)
    file_count = tree["base"]["file_count"]
    print(f"Done. Vault file count: {file_count}")


if __name__ == "__main__":
    asyncio.run(main())
