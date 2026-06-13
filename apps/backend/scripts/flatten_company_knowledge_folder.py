"""Hoist a nested company knowledge folder's children to the vault root."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db import connect
from app.core.storage import global_knowledge_folder_dir, resolve_stored_path, store_path
from app.repositories import global_knowledge_repo

BASE_ID = "gkb-e59ec77300ea783d"
FLATTEN_FOLDER_NAME = "产品手册"


def _move_vault_file_paths(base_id: str, file_row, target_folder_id: str) -> tuple[str, str]:
    target_dir = global_knowledge_folder_dir(base_id, target_folder_id)
    target_raw_dir = target_dir / "raw"
    target_markdown_dir = target_dir / "markdown"
    target_raw_dir.mkdir(parents=True, exist_ok=True)
    target_markdown_dir.mkdir(parents=True, exist_ok=True)

    raw_source = resolve_stored_path(file_row["raw_path"])
    markdown_source = resolve_stored_path(file_row["markdown_path"])
    if raw_source is None or not raw_source.exists():
        raise FileNotFoundError(f"Missing raw file for {file_row['id']}: {file_row['raw_path']}")
    if markdown_source is None or not markdown_source.exists():
        raise FileNotFoundError(f"Missing markdown file for {file_row['id']}: {file_row['markdown_path']}")

    raw_target = target_raw_dir / raw_source.name
    markdown_target = target_markdown_dir / markdown_source.name
    if raw_target.exists() and raw_target.resolve() != raw_source.resolve():
        raise FileExistsError(f"Target raw file already exists: {raw_target}")
    if markdown_target.exists() and markdown_target.resolve() != markdown_source.resolve():
        raise FileExistsError(f"Target markdown file already exists: {markdown_target}")

    if raw_target.resolve() != raw_source.resolve():
        shutil.move(str(raw_source), str(raw_target))
    if markdown_target.resolve() != markdown_source.resolve():
        shutil.move(str(markdown_source), str(markdown_target))

    assets_dir = raw_source.parent.parent / "markdown" / f"{file_row['id']}_assets"
    target_assets_dir = target_markdown_dir / f"{file_row['id']}_assets"
    if assets_dir.is_dir() and assets_dir.resolve() != target_assets_dir.resolve():
        if target_assets_dir.exists():
            shutil.rmtree(target_assets_dir)
        shutil.move(str(assets_dir), str(target_assets_dir))

    return store_path(raw_target) or str(raw_target), store_path(markdown_target) or str(markdown_target)


def main() -> None:
    with connect() as db:
        base = global_knowledge_repo.find_base(db, BASE_ID)
        if not base:
            raise SystemExit(f"Knowledge base not found: {BASE_ID}")

        root_folder_id = base["root_folder_id"]
        folders = global_knowledge_repo.list_folders_by_base(db, BASE_ID)
        flatten_folder = next(
            (
                row
                for row in folders
                if row["name"] == FLATTEN_FOLDER_NAME and row["parent_id"] == root_folder_id
            ),
            None,
        )
        if flatten_folder is None:
            print(f"No '{FLATTEN_FOLDER_NAME}' folder under root; nothing to do.")
            return

        flatten_folder_id = flatten_folder["id"]
        child_folders = [row for row in folders if row["parent_id"] == flatten_folder_id]
        direct_files = global_knowledge_repo.list_files_by_folder(db, flatten_folder_id)

        print(
            f"Flattening '{FLATTEN_FOLDER_NAME}' ({flatten_folder_id}) "
            f"into root '{base['name']}' ({root_folder_id})"
        )
        print(f"  child folders: {len(child_folders)}")
        print(f"  direct files: {len(direct_files)}")

        for child in child_folders:
            db.execute(
                "UPDATE global_knowledge_folders SET parent_id = ? WHERE id = ?",
                (root_folder_id, child["id"]),
            )
            print(f"  [folder] {child['name']} -> root")

        for file_row in direct_files:
            raw_path, markdown_path = _move_vault_file_paths(BASE_ID, file_row, root_folder_id)
            db.execute(
                """
                UPDATE global_knowledge_vault_files
                SET folder_id = ?, raw_path = ?, markdown_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (root_folder_id, raw_path, markdown_path, file_row["id"]),
            )
            print(f"  [file] {file_row['display_name']} -> root")

        db.execute("DELETE FROM global_knowledge_folders WHERE id = ?", (flatten_folder_id,))
        global_knowledge_repo.touch_base(db, BASE_ID)
        print(f"  [removed folder] {FLATTEN_FOLDER_NAME}")

    flatten_dir = global_knowledge_folder_dir(BASE_ID, flatten_folder_id)
    if flatten_dir.exists():
        shutil.rmtree(flatten_dir, ignore_errors=True)
        print(f"  [removed dir] {flatten_dir}")

    print("Done.")


if __name__ == "__main__":
    main()
