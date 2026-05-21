from __future__ import annotations

import secrets
import shutil
from pathlib import Path

from fastapi import UploadFile

from app.agents.document_parser import requirement_file_parser_agent
from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import project_requirement_dir
from app.repositories import document_repo

PARSING_STATUS = "parsing"
READY_STATUS = "pending_review"


def list_documents(project_id: str, actor) -> list[dict]:
    with connect() as db:
        rows = document_repo.list_by_project(db, project_id)
        return [serialize_document(row, actor["role"]) for row in rows]


async def upload_documents(
    project_id: str,
    files: list[UploadFile],
    name: str,
    document_type: str,
    change_summary: str,
    actor,
) -> list[dict]:
    if not files:
        raise api_error(400, "DOCUMENT_UPLOAD_EMPTY", "请至少上传一个需求文件。")

    created: list[dict] = []
    with connect() as db:
        for index, upload in enumerate(files, start=1):
            raw_bytes = await upload.read()
            if not raw_bytes:
                raise api_error(400, "DOCUMENT_UPLOAD_EMPTY", "上传文件不能为空。")

            document_id = f"doc-{secrets.token_hex(8)}"
            version_id = f"docver-{secrets.token_hex(8)}"
            mapping_id = f"docmap-{secrets.token_hex(8)}"
            safe_filename = _safe_filename(upload.filename or f"requirement-{index}")
            document_dir = project_requirement_dir(project_id, document_id)
            original_path = document_dir / "raw" / safe_filename
            markdown_path = document_dir / "markdown" / "v1.md"
            original_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            original_path.write_bytes(raw_bytes)

            is_markdown = safe_filename.lower().endswith((".md", ".markdown"))
            if is_markdown:
                markdown_text = _decode_text(raw_bytes)
                parsed_summary = "Markdown 文件直接保存，无需解析。"
                document_status = READY_STATUS
                mapping_status = READY_STATUS
            else:
                parsed_document = requirement_file_parser_agent.parse(safe_filename, raw_bytes)
                markdown_text = parsed_document.markdown
                parsed_summary = parsed_document.summary
                document_status = PARSING_STATUS
                mapping_status = PARSING_STATUS

            markdown_path.write_text(markdown_text, encoding="utf-8")

            document_repo.create_document(
                db,
                document_id=document_id,
                project_id=project_id,
                name=name or safe_filename,
                document_type=document_type,
                original_file_path=str(original_path),
                status=document_status,
                created_by=actor["id"],
            )
            document_repo.create_version(
                db,
                version_id=version_id,
                document_id=document_id,
                version_no=1,
                file_path=str(markdown_path),
                source_action="upload",
                change_summary=change_summary or "上传需求文件",
                diff_summary="首次上传，无差异。",
                created_by=actor["id"],
            )
            document_repo.create_file_mapping(
                db,
                mapping_id=mapping_id,
                document_id=document_id,
                version_id=version_id,
                source_file_path=str(original_path),
                markdown_file_path=str(markdown_path),
                mapping_status=mapping_status,
                conversion_summary=parsed_summary,
            )
            document_repo.update_current_version(db, document_id, version_id, document_status)
            created.append(_serialize_document_from_db(db, document_id, actor["role"]))
    return created


def get_document_versions(document_id: str) -> list[dict]:
    with connect() as db:
        rows = document_repo.find_versions_by_document(db, document_id)
        return [
            {
                "id": row["id"],
                "version_no": row["version_no"],
                "file_path": row["file_path"],
                "source_action": row["source_action"],
                "change_summary": row["change_summary"],
                "diff_summary": row["diff_summary"],
                "created_by": row["created_by"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def get_document_detail(project_id: str, document_id: str, actor) -> dict:
    with connect() as db:
        row = db.execute(
            """
            SELECT d.*,
                   v.id AS version_id,
                   v.version_no AS version_no,
                   v.file_path AS markdown_file_path,
                   v.source_action AS source_action,
                   v.change_summary AS change_summary,
                   v.diff_summary AS diff_summary,
                   v.created_by AS version_created_by,
                   v.created_at AS version_created_at
            FROM source_documents d
            LEFT JOIN source_document_versions v ON v.id = d.current_version_id
            WHERE d.project_id = ? AND d.id = ?
            """,
            (project_id, document_id),
        ).fetchone()
        if row is None:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        document = serialize_document(row, actor["role"])
        versions = get_document_versions(document_id)
        markdown_content = ""
        current_version = document["current_version"]
        if current_version and current_version["file_path"]:
            markdown_path = Path(current_version["file_path"])
            if markdown_path.exists():
                markdown_content = markdown_path.read_text(encoding="utf-8")

        return {
            "document": document,
            "versions": versions,
            "markdown_content": markdown_content,
        }


def delete_document(project_id: str, document_id: str) -> dict:
    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        document_dir = project_requirement_dir(project_id, document_id)
        document_repo.delete_graph(db, document_id)

    if document_dir.exists():
        shutil.rmtree(document_dir)

    return {"success": True}


def serialize_document(row, actor_role: str) -> dict:
    current_version = None
    if row["version_id"]:
        current_version = {
            "id": row["version_id"],
            "version_no": row["version_no"],
            "file_path": row["markdown_file_path"],
            "source_action": row["source_action"],
            "change_summary": row["change_summary"],
            "diff_summary": row["diff_summary"],
            "created_by": row["version_created_by"],
            "created_at": row["version_created_at"],
        }

    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "document_type": row["document_type"],
        "original_file_path": row["original_file_path"],
        "current_version_id": row["current_version_id"],
        "status": row["status"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "current_version": current_version,
        "available_actions": ["read", "create", "update", "delete"] if actor_role == "admin" else ["read", "create"],
    }


def _serialize_document_from_db(db, document_id: str, actor_role: str) -> dict:
    row = db.execute(
        """
        SELECT d.*,
               v.id AS version_id,
               v.version_no AS version_no,
               v.file_path AS markdown_file_path,
               v.source_action AS source_action,
               v.change_summary AS change_summary,
               v.diff_summary AS diff_summary,
               v.created_by AS version_created_by,
               v.created_at AS version_created_at
        FROM source_documents d
        LEFT JOIN source_document_versions v ON v.id = d.current_version_id
        WHERE d.id = ?
        """,
        (document_id,),
    ).fetchone()
    return serialize_document(row, actor_role)


def _safe_filename(filename: str) -> str:
    return Path(filename).name.replace("/", "_").replace("\\", "_")


def _decode_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")
