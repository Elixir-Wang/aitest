"""document CRUD + listing + 文件相关委派。

不包含版本管理（见 versions.py）和分析运行生命周期（见 analysis_runs.py）。
所有 *SourceFile / DocumentFile 操作委托给 file_service。
"""
from __future__ import annotations

import secrets
import shutil
from pathlib import Path

from fastapi import UploadFile
from loguru import logger

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import project_requirement_dir, resolve_stored_path, store_path
from app.repositories import (
    document_repo,
    requirement_analysis_run_repo,
    test_case_repo,
)
from app.schemas.document import SourceDocumentUpdateIn
from app.services import operation_log_service, task_service

from ._constants import (
    CONVERSION_FAILED_STATUS,
    CONVERSION_SUCCESS_STATUS,
    DOCUMENT_VERSIONED_STATUS,
)
from ._common import version_markdown_path
from .analysis_runs import (
    execute_requirement_review_run,
    start_requirement_review_run,
)
from . import file_service as document_file_service
from . import serializer as document_serializer


# === Listing ============================================================

def list_documents(project_id: str, actor) -> list[dict]:
    task_service.recover_stale_requirement_analysis_runs(project_id=project_id)
    with connect() as db:
        rows = document_repo.list_by_project(db, project_id)
        return [document_serializer.serialize_document(row, actor["role"]) for row in rows]


def list_visible_documents(actor) -> list[dict]:
    task_service.recover_stale_requirement_analysis_runs()
    with connect() as db:
        rows = document_repo.list_visible(db, actor)
        return [document_serializer.serialize_document(row, actor["role"]) for row in rows]


def check_document_name(project_id: str, name: str, exclude_id: str | None = None) -> dict:
    normalized_name = name.strip()
    if not normalized_name:
        return {"exists": False}
    with connect() as db:
        return {"exists": document_repo.find_by_project_and_name(db, project_id, normalized_name, exclude_id) is not None}


# === File 上传委派 =====================================================

async def upload_documents(
    project_id: str,
    files: list[UploadFile],
    actor,
    *,
    mode: str = "new",
    document_name: str = "",
    existing_document_id: str = "",
) -> dict:
    return await document_file_service.upload_documents(
        project_id,
        files,
        actor,
        mode=mode,
        document_name=document_name,
        existing_document_id=existing_document_id,
    )


async def append_document_files(project_id: str, document_id: str, files: list[UploadFile], actor) -> dict:
    return await document_file_service.append_document_files(project_id, document_id, files, actor)


def list_document_files(project_id: str, document_id: str) -> list[dict]:
    return document_file_service.list_document_files(project_id, document_id)


def get_original_file(mapping_id: str) -> dict:
    return document_file_service.get_original_file(mapping_id)


def get_converted_markdown(mapping_id: str) -> dict:
    return document_file_service.get_converted_markdown(mapping_id)


async def convert_source_file_mapping(mapping_id: str) -> dict:
    return await document_file_service.convert_source_file_mapping(mapping_id)


async def convert_pending_file_mappings(
    mapping_ids: list[str],
    actor: dict | None = None,
    *,
    auto_continue: bool = False,
) -> None:
    for mapping_id in mapping_ids:
        result = await document_file_service.convert_source_file_mapping(mapping_id)
        if auto_continue and actor:
            await maybe_auto_start_requirement_analysis(mapping_id, result, actor)


def update_converted_markdown(mapping_id: str, *, markdown_content: str, change_summary: str, actor) -> dict:
    return document_file_service.update_converted_markdown(
        mapping_id,
        markdown_content=markdown_content,
        change_summary=change_summary,
        actor=actor,
    )


async def maybe_auto_start_requirement_analysis(mapping_id: str, conversion_result: dict, actor: dict) -> None:
    conversion_status = conversion_result.get("conversion_status")
    if conversion_status not in {CONVERSION_SUCCESS_STATUS, "warning"}:
        return
    if conversion_result.get("file_role") != "primary":
        return
    if not conversion_result.get("markdown_file_path"):
        return

    document_id = conversion_result.get("document_id")
    if not document_id:
        return

    with connect() as db:
        mapping_row = document_repo.find_file_mapping(db, mapping_id)
        if not mapping_row:
            return
        project_id = mapping_row["project_id"]
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document or document["current_version_id"]:
            return
        if requirement_analysis_run_repo.list_by_document(db, document_id):
            return
        if requirement_analysis_run_repo.find_active_by_document(db, document_id):
            return

    try:
        task = start_requirement_review_run(project_id, document_id, actor)
        await execute_requirement_review_run(task["source_id"], actor)
    except Exception as exc:
        logger.warning(
            "auto_continue_requirement_analysis_failed | mapping_id={mapping_id} document_id={document_id} error={error}",
            mapping_id=mapping_id,
            document_id=document_id,
            error=exc,
        )


