import secrets
from pathlib import Path

from fastapi import UploadFile

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import global_knowledge_version_dir, resolve_stored_path, store_path
from app.repositories import global_knowledge_repo
from app.schemas.global_knowledge import GlobalKnowledgeListQuery, GlobalKnowledgeUpdateIn
from app.services import operation_log_service
from app.services.document.file_service import convert_to_markdown, file_format_for_filename, safe_filename_for_storage

KNOWLEDGE_TYPES = {
    "platform_prd": "平台 PRD",
    "test_standard": "测试规范",
    "case_template": "用例模板",
    "review_rule": "评审规则",
    "automation_standard": "自动化规范",
    "term": "通用术语",
    "workflow": "通用流程",
    "other": "其他",
}
STATUSES = {
    "processing": "转换中",
    "available": "可用",
    "conversion_failed": "转换失败",
    "archived": "已废弃",
}


def list_documents(query: GlobalKnowledgeListQuery, actor) -> dict:
    with connect() as db:
        rows, total = global_knowledge_repo.list_documents(db, query.model_dump())
        return {
            "items": [_serialize_document_list_item(row, actor["role"]) for row in rows],
            "pagination": {
                "page": query.page,
                "page_size": query.page_size,
                "total": total,
            },
            "filters": {
                "knowledge_types": [{"value": key, "label": value} for key, value in KNOWLEDGE_TYPES.items()],
                "statuses": [{"value": key, "label": value} for key, value in STATUSES.items()],
            },
        }


async def upload_document(
    *,
    name: str,
    knowledge_type: str,
    version: str,
    scope: str,
    source_note: str,
    description: str,
    files: list[UploadFile],
    actor,
    project_id: str = "",
) -> dict:
    if project_id:
        raise api_error(400, "GLOBAL_KNOWLEDGE_PROJECT_ID_FORBIDDEN", "公司知识库不允许关联项目。")
    _require_admin(actor)
    name = name.strip()
    knowledge_type = knowledge_type.strip()
    version_no = version.strip() or "v1"
    scope = scope.strip() or "全部项目"
    if not name:
        raise api_error(400, "GLOBAL_KNOWLEDGE_NAME_REQUIRED", "请填写知识名称。")
    if knowledge_type not in KNOWLEDGE_TYPES:
        raise api_error(400, "GLOBAL_KNOWLEDGE_TYPE_INVALID", "请选择有效的知识类型。")
    if not files:
        raise api_error(400, "GLOBAL_KNOWLEDGE_FILE_REQUIRED", "请至少上传一个公司知识文件。")

    document_id = f"gkdoc-{secrets.token_hex(8)}"
    version_id = f"gkver-{secrets.token_hex(8)}"
    with connect() as db:
        if global_knowledge_repo.find_document_by_name_type(db, name, knowledge_type):
            raise api_error(422, "GLOBAL_KNOWLEDGE_NAME_EXISTS", "同类型下已存在同名公司知识。")
        global_knowledge_repo.create_document(
            db,
            document_id=document_id,
            name=name,
            knowledge_type=knowledge_type,
            scope=scope,
            source_note=source_note.strip(),
            description=description.strip(),
            status="processing",
            created_by=actor["id"],
        )
        global_knowledge_repo.create_version(
            db,
            version_id=version_id,
            document_id=document_id,
            version_no=version_no,
            markdown_content="",
            markdown_path="",
            change_summary="首次上传公司知识。",
            conversion_status="queued",
            conversion_summary="文件已上传，等待转换。",
            created_by=actor["id"],
        )

    await _save_files_and_convert(document_id, version_id, files, actor, change_summary="首次上传公司知识。")
    result = get_document(document_id, actor)
    operation_log_service.record_change(
        log_type="audit",
        module="knowledge",
        action="upload_global_knowledge",
        object_type="global_knowledge_document",
        object_id=document_id,
        object_name=name,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"上传公司知识：{name}",
        after={"name": name, "knowledge_type": knowledge_type, "version": version_no},
    )
    return result


def get_document(document_id: str, actor) -> dict:
    with connect() as db:
        document = global_knowledge_repo.find_document(db, document_id)
        if not document:
            raise api_error(404, "GLOBAL_KNOWLEDGE_NOT_FOUND", "公司知识不存在。")
        current_version = global_knowledge_repo.find_current_version(db, document_id)
        versions = global_knowledge_repo.list_versions(db, document_id)
        files = global_knowledge_repo.list_files_by_version(db, current_version["id"]) if current_version else []
        usage_logs = global_knowledge_repo.list_usage_logs(db, current_version["id"]) if current_version else []
        return {
            "document": _serialize_document(document, current_version, files, actor["role"]),
            "current_version": _serialize_version(current_version) if current_version else None,
            "files": [_serialize_file(row) for row in files],
            "versions": [_serialize_version(row) for row in versions],
            "usage_logs": [dict(row) for row in usage_logs],
            "available_actions": _available_actions(document["status"], actor["role"]),
        }


