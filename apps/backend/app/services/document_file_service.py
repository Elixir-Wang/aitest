import secrets
import shutil
from pathlib import Path

from fastapi import UploadFile
from loguru import logger

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import project_requirement_dir, resolve_stored_path, store_path
from app.repositories import document_repo, project_repo
from app.services.document_serializer import serialize_document_from_db, serialize_file_mapping
from app.schemas.requirement_conversion import RequirementConversionInput
from app.agents.requirement_standardization.service import convert_requirement_file, fallback_convert_requirement_file
from app.services.requirement_markdown_normalizer import normalize_requirement_markdown
from app.services import operation_log_service

DOCUMENT_PENDING_MERGE_STATUS = "pending_merge"
CONVERSION_SUCCESS_STATUS = "success"
CONVERSION_FAILED_STATUS = "failed"
CONVERSION_PENDING_STATUS = "pending"
CONVERSION_PROCESSING_STATUS = "processing"
MAPPING_PENDING_MERGE_STATUS = "pending_merge"


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
        ensure_project_accepts_upload(db, project_id)
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

        created_mapping_ids: list[str] = []
        for index, upload in enumerate(files, start=1):
            created_mapping_ids.append(await save_source_file(db, project_id, document_id, upload, index, actor))

        document_repo.update_document_status(db, document_id, DOCUMENT_PENDING_MERGE_STATUS)
        created_files = [
            serialize_file_mapping(row)
            for row in document_repo.list_file_mappings(db, document_id)
            if row["id"] in set(created_mapping_ids)
        ]
        result = {
            "document": serialize_document_from_db(db, document_id, actor["role"]),
            "files": created_files,
        }
    action = "create" if mode == "new" else "upload"
    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action=action,
        object_type="requirement",
        object_id=document_id,
        object_name=result["document"]["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"{'新建需求' if mode == 'new' else '追加需求文件'}：{result['document']['name']}，文件 {len(created_files)} 个",
        after={
            "document_name": result["document"]["name"],
            "mode": mode,
            "files": [item["original_filename"] for item in created_files],
        },
    )
    return result


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
        rows = document_repo.list_file_mappings(db, document_id)
        return [serialize_file_mapping(row) for row in rows]


def get_original_file(mapping_id: str) -> dict:
    with connect() as db:
        row = document_repo.find_file_mapping(db, mapping_id)
        if not row:
            raise api_error(404, "DOCUMENT_FILE_NOT_FOUND", "来源文件不存在。")
        path = resolve_stored_path(row["source_file_path"])
        if path is None:
            raise api_error(404, "DOCUMENT_FILE_MISSING", "原始文件不存在。")
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
                "content_path": str(path),
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
        markdown_path = resolve_stored_path(markdown_path_value)
        if markdown_path is None:
            raise api_error(404, "DOCUMENT_MARKDOWN_MISSING", "转换稿不存在。")
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
    with connect() as db:
        row = document_repo.find_file_mapping(db, mapping_id)
        if not row:
            raise api_error(404, "DOCUMENT_FILE_NOT_FOUND", "来源文件不存在。")
        markdown_path_value = row["markdown_file_path"]
        if markdown_path_value:
            markdown_path = resolve_stored_path(markdown_path_value) or Path(markdown_path_value)
        else:
            markdown_path = standard_markdown_path(row["project_id"], row["document_id"], mapping_id)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown_content, encoding="utf-8")
        summary = change_summary.strip() or "人工修订标准文件。"
        document_repo.update_file_mapping_markdown(db, mapping_id, store_path(markdown_path) or str(markdown_path), summary)
        document = document_repo.find_by_project_and_id(db, row["project_id"], row["document_id"])
    result = get_converted_markdown(mapping_id)
    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="update",
        object_type="source_file",
        object_id=mapping_id,
        object_name=row["original_filename"],
        project_id=row["project_id"],
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"编辑需求标准文件：{row['original_filename']}",
        before={"original_filename": row["original_filename"], "document_name": document["name"] if document else ""},
        after={"conversion_summary": result["conversion_summary"]},
    )
    return result


