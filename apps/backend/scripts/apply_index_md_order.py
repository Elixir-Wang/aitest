"""Apply company knowledge vault sort order from index.md TOC."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db import connect
from app.repositories import global_knowledge_repo
from app.seed.init_db import init_db
from app.services.knowledge import global_service

INDEX_PATH = Path(r"D:\project\bairong_history_export\exported_docs\产品手册\index.md")
BASE_ID = "gkb-df74f65ec2ab4935"
TRAILING_SORT_START = 1000

FOLDER_NAME_ALIASES = {
    "智能体能力扩展——资源库": "智能体能力扩展--资源库",
}

LINK_LINE = re.compile(r"^- \[(.+?)\]\((.+?)\)\s*$")


def _resolve_folder_name(name: str) -> str:
    return FOLDER_NAME_ALIASES.get(name, name)


def parse_index_md(content: str) -> list[dict]:
    root_children: list[dict] = []
    stack: list[tuple[int, dict]] = []

    for raw_line in content.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        depth = (len(raw_line) - len(raw_line.lstrip(" "))) // 2
        line = raw_line.strip()

        if line.startswith("- ["):
            match = LINK_LINE.match(line)
            if not match:
                continue
            path = match.group(2).replace("\\", "/")
            node = {"type": "file", "name": Path(path).name, "path": path, "children": []}
        elif line.startswith("- "):
            node = {"type": "folder", "name": line[2:].strip(), "path": None, "children": []}
        else:
            continue

        while stack and stack[-1][0] >= depth:
            stack.pop()

        if stack:
            stack[-1][1]["children"].append(node)
        else:
            root_children.append(node)

        if node["type"] == "folder":
            stack.append((depth, node))

    return root_children


def _apply_level(
    db,
    *,
    base_id: str,
    parent_id: str,
    nodes: list[dict],
    warnings: list[str],
    depth: int = 0,
) -> set[str]:
    matched: set[str] = set()
    prefix = "  " * depth
    for order, node in enumerate(nodes):
        if node["type"] == "folder":
            folder_name = _resolve_folder_name(node["name"])
            row = global_knowledge_repo.find_folder_by_parent_and_name(db, base_id, parent_id, folder_name)
            if row is None:
                warnings.append(f"folder not found: {folder_name} under parent {parent_id}")
                continue
            global_knowledge_repo.update_folder_sort_order(db, row["id"], order)
            matched.add(row["id"])
            print(f"{prefix}[{order}] folder {folder_name}")
            child_matched = _apply_level(
                db,
                base_id=base_id,
                parent_id=row["id"],
                nodes=node["children"],
                warnings=warnings,
                depth=depth + 1,
            )
            _finalize_level(db, base_id=base_id, parent_id=row["id"], matched=child_matched)
        else:
            row = global_knowledge_repo.find_vault_file_by_folder_and_name(db, parent_id, node["name"])
            if row is None:
                warnings.append(f"file not found: {node['name']} under parent {parent_id}")
                continue
            global_knowledge_repo.update_vault_file_sort_order(db, row["id"], order)
            matched.add(row["id"])
            print(f"{prefix}[{order}] file {node['name']}")
    return matched


def _finalize_level(db, *, base_id: str, parent_id: str, matched: set[str]) -> None:
    order = TRAILING_SORT_START
    for row in global_knowledge_repo.list_child_folders(db, base_id, parent_id):
        if row["id"] in matched:
            continue
        global_knowledge_repo.update_folder_sort_order(db, row["id"], order)
        order += 1
        _finalize_level(db, base_id=base_id, parent_id=row["id"], matched=set())
    for row in global_knowledge_repo.list_files_by_folder(db, parent_id):
        if row["id"] in matched:
            continue
        global_knowledge_repo.update_vault_file_sort_order(db, row["id"], order)
        order += 1


def main() -> None:
    if not INDEX_PATH.is_file():
        raise SystemExit(f"index.md not found: {INDEX_PATH}")

    init_db()
    toc = parse_index_md(INDEX_PATH.read_text(encoding="utf-8"))
    warnings: list[str] = []

    with connect() as db:
        base = global_knowledge_repo.find_base(db, BASE_ID)
        if base is None:
            raise SystemExit(f"Knowledge base not found: {BASE_ID}")
        root_folder_id = base["root_folder_id"]
        print(f"Applying index.md order to base '{base['name']}' ({BASE_ID})")
        matched = _apply_level(
            db,
            base_id=BASE_ID,
            parent_id=root_folder_id,
            nodes=toc,
            warnings=warnings,
        )
        _finalize_level(db, base_id=BASE_ID, parent_id=root_folder_id, matched=matched)
        global_knowledge_repo.touch_base(db, BASE_ID)

    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"  - {item}")

    tree = global_service.get_base_tree(BASE_ID, {
        "id": "u-admin",
        "role": "admin",
        "nickname": "管理员",
        "username": "admin",
        "project_scope": "全部项目",
    })

    def walk(node: dict, depth: int = 0) -> None:
        prefix = "  " * depth
        print(f"{prefix}{node['name']} (sort={node.get('sort_order', 0)})")
        if node["type"] == "folder":
            for child in node["children"]:
                walk(child, depth + 1)

    print("\nResult tree order:")
    for child in tree["root"]["children"]:
        walk(child)

    print(f"\nDone. Vault file count: {tree['base']['file_count']}")


if __name__ == "__main__":
    main()
