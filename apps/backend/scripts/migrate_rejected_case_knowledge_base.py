# ruff: noqa: I001

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core import settings
from app.core.db import connect
from app.core.storage import resolve_stored_path
from app.repositories import global_knowledge_repo
from app.services.knowledge import global_service
from app.services.rejected_case_knowledge.markdown_codec import parse_document, render_document
from app.services.rejected_case_knowledge.service import (
    KNOWLEDGE_BASE_DESCRIPTION,
    KNOWLEDGE_BASE_NAME,
    _safe_name,
)


ACTOR = {"id": "system-migration", "role": "admin"}


def migrate(*, apply: bool) -> dict:
    if settings.REJECTED_CASE_KNOWLEDGE_BASE_ID:
        raise ValueError("迁移前请移除 AI_TESTING_REJECTED_CASE_KNOWLEDGE_BASE_ID，改用独立顶层知识库。")

    with connect() as db:
        bases = [dict(row) for row in global_knowledge_repo.list_bases(db)]
        dedicated = global_knowledge_repo.find_base_by_name(db, KNOWLEDGE_BASE_NAME)
        legacy_roots = []
        for base in bases:
            if dedicated and base["id"] == dedicated["id"]:
                continue
            folder = global_knowledge_repo.find_folder_by_parent_and_name(
                db,
                base["id"],
                base["root_folder_id"],
                KNOWLEDGE_BASE_NAME,
            )
            if folder:
                legacy_roots.append((base, dict(folder)))

    report = {
        "mode": "apply" if apply else "dry-run",
        "legacy_roots": len(legacy_roots),
        "folders": 0,
        "files": 0,
        "deleted_legacy_roots": 0,
        "renamed_folders": 0,
        "renamed_files": 0,
        "reformatted_files": 0,
    }

    if not apply:
        with connect() as db:
            for base, root in legacy_roots:
                folder_ids = global_knowledge_repo.descendant_folder_ids(db, base["id"], root["id"])
                report["folders"] += max(0, len(folder_ids) - 1)
                report["files"] += sum(
                    len(global_knowledge_repo.list_files_by_folder(db, folder_id)) for folder_id in folder_ids
                )
        if dedicated:
            _normalize_display_names(dict(dedicated), report, apply=False)
        return report

    if dedicated:
        target_base = dict(dedicated)
    elif legacy_roots:
        target_base = global_service.create_base(
            name=KNOWLEDGE_BASE_NAME,
            description=KNOWLEDGE_BASE_DESCRIPTION,
            actor=ACTOR,
        )
    else:
        return report

    for source_base, source_root in legacy_roots:
        _copy_folder_contents(
            source_base["id"],
            source_root["id"],
            target_base["id"],
            target_base["root_folder_id"],
            report,
        )
        global_service.delete_folder(source_base["id"], source_root["id"], ACTOR)
        report["deleted_legacy_roots"] += 1
    _normalize_display_names(target_base, report, apply=True)
    return report


def _copy_folder_contents(
    source_base_id: str,
    source_folder_id: str,
    target_base_id: str,
    target_folder_id: str,
    report: dict,
) -> None:
    with connect() as db:
        files = [dict(row) for row in global_knowledge_repo.list_files_by_folder(db, source_folder_id)]
        child_folders = [
            dict(row) for row in global_knowledge_repo.list_child_folders(db, source_base_id, source_folder_id)
        ]

    for file_row in files:
        path = resolve_stored_path(file_row["markdown_path"])
        content = path.read_text(encoding="utf-8") if path and path.exists() else file_row["markdown_content"]
        global_service.upsert_markdown_file(
            target_base_id,
            target_folder_id,
            display_name=file_row["display_name"],
            markdown_content=content,
            actor=ACTOR,
        )
        report["files"] += 1

    for child in child_folders:
        with connect() as db:
            target_child = global_knowledge_repo.find_folder_by_parent_and_name(
                db,
                target_base_id,
                target_folder_id,
                child["name"],
            )
        if not target_child:
            target_child = global_service.create_folder(
                target_base_id,
                parent_id=target_folder_id,
                name=child["name"],
                actor=ACTOR,
            )
        report["folders"] += 1
        _copy_folder_contents(
            source_base_id,
            child["id"],
            target_base_id,
            target_child["id"],
            report,
        )


def _normalize_display_names(base: dict, report: dict, *, apply: bool) -> None:
    with connect() as db:
        project_folders = [
            dict(row)
            for row in global_knowledge_repo.list_child_folders(db, base["id"], base["root_folder_id"])
        ]

    for folder in project_folders:
        with connect() as db:
            files = [dict(row) for row in global_knowledge_repo.list_files_by_folder(db, folder["id"])]
        project_name = ""
        file_updates = []
        for file_row in files:
            content = _read_markdown(file_row)
            header, records = parse_document(content)
            if records and not project_name:
                project_name = records[0].project_name
            requirement_name = str(header.get("requirement_name") or "")
            if not requirement_name and records:
                requirement_name = records[0].requirement_name
            desired_file_name = f"{_safe_name(requirement_name)}.md"
            rendered = render_document(
                project_id=str(header["project_id"]),
                project_name=str(header["project_name"]),
                requirement_id=str(header["requirement_id"]),
                requirement_name=str(header["requirement_name"]),
                records=records,
                updated_at=str(header.get("updated_at") or "") or None,
            )
            file_updates.append((file_row, desired_file_name, rendered, content != rendered))

        desired_folder_name = _safe_name(project_name) if project_name else folder["name"]
        if folder["name"] != desired_folder_name:
            report["renamed_folders"] += 1
            if apply:
                with connect() as db:
                    conflict = global_knowledge_repo.find_folder_by_parent_and_name(
                        db,
                        base["id"],
                        base["root_folder_id"],
                        desired_folder_name,
                    )
                    if conflict and conflict["id"] != folder["id"]:
                        raise ValueError(f"无法重命名项目目录，目标名称已存在：{desired_folder_name}")
                    global_knowledge_repo.update_folder_name(db, folder["id"], desired_folder_name)
                    global_knowledge_repo.touch_base(db, base["id"])

        for file_row, desired_file_name, rendered, needs_reformat in file_updates:
            needs_rename = file_row["display_name"] != desired_file_name
            report["renamed_files"] += int(needs_rename)
            report["reformatted_files"] += int(needs_reformat)
            if not apply or not (needs_rename or needs_reformat):
                continue
            if needs_rename:
                with connect() as db:
                    conflict = global_knowledge_repo.find_vault_file_by_folder_and_name(
                        db,
                        folder["id"],
                        desired_file_name,
                    )
                if conflict and conflict["id"] != file_row["id"]:
                    raise ValueError(f"无法重命名需求文件，目标名称已存在：{desired_file_name}")
            global_service.upsert_markdown_file(
                base["id"],
                folder["id"],
                display_name=desired_file_name,
                markdown_content=rendered,
                actor=ACTOR,
            )
            if needs_rename:
                global_service.delete_vault_file(base["id"], file_row["id"], ACTOR)


def _read_markdown(file_row: dict) -> str:
    path = resolve_stored_path(file_row["markdown_path"])
    return path.read_text(encoding="utf-8") if path and path.exists() else file_row["markdown_content"]


def main() -> None:
    parser = argparse.ArgumentParser(description="将库内的不采纳用例目录迁移为独立顶层知识库。")
    parser.add_argument("--apply", action="store_true", help="实际迁移；默认只输出 dry-run 报告。")
    args = parser.parse_args()
    print(json.dumps(migrate(apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