def delete_source_file(mapping_id: str, actor) -> dict:
    with connect() as db:
        row = document_repo.find_file_mapping(db, mapping_id)
        if not row:
            raise api_error(404, "DOCUMENT_FILE_NOT_FOUND", "来源文件不存在。")

        snapshot = {
            "original_filename": row["original_filename"],
            "document_id": row["document_id"],
            "conversion_status": row["conversion_status"],
            "mapping_status": row["mapping_status"],
        }
        source_path = row["source_file_path"]
        markdown_path_value = row["markdown_file_path"]
        assets_dir = converted_assets_dir(row, markdown_path_value)
        document_repo.delete_file_mapping(db, mapping_id)

    if source_path:
        path = resolve_stored_path(source_path) or Path(source_path)
        if path.exists():
            path.unlink()

    if markdown_path_value:
        md_path = resolve_stored_path(markdown_path_value) or Path(markdown_path_value)
        if md_path.exists():
            md_path.unlink()

    if assets_dir.exists():
        shutil.rmtree(assets_dir)

    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="delete",
        object_type="source_file",
        object_id=mapping_id,
        object_name=snapshot["original_filename"],
        project_id=row["project_id"],
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"删除需求来源文件：{snapshot['original_filename']}",
        before=snapshot,
        after={},
    )
    return {"success": True}


async def save_source_file(db, project_id: str, document_id: str, upload: UploadFile, index: int, actor) -> str:
    raw_bytes = await upload.read()
    if not raw_bytes:
        raise api_error(400, "DOCUMENT_UPLOAD_EMPTY", "上传文件不能为空。")

    mapping_id = f"docmap-{secrets.token_hex(8)}"
    safe_filename = safe_filename_for_storage(upload.filename or f"requirement-{index}")
    file_format = file_format_for_filename(safe_filename)
    document_dir = project_requirement_dir(project_id, document_id)
    original_path = document_dir / "raw" / f"{mapping_id}-{safe_filename}"
    markdown_path = standard_markdown_path(project_id, document_id, mapping_id)
    original_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.write_bytes(raw_bytes)

    document_repo.create_file_mapping(
        db,
        mapping_id=mapping_id,
        document_id=document_id,
        version_id=None,
        source_file_path=store_path(original_path) or str(original_path),
        original_filename=safe_filename,
        file_format=file_format,
        markdown_file_path=None,
        conversion_status=CONVERSION_PENDING_STATUS,
        mapping_status=MAPPING_PENDING_MERGE_STATUS,
        conversion_summary="文件已上传，等待生成 Markdown 标准文件。",
        conversion_quality=None,
        created_by=actor["id"],
    )
    return mapping_id


async def convert_pending_mappings(mapping_ids: list[str]) -> None:
    for mapping_id in mapping_ids:
        await convert_source_file_mapping(mapping_id)


async def convert_source_file_mapping(mapping_id: str) -> dict:
    with connect() as db:
        row = document_repo.find_file_mapping(db, mapping_id)
        if not row:
            raise api_error(404, "DOCUMENT_FILE_NOT_FOUND", "来源文件不存在。")
        if row["conversion_status"] == CONVERSION_SUCCESS_STATUS and row["markdown_file_path"]:
            return serialize_file_mapping(row)
        document_repo.update_file_mapping_conversion_status(
            db,
            mapping_id,
            conversion_status=CONVERSION_PROCESSING_STATUS,
            conversion_summary="正在生成 Markdown 标准文件。",
        )

    try:
        source_path = resolve_stored_path(row["source_file_path"]) or Path(row["source_file_path"])
        if not source_path.exists():
            raise RuntimeError("原始文件不存在，无法生成 Markdown 标准文件。")
        markdown_path = standard_markdown_path(row["project_id"], row["document_id"], row["id"])
        markdown_text, conversion_summary = await convert_to_markdown(
            row["original_filename"],
            source_path=source_path,
            assets_dir=standard_assets_dir(row["project_id"], row["document_id"], row["id"]),
        )
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown_text, encoding="utf-8")
        with connect() as db:
            document_repo.update_file_mapping_markdown(
                db,
                mapping_id,
                store_path(markdown_path) or str(markdown_path),
                conversion_summary,
            )
            updated = document_repo.find_file_mapping(db, mapping_id)
            return serialize_file_mapping(updated)
    except Exception as exc:
        with connect() as db:
            document_repo.update_file_mapping_conversion_status(
                db,
                mapping_id,
                conversion_status=CONVERSION_FAILED_STATUS,
                conversion_summary=str(exc) or "文件转换失败。",
            )
            updated = document_repo.find_file_mapping(db, mapping_id)
            return serialize_file_mapping(updated)