def update_document(document_id: str, payload: GlobalKnowledgeUpdateIn, actor) -> dict:
    _require_admin(actor)
    if payload.knowledge_type not in KNOWLEDGE_TYPES:
        raise api_error(400, "GLOBAL_KNOWLEDGE_TYPE_INVALID", "请选择有效的知识类型。")
    with connect() as db:
        existing = global_knowledge_repo.find_document(db, document_id)
        if not existing:
            raise api_error(404, "GLOBAL_KNOWLEDGE_NOT_FOUND", "公司知识不存在。")
        duplicate = global_knowledge_repo.find_document_by_name_type(db, payload.name.strip(), payload.knowledge_type, exclude_id=document_id)
        if duplicate:
            raise api_error(422, "GLOBAL_KNOWLEDGE_NAME_EXISTS", "同类型下已存在同名公司知识。")
        before = dict(existing)
        global_knowledge_repo.update_document_metadata(
            db,
            document_id,
            name=payload.name.strip(),
            knowledge_type=payload.knowledge_type,
            scope=payload.scope.strip() or "全部项目",
            source_note=payload.source_note.strip(),
            description=payload.description.strip(),
        )
    operation_log_service.record_change(
        log_type="audit",
        module="knowledge",
        action="update_global_knowledge",
        object_type="global_knowledge_document",
        object_id=document_id,
        object_name=payload.name,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"编辑公司知识：{payload.name}",
        before=before,
        after=payload.model_dump(),
    )
    return get_document(document_id, actor)


async def create_version(
    document_id: str,
    *,
    version: str,
    source_note: str,
    change_summary: str,
    files: list[UploadFile],
    actor,
) -> dict:
    _require_admin(actor)
    if not files:
        raise api_error(400, "GLOBAL_KNOWLEDGE_FILE_REQUIRED", "请至少上传一个公司知识文件。")
    version_id = f"gkver-{secrets.token_hex(8)}"
    with connect() as db:
        document = global_knowledge_repo.find_document(db, document_id)
        if not document:
            raise api_error(404, "GLOBAL_KNOWLEDGE_NOT_FOUND", "公司知识不存在。")
        if document["status"] == "archived":
            raise api_error(409, "GLOBAL_KNOWLEDGE_ARCHIVED", "已废弃公司知识不能新增版本。")
        version_no = version.strip() or f"v{len(global_knowledge_repo.list_versions(db, document_id)) + 1}"
        global_knowledge_repo.create_version(
            db,
            version_id=version_id,
            document_id=document_id,
            version_no=version_no,
            markdown_content="",
            markdown_path="",
            change_summary=change_summary.strip() or "新增公司知识版本。",
            conversion_status="queued",
            conversion_summary="文件已上传，等待转换。",
            created_by=actor["id"],
        )
        global_knowledge_repo.update_document_metadata(
            db,
            document_id,
            name=document["name"],
            knowledge_type=document["knowledge_type"],
            scope=document["scope"],
            source_note=source_note.strip() or document["source_note"],
            description=document["description"],
        )
        name = document["name"]

    await _save_files_and_convert(document_id, version_id, files, actor, change_summary=change_summary.strip() or "新增公司知识版本。")
    operation_log_service.record_change(
        log_type="audit",
        module="knowledge",
        action="create_global_knowledge_version",
        object_type="global_knowledge_document",
        object_id=document_id,
        object_name=name,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"新增公司知识版本：{name}",
        after={"version_id": version_id, "version": version or ""},
    )
    return get_document(document_id, actor)


