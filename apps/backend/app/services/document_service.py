from __future__ import annotations

import secrets
import shutil
from pathlib import Path

from fastapi import UploadFile

from app.agents.document_parser import requirement_file_parser_agent
from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import project_requirement_dir
from app.repositories import document_repo, project_repo
from app.schemas.document import SourceDocumentUpdateIn

DOCUMENT_PENDING_MERGE_STATUS = "pending_merge"
DOCUMENT_VERSIONED_STATUS = "versioned"
CONVERSION_SUCCESS_STATUS = "success"
CONVERSION_FAILED_STATUS = "failed"
MAPPING_PENDING_MERGE_STATUS = "pending_merge"
MAPPING_MERGED_STATUS = "merged"


def list_documents(project_id: str, actor) -> list[dict]:
    with connect() as db:
        rows = document_repo.list_by_project(db, project_id)
        return [serialize_document(row, actor["role"]) for row in rows]


def check_document_name(project_id: str, name: str, exclude_id: str | None = None) -> dict:
    normalized_name = name.strip()
    if not normalized_name:
        return {"exists": False}
    with connect() as db:
        return {"exists": document_repo.find_by_project_and_name(db, project_id, normalized_name, exclude_id) is not None}


async def upload_documents(
    project_id: str,
    files: list[UploadFile],
    actor,
    *,
    mode: str = "new",
    document_name: str = "",
    existing_document_id: str = "",
) -> dict:
    if not files:
        raise api_error(400, "DOCUMENT_UPLOAD_EMPTY", "请至少上传一个需求文件。")
    if mode not in {"new", "append"}:
        raise api_error(400, "DOCUMENT_UPLOAD_MODE_INVALID", "上传模式不正确。")

    with connect() as db:
        _ensure_project_accepts_upload(db, project_id)
        if mode == "new":
            name = document_name.strip()
            if not name:
                raise api_error(400, "DOCUMENT_NAME_REQUIRED", "请填写需求名称。")
            if document_repo.find_by_project_and_name(db, project_id, name):
                raise api_error(422, "DOCUMENT_NAME_EXISTS", "该需求名称已存在。")
            document_id = f"doc-{secrets.token_hex(8)}"
            document_repo.create_document(
                db,
                document_id=document_id,
                project_id=project_id,
                name=name,
                document_type="PRD",
                status=DOCUMENT_PENDING_MERGE_STATUS,
                created_by=actor["id"],
            )
        else:
            document_id = existing_document_id.strip()
            if not document_id:
                raise api_error(400, "DOCUMENT_ID_REQUIRED", "请选择已有需求。")
            existing = document_repo.find_by_project_and_id(db, project_id, document_id)
            if not existing:
                raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        created_files: list[dict] = []
        for index, upload in enumerate(files, start=1):
            created_files.append(await _save_source_file(db, project_id, document_id, upload, index, actor))

        document_repo.update_document_status(db, document_id, DOCUMENT_PENDING_MERGE_STATUS)
        return {
            "document": _serialize_document_from_db(db, document_id, actor["role"]),
            "files": created_files,
        }


async def append_document_files(project_id: str, document_id: str, files: list[UploadFile], actor) -> dict:
    return await upload_documents(
        project_id,
        files,
        actor,
        mode="append",
        existing_document_id=document_id,
    )


def list_document_files(project_id: str, document_id: str) -> list[dict]:
    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        return [serialize_file_mapping(row) for row in document_repo.list_file_mappings(db, document_id)]


def get_original_file(mapping_id: str) -> dict:
    with connect() as db:
        row = document_repo.find_file_mapping(db, mapping_id)
        if not row:
            raise api_error(404, "DOCUMENT_FILE_NOT_FOUND", "来源文件不存在。")
        path = Path(row["source_file_path"])
        if not path.exists():
            raise api_error(404, "DOCUMENT_FILE_MISSING", "原始文件不存在。")
        file_format = row["file_format"].lower()
        if file_format in {"txt", "md", "markdown"}:
            return {
                "id": row["id"],
                "original_filename": row["original_filename"],
                "file_format": row["file_format"],
                "content_type": "text",
                "content": path.read_text(encoding="utf-8", errors="ignore"),
            }
        return {
            "id": row["id"],
            "original_filename": row["original_filename"],
            "file_format": row["file_format"],
            "content_type": "download",
            "download_path": str(path),
        }