async def convert_to_markdown(
    filename: str,
    raw_bytes: bytes | None = None,
    *,
    source_path: Path | None = None,
    assets_dir: Path | None = None,
) -> tuple[str, str]:
    if source_path is None:
        if raw_bytes is None:
            raise ValueError("缺少原始文件路径或文件内容，无法生成 Markdown 标准文件。")
        source_path = assets_dir.parent / filename if assets_dir is not None else Path(filename)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(raw_bytes)

    conversion_input = RequirementConversionInput(
        filename=filename,
        file_format=file_format_for_filename(filename),
        source_file_path=str(source_path),
        assets_dir_path=str(assets_dir) if assets_dir else None,
    )
    try:
        agent_output = await convert_requirement_file(conversion_input)
    except Exception as exc:
        fallback_markdown, fallback_summary = fallback_convert_requirement_file(conversion_input)
        fallback_markdown = normalize_requirement_markdown(fallback_markdown)
        logger.warning(
            "Requirement format agent output failed; using local conversion fallback | filename={filename} file_format={file_format} error={error_type}: {error}",
            filename=filename,
            file_format=conversion_input.file_format,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return fallback_markdown, f"{fallback_summary}（智能体输出解析或运行失败，已使用本地转换结果：{type(exc).__name__}。）"

    markdown = normalize_requirement_markdown(agent_output.markdown_content)
    markdown = markdown.strip()
    if not markdown:
        fallback_markdown, fallback_summary = fallback_convert_requirement_file(conversion_input)
        fallback_markdown = normalize_requirement_markdown(fallback_markdown)
        return fallback_markdown, f"{fallback_summary}（智能体未返回有效 Markdown，已使用本地转换结果。）"

    summary = agent_output.conversion_summary.strip() or "已通过需求标准化智能体生成标准 Markdown。"
    return markdown + "\n", summary


def converted_assets_dir(row, markdown_path_value: str | None) -> Path:
    if markdown_path_value:
        return (resolve_stored_path(markdown_path_value) or Path(markdown_path_value)).parent / f"{row['id']}_assets"
    return standard_assets_dir(row["project_id"], row["document_id"], row["id"])


def safe_filename_for_storage(filename: str) -> str:
    return Path(filename).name.replace("/", "_").replace("\\", "_")


def file_format_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix == "markdown":
        return "md"
    return suffix or "unknown"


def standard_markdown_path(project_id: str, document_id: str, mapping_id: str) -> Path:
    return project_requirement_dir(project_id, document_id) / "standard" / f"{mapping_id}.md"


def standard_assets_dir(project_id: str, document_id: str, mapping_id: str) -> Path:
    return project_requirement_dir(project_id, document_id) / "standard" / f"{mapping_id}_assets"


def ensure_project_accepts_upload(db, project_id: str) -> None:
    project = project_repo.find_by_id(db, project_id)
    if project is None:
        raise api_error(404, "PROJECT_NOT_FOUND", "项目不存在。")
    if project["status"] == "archived":
        raise api_error(409, "PROJECT_ARCHIVED", "归档项目不能上传需求。")