# === Document 详情 ===================================================

def get_document_detail(project_id: str, document_id: str, actor) -> dict:
    from .versions import get_document_versions

    task_service.recover_stale_requirement_analysis_runs(project_id=project_id)
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
                   v.created_at AS version_created_at,
                   latest_run.id AS requirement_analysis_run_id,
                   latest_run.status AS requirement_analysis_run_status,
                   latest_run.summary AS requirement_analysis_run_summary,
                   latest_run.failure_reason AS requirement_analysis_run_failure_reason,
                   latest_run.created_at AS requirement_analysis_run_created_at,
                   latest_run.updated_at AS requirement_analysis_run_updated_at
            FROM source_documents d
            LEFT JOIN source_document_versions v ON v.id = d.current_version_id
            LEFT JOIN source_document_file_mappings m ON m.document_id = d.id
            LEFT JOIN requirement_analysis_runs latest_run ON latest_run.id = (
                SELECT r.id
                FROM requirement_analysis_runs r
                WHERE r.document_id = d.id
                ORDER BY r.created_at DESC, r.id DESC
                LIMIT 1
            )
            WHERE d.project_id = ? AND d.id = ?
            GROUP BY d.id
            """,
            (project_id, document_id),
        ).fetchone()
        if row is None:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        document = document_serializer.serialize_document(row, actor["role"])
        versions = get_document_versions(document_id)
        markdown_content = ""
        current_version = document["current_version"]
        if current_version and current_version["file_path"]:
            markdown_path = resolve_stored_path(current_version["file_path"]) or Path(current_version["file_path"])
            if markdown_path.exists():
                markdown_content = markdown_path.read_text(encoding="utf-8")

        return {
            "document": document,
            "versions": versions,
            "markdown_content": markdown_content,
        }


def get_document_overview(project_id: str, document_id: str, actor) -> dict:
    detail = get_document_detail(project_id, document_id, actor)
    files = list_document_files(project_id, document_id)

    stats = {
        "total_files": len(files),
        "conversion_success": sum(1 for item in files if item["conversion_status"] == CONVERSION_SUCCESS_STATUS),
        "conversion_warning": sum(1 for item in files if item["conversion_status"] == "warning"),
        "conversion_failed": sum(1 for item in files if item["conversion_status"] == CONVERSION_FAILED_STATUS),
        "primary_files": sum(1 for item in files if item.get("file_role") == "primary"),
        "initial_requirement_status": "generated" if detail["document"]["current_version_id"] else "not_generated",
    }

    overview_files = [
        {
            **item,
            "standard_file_status": document_serializer.standard_file_status(item),
        }
        for item in files
    ]

    return {
        "document": detail["document"],
        "stats": stats,
        "files": overview_files,
        "initial_markdown_content": detail["markdown_content"],
    }


# === Document 编辑 / 设置主需求 =====================================

def update_document(project_id: str, document_id: str, payload: SourceDocumentUpdateIn, actor) -> dict:
    name = payload.name.strip()
    if not name:
        raise api_error(400, "DOCUMENT_NAME_REQUIRED", "请填写需求名称。")
    markdown_content = payload.markdown_content.strip()
    if not markdown_content:
        raise api_error(422, "DOCUMENT_MARKDOWN_REQUIRED", "最终需求稿不能为空。")

    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        duplicate = document_repo.find_by_project_and_name(db, project_id, name, exclude_id=document_id)
        if duplicate:
            raise api_error(422, "DOCUMENT_NAME_EXISTS", "该需求名称已存在。")

        version_id = f"docver-{secrets.token_hex(8)}"
        version_no = document_repo.next_version_no(db, document_id)
        markdown_path = version_markdown_path(project_id, document_id, version_no)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown_content, encoding="utf-8")

        document_repo.update_document_name(db, document_id, name)
        document_repo.create_version(
            db,
            version_id=version_id,
            document_id=document_id,
            version_no=version_no,
            file_path=store_path(markdown_path) or str(markdown_path),
            source_action="edit",
            change_summary=payload.change_summary.strip() or "编辑需求文档",
            diff_summary="人工编辑生成新版本。",
            created_by=actor["id"],
        )
        document_repo.update_current_version(db, document_id, version_id, DOCUMENT_VERSIONED_STATUS)

    result = get_document_detail(project_id, document_id, actor)
    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="update",
        object_type="requirement",
        object_id=document_id,
        object_name=name,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"编辑需求：{name}",
        before={"name": existing["name"], "status": existing["status"], "current_version_id": existing["current_version_id"]},
        after={"name": name, "version_id": version_id, "version_no": version_no},
    )
    return result


def set_primary_requirement_file(project_id: str, document_id: str, mapping_id: str, actor) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        file_mapping = document_repo.find_file_mapping(db, mapping_id)
        if not file_mapping or file_mapping["document_id"] != document_id or file_mapping["project_id"] != project_id:
            raise api_error(404, "DOCUMENT_FILE_NOT_FOUND", "来源文件不存在。")
        if file_mapping["conversion_status"] not in {CONVERSION_SUCCESS_STATUS, "warning"} or not file_mapping["markdown_file_path"]:
            raise api_error(409, "DOCUMENT_PRIMARY_FILE_NOT_READY", "请先完成标准文件转换后再设为主需求。")

        markdown_path = resolve_stored_path(file_mapping["markdown_file_path"]) or Path(file_mapping["markdown_file_path"])
        if not markdown_path.exists():
            raise api_error(404, "DOCUMENT_MARKDOWN_MISSING", "标准文件不存在。")

        document_repo.set_primary_file_mapping(db, document_id, mapping_id)
        document_file_service.sync_document_status(db, document_id)

    result = get_document_overview(project_id, document_id, actor)
    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="set_primary_file",
        object_type="source_file",
        object_id=mapping_id,
        object_name=file_mapping["original_filename"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"设置主需求文件：{file_mapping['original_filename']}",
        after={"file_role": "primary"},
    )
    return result


def delete_source_file(mapping_id: str, actor) -> dict:
    return document_file_service.delete_source_file(mapping_id, actor)


def delete_document(project_id: str, document_id: str, actor) -> dict:
    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        document_dir = project_requirement_dir(project_id, document_id)
        snapshot = {"name": existing["name"], "status": existing["status"], "current_version_id": existing["current_version_id"]}
        linked_test_case_sets = test_case_repo.list_by_requirement_document(db, document_id)
        if linked_test_case_sets:
            names = "、".join(row["name"] for row in linked_test_case_sets[:3])
            suffix = "等" if len(linked_test_case_sets) > 3 else ""
            raise api_error(
                409,
                "DOCUMENT_HAS_TEST_CASE_SETS",
                f"该需求文档已关联测试用例集：{names}{suffix}。请先删除关联测试用例集后再删除需求文档。",
            )
        document_repo.delete_graph(db, document_id)

    if document_dir.exists():
        try:
            shutil.rmtree(document_dir)
        except OSError as exc:
            message = f"需求文档数据已删除，但文件目录清理失败：{document_dir}。请检查文件占用或目录权限后手动清理。"
            operation_log_service.record_failure(
                log_type="audit",
                module="requirement",
                action="delete",
                object_type="requirement",
                object_id=document_id,
                object_name=snapshot["name"],
                project_id=project_id,
                actor_id=actor["id"],
                actor_name=operation_log_service.actor_display_name(actor),
                source="web",
                summary=f"删除需求文件清理失败：{snapshot['name']}",
                failure_reason=f"{message} 原因：{exc}",
                before=snapshot,
                after={"document_dir": str(document_dir)},
            )
            raise api_error(500, "DOCUMENT_FILE_DELETE_FAILED", message) from exc

    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="delete",
        object_type="requirement",
        object_id=document_id,
        object_name=snapshot["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"删除需求：{snapshot['name']}",
        before=snapshot,
        after={},
    )
    return {"success": True}