def get_converted_markdown(mapping_id: str) -> dict:
    with connect() as db:
        row = document_repo.find_file_mapping(db, mapping_id)
        if not row:
            raise api_error(404, "DOCUMENT_FILE_NOT_FOUND", "来源文件不存在。")
        if row["conversion_status"] not in {CONVERSION_SUCCESS_STATUS, "warning"}:
            raise api_error(409, "DOCUMENT_CONVERSION_NOT_READY", row["conversion_summary"] or "转换稿尚未生成。")
        markdown_path_value = row["markdown_file_path"]
        if not markdown_path_value:
            raise api_error(404, "DOCUMENT_MARKDOWN_MISSING", "转换稿不存在。")
        markdown_path = Path(markdown_path_value)
        if not markdown_path.exists():
            raise api_error(404, "DOCUMENT_MARKDOWN_MISSING", "转换稿不存在。")
        return {
            "id": row["id"],
            "original_filename": row["original_filename"],
            "markdown_content": markdown_path.read_text(encoding="utf-8"),
            "conversion_status": row["conversion_status"],
            "conversion_summary": row["conversion_summary"],
        }


def update_converted_markdown(mapping_id: str, *, markdown_content: str, change_summary: str, actor) -> dict:
    _ = actor
    with connect() as db:
        row = document_repo.find_file_mapping(db, mapping_id)
        if not row:
            raise api_error(404, "DOCUMENT_FILE_NOT_FOUND", "来源文件不存在。")
        markdown_path_value = row["markdown_file_path"]
        if markdown_path_value:
            markdown_path = Path(markdown_path_value)
        else:
            document_dir = project_requirement_dir(row["project_id"], row["document_id"])
            markdown_path = document_dir / "markdown" / "conversions" / f"{mapping_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown_content, encoding="utf-8")
        summary = change_summary.strip() or "人工修订标准文件。"
        document_repo.update_file_mapping_markdown(db, mapping_id, str(markdown_path), summary)
    return get_converted_markdown(mapping_id)


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
                   COUNT(m.id) AS file_count,
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
            LEFT JOIN source_document_file_mappings m ON m.document_id = d.id
            WHERE d.project_id = ? AND d.id = ?
            GROUP BY d.id
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


def update_document(project_id: str, document_id: str, payload: SourceDocumentUpdateIn, actor) -> dict:
    name = payload.name.strip()
    if not name:
        raise api_error(400, "DOCUMENT_NAME_REQUIRED", "请填写需求名称。")

    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        duplicate = document_repo.find_by_project_and_name(db, project_id, name, exclude_id=document_id)
        if duplicate:
            raise api_error(422, "DOCUMENT_NAME_EXISTS", "该需求名称已存在。")

        version_id = f"docver-{secrets.token_hex(8)}"
        version_no = document_repo.next_version_no(db, document_id)
        markdown_path = project_requirement_dir(project_id, document_id) / "markdown" / "versions" / f"v{version_no}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(payload.markdown_content, encoding="utf-8")

        document_repo.update_document_name(db, document_id, name)
        document_repo.create_version(
            db,
            version_id=version_id,
            document_id=document_id,
            version_no=version_no,
            file_path=str(markdown_path),
            source_action="edit",
            change_summary=payload.change_summary.strip() or "编辑需求文档",
            diff_summary="人工编辑生成新版本。",
            created_by=actor["id"],
        )
        document_repo.update_current_version(db, document_id, version_id, DOCUMENT_VERSIONED_STATUS)

    return get_document_detail(project_id, document_id, actor)


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
        "file_count": row["file_count"] if "file_count" in row.keys() else 0,
        "current_version_id": row["current_version_id"],
        "status": row["status"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "current_version": current_version,
        "available_actions": ["read", "create", "update", "delete"] if actor_role == "admin" else ["read", "create"],
    }