def archive_document(document_id: str, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        document = global_knowledge_repo.find_document(db, document_id)
        if not document:
            raise api_error(404, "GLOBAL_KNOWLEDGE_NOT_FOUND", "公司知识不存在。")
        global_knowledge_repo.update_document_status(db, document_id, status="archived")
    operation_log_service.record_change(
        log_type="audit",
        module="knowledge",
        action="archive_global_knowledge",
        object_type="global_knowledge_document",
        object_id=document_id,
        object_name=document["name"],
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"废弃公司知识：{document['name']}",
        before=dict(document),
        after={"status": "archived"},
    )
    return get_document(document_id, actor)


async def _save_files_and_convert(
    document_id: str,
    version_id: str,
    files: list[UploadFile],
    actor,
    *,
    change_summary: str,
) -> None:
    version_dir = global_knowledge_version_dir(document_id, version_id)
    raw_dir = version_dir / "raw"
    markdown_dir = version_dir / "markdown"
    raw_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)
    markdown_parts: list[str] = []
    summaries: list[str] = []
    try:
        for index, upload in enumerate(files, start=1):
            raw_bytes = await upload.read()
            if not raw_bytes:
                raise RuntimeError("上传文件不能为空。")
            safe_name = safe_filename_for_storage(upload.filename or f"global-knowledge-{index}")
            file_id = f"gkfile-{secrets.token_hex(8)}"
            raw_path = raw_dir / f"{file_id}-{safe_name}"
            raw_path.write_bytes(raw_bytes)
            file_type = file_format_for_filename(safe_name)
            with connect() as db:
                global_knowledge_repo.create_file(
                    db,
                    file_id=file_id,
                    version_id=version_id,
                    original_filename=safe_name,
                    file_path=store_path(raw_path) or str(raw_path),
                    file_type=file_type,
                    file_size=len(raw_bytes),
                )
            markdown, summary = await convert_to_markdown(
                safe_name,
                source_path=raw_path,
                assets_dir=markdown_dir / f"{file_id}_assets",
            )
            markdown_parts.append(f"<!-- source: {safe_name} -->\n\n{markdown.strip()}\n")
            summaries.append(summary)
        markdown_content = "\n\n---\n\n".join(markdown_parts).strip() + "\n"
        markdown_path = markdown_dir / "content.md"
        markdown_path.write_text(markdown_content, encoding="utf-8")
        with connect() as db:
            global_knowledge_repo.update_version_conversion(
                db,
                version_id,
                markdown_content=markdown_content,
                markdown_path=store_path(markdown_path) or str(markdown_path),
                conversion_status="success",
                conversion_summary="；".join(summaries) or "公司知识已转换为 Markdown。",
            )
            version = global_knowledge_repo.find_version(db, version_id)
            if version:
                global_knowledge_repo.update_document_status(
                    db,
                    version["document_id"],
                    status="available",
                    current_version_id=version_id,
                )
    except Exception as exc:
        with connect() as db:
            global_knowledge_repo.update_version_conversion(
                db,
                version_id,
                markdown_content="",
                markdown_path="",
                conversion_status="failed",
                conversion_summary=str(exc) or "文件转换失败。",
            )
            version = global_knowledge_repo.find_version(db, version_id)
            if version:
                global_knowledge_repo.update_document_status(db, version["document_id"], status="conversion_failed", current_version_id=version_id)


def _serialize_document_list_item(row, role: str) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "knowledge_type": row["knowledge_type"],
        "knowledge_type_label": KNOWLEDGE_TYPES.get(row["knowledge_type"], row["knowledge_type"]),
        "version": row["current_version_no"] or "",
        "scope": row["scope"],
        "status": row["status"],
        "status_label": STATUSES.get(row["status"], row["status"]),
        "file_count": row["file_count"],
        "description": row["description"],
        "updated_at": row["updated_at"],
        "created_by": row["created_by"],
        "available_actions": _available_actions(row["status"], role),
    }


def _serialize_document(row, current_version, files, role: str) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "knowledge_type": row["knowledge_type"],
        "knowledge_type_label": KNOWLEDGE_TYPES.get(row["knowledge_type"], row["knowledge_type"]),
        "scope": row["scope"],
        "source_note": row["source_note"],
        "description": row["description"],
        "status": row["status"],
        "status_label": STATUSES.get(row["status"], row["status"]),
        "current_version_id": row["current_version_id"],
        "version": current_version["version_no"] if current_version else "",
        "markdown_content": current_version["markdown_content"] if current_version else "",
        "file_count": len(files),
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "archived_at": row["archived_at"],
        "available_actions": _available_actions(row["status"], role),
    }


def _serialize_version(row) -> dict:
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "version_no": row["version_no"],
        "markdown_content": row["markdown_content"],
        "markdown_path": row["markdown_path"],
        "change_summary": row["change_summary"],
        "conversion_status": row["conversion_status"],
        "conversion_summary": row["conversion_summary"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


def _serialize_file(row) -> dict:
    return {
        "id": row["id"],
        "version_id": row["version_id"],
        "original_filename": row["original_filename"],
        "file_path": row["file_path"],
        "file_type": row["file_type"],
        "file_size": row["file_size"],
        "created_at": row["created_at"],
    }


def _available_actions(status: str, role: str) -> list[dict]:
    can_write = role == "admin"
    return [
        {
            "key": "upload_global_knowledge",
            "label": "上传公司知识",
            "enabled": can_write,
            "disabled_reason": "" if can_write else "仅管理员可上传公司知识。",
            "risk_level": "normal",
            "confirm_required": False,
        },
        {
            "key": "update_global_knowledge",
            "label": "编辑公司知识",
            "enabled": can_write and status != "archived",
            "disabled_reason": "" if can_write and status != "archived" else "已废弃或无权限。",
            "risk_level": "normal",
            "confirm_required": False,
        },
        {
            "key": "create_global_knowledge_version",
            "label": "新增版本",
            "enabled": can_write and status != "archived",
            "disabled_reason": "" if can_write and status != "archived" else "已废弃或无权限。",
            "risk_level": "normal",
            "confirm_required": False,
        },
        {
            "key": "archive_global_knowledge",
            "label": "废弃",
            "enabled": can_write and status != "archived",
            "disabled_reason": "" if can_write and status != "archived" else "已废弃或无权限。",
            "risk_level": "warning",
            "confirm_required": True,
        },
    ]


def _require_admin(actor) -> None:
    if actor["role"] != "admin":
        raise api_error(403, "PERMISSION_DENIED", "仅管理员可维护公司知识库。")