def serialize_file_mapping(row) -> dict:
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "version_id": row["version_id"],
        "version_no": row["version_no"] if "version_no" in row.keys() else None,
        "original_filename": row["original_filename"],
        "file_format": row["file_format"],
        "source_file_path": row["source_file_path"],
        "markdown_file_path": row["markdown_file_path"],
        "conversion_status": row["conversion_status"],
        "mapping_status": row["mapping_status"],
        "conversion_summary": row["conversion_summary"],
        "conversion_quality": row["conversion_quality"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


async def _save_source_file(db, project_id: str, document_id: str, upload: UploadFile, index: int, actor) -> dict:
    raw_bytes = await upload.read()
    if not raw_bytes:
        raise api_error(400, "DOCUMENT_UPLOAD_EMPTY", "上传文件不能为空。")

    mapping_id = f"docmap-{secrets.token_hex(8)}"
    safe_filename = _safe_filename(upload.filename or f"requirement-{index}")
    file_format = _file_format(safe_filename)
    document_dir = project_requirement_dir(project_id, document_id)
    original_path = document_dir / "raw" / f"{mapping_id}-{safe_filename}"
    markdown_path = document_dir / "markdown" / "conversions" / f"{mapping_id}.md"
    original_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.write_bytes(raw_bytes)

    try:
        markdown_text, conversion_summary = _convert_to_markdown(safe_filename, raw_bytes)
        markdown_path.write_text(markdown_text, encoding="utf-8")
        conversion_status = CONVERSION_SUCCESS_STATUS
        markdown_file_path: str | None = str(markdown_path)
    except Exception as exc:  # pragma: no cover - parser failures depend on external converters
        conversion_status = CONVERSION_FAILED_STATUS
        conversion_summary = str(exc) or "文件转换失败。"
        markdown_file_path = None

    document_repo.create_file_mapping(
        db,
        mapping_id=mapping_id,
        document_id=document_id,
        version_id=None,
        source_file_path=str(original_path),
        original_filename=safe_filename,
        file_format=file_format,
        markdown_file_path=markdown_file_path,
        conversion_status=conversion_status,
        mapping_status=MAPPING_PENDING_MERGE_STATUS,
        conversion_summary=conversion_summary,
        conversion_quality=100 if conversion_status == CONVERSION_SUCCESS_STATUS else None,
        created_by=actor["id"],
    )
    row = document_repo.find_file_mapping(db, mapping_id)
    return serialize_file_mapping(row)


def _serialize_document_from_db(db, document_id: str, actor_role: str) -> dict:
    row = db.execute(
        """
        SELECT d.*,
               COUNT(m.id) AS file_count,
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
        LEFT JOIN source_document_file_mappings m ON m.document_id = d.id
        WHERE d.id = ?
        GROUP BY d.id
        """,
        (document_id,),
    ).fetchone()
    return serialize_document(row, actor_role)


def _convert_to_markdown(filename: str, raw_bytes: bytes) -> tuple[str, str]:
    if filename.lower().endswith((".md", ".markdown", ".txt")):
        return _decode_text(raw_bytes), "文本文件直接保存为 Markdown 转换稿。"
    parsed_document = requirement_file_parser_agent.parse(filename, raw_bytes)
    return parsed_document.markdown, parsed_document.summary


def _safe_filename(filename: str) -> str:
    return Path(filename).name.replace("/", "_").replace("\\", "_")


def _file_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix == "markdown":
        return "md"
    return suffix or "unknown"


def _decode_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def _ensure_project_accepts_upload(db, project_id: str) -> None:
    project = project_repo.find_by_id(db, project_id)
    if project is None:
        raise api_error(404, "PROJECT_NOT_FOUND", "项目不存在。")
    if project["status"] == "archived":
        raise api_error(409, "PROJECT_ARCHIVED", "归档项目不能上传需求。")
