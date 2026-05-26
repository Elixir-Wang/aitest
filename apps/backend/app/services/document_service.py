from __future__ import annotations

import json
import secrets
import shutil
from pathlib import Path

from fastapi import UploadFile
from fastapi import HTTPException

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import project_requirement_dir, resolve_stored_path, store_path
from app.repositories import document_repo
from app.schemas.document import SourceDocumentUpdateIn
from app.schemas.requirement_analysis import RequirementAnalysisInput
from app.services import (
    document_file_service,
    document_merge_orchestrator,
    document_serializer,
    operation_log_service,
    requirement_analysis_service,
    requirement_merge_artifact_service,
)

DOCUMENT_PENDING_MERGE_STATUS = "pending_merge"
DOCUMENT_VERSIONED_STATUS = "versioned"
CONVERSION_SUCCESS_STATUS = "success"
CONVERSION_FAILED_STATUS = "failed"


def list_documents(project_id: str, actor) -> list[dict]:
    with connect() as db:
        rows = document_repo.list_by_project(db, project_id)
        return [document_serializer.serialize_document(row, actor["role"]) for row in rows]


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


async def convert_pending_file_mappings(mapping_ids: list[str]) -> None:
    await document_file_service.convert_pending_mappings(mapping_ids)


def update_converted_markdown(mapping_id: str, *, markdown_content: str, change_summary: str, actor) -> dict:
    return document_file_service.update_converted_markdown(
        mapping_id,
        markdown_content=markdown_content,
        change_summary=change_summary,
        actor=actor,
    )


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
    with connect() as db:
        open_conflicts = document_repo.list_conflicts(db, document_id, status="open")
        latest_merge_run = document_repo.find_latest_merge_run(db, document_id)

    stats = {
        "total_files": len(files),
        "conversion_success": sum(1 for item in files if item["conversion_status"] == CONVERSION_SUCCESS_STATUS),
        "conversion_warning": sum(1 for item in files if item["conversion_status"] == "warning"),
        "conversion_failed": sum(1 for item in files if item["conversion_status"] == CONVERSION_FAILED_STATUS),
        "mergeable_files": sum(
            1
            for item in files
            if item["conversion_status"] in {CONVERSION_SUCCESS_STATUS, "warning"} and item["mapping_status"] != "discarded"
        ),
        "open_conflicts": len(open_conflicts),
        "initial_requirement_status": "generated" if detail["document"]["current_version_id"] else "not_generated",
    }

    overview_files = [
        {
            **item,
            "standard_file_status": document_serializer.standard_file_status(item),
            "conflict_status": "open" if open_conflicts else "none",
        }
        for item in files
    ]
    changed_standard_files = [
        item
        for item in overview_files
        if detail["document"]["current_version_id"]
        and item["conversion_status"] in {CONVERSION_SUCCESS_STATUS, "warning"}
        and item["mapping_status"] == DOCUMENT_PENDING_MERGE_STATUS
    ]

    return {
        "document": detail["document"],
        "stats": stats,
        "files": overview_files,
        "has_open_conflicts": len(open_conflicts) > 0,
        "merge_sync_status": "outdated" if changed_standard_files else "synced",
        "changed_standard_files": changed_standard_files,
        "initial_markdown_content": detail["markdown_content"],
        "artifact_tabs": requirement_merge_artifact_service.read_merge_artifact_tabs(
            project_id,
            document_id,
            latest_merge_run["id"],
        )
        if latest_merge_run
        else [],
    }


async def analyze_document_requirement(project_id: str, document_id: str, actor) -> dict:
    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        if not existing["current_version_id"]:
            raise api_error(409, "REQUIREMENT_ANALYSIS_NO_VERSION", "请先归并生成需求工作稿后再分析。")

        open_conflicts = document_repo.list_conflicts(db, document_id, status="open")
        if open_conflicts:
            raise api_error(409, "REQUIREMENT_ANALYSIS_CONFLICT_BLOCKED", "存在未解决的需求归并冲突，不能开始分析。")

        version = document_repo.find_version(db, existing["current_version_id"])
        if not version:
            raise api_error(409, "DOCUMENT_VERSION_NOT_FOUND", "当前需求版本不存在。")

        markdown_path = resolve_stored_path(version["file_path"]) or Path(version["file_path"])
        if not markdown_path.exists():
            raise api_error(409, "DOCUMENT_VERSION_FILE_MISSING", "当前需求版本文件不存在。")
        markdown_content = markdown_path.read_text(encoding="utf-8")

    analysis_input = RequirementAnalysisInput(
        project_id=project_id,
        document_id=document_id,
        document_name=existing["name"],
        version_id=version["id"],
        version_no=version["version_no"],
        markdown_content=markdown_content,
    )
    try:
        analysis_output = await requirement_analysis_service.run_requirement_analysis(analysis_input)
    except Exception as exc:
        raise api_error(502, "REQUIREMENT_ANALYSIS_AGENT_FAILED", f"需求分析智能体运行失败：{exc}") from exc

    analysis_id = f"reqana-{secrets.token_hex(8)}"
    output_data = analysis_output.model_dump()
    with connect() as db:
        document_repo.create_requirement_analysis(
            db,
            analysis_id=analysis_id,
            project_id=project_id,
            document_id=document_id,
            version_id=version["id"],
            status=analysis_output.status,
            analysis_summary=analysis_output.analysis_summary,
            output_json=output_data,
            quality_result=analysis_output.quality_gate.result,
            testability_score=analysis_output.quality_gate.testability_score,
            created_by=actor["id"],
        )

    result = {
        "id": analysis_id,
        "document_id": document_id,
        "version_id": version["id"],
        **output_data,
    }
    operation_log_service.record_success(
        log_type="agent",
        module="requirement",
        action="run",
        object_type="requirement_analysis",
        object_id=analysis_id,
        object_name=existing["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="agent",
        summary=f"执行需求分析：{existing['name']}",
        after={"status": analysis_output.status, "quality_result": analysis_output.quality_gate.result},
    )
    return result


def get_latest_requirement_analysis(project_id: str, document_id: str, actor) -> dict:
    _ = actor
    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        row = document_repo.find_latest_requirement_analysis(db, document_id)
        if not row:
            return {"analysis": None}
        output = json.loads(row["output_json"])
        return {
            "analysis": {
                "id": row["id"],
                "project_id": row["project_id"],
                "document_id": row["document_id"],
                "version_id": row["version_id"],
                "status": row["status"],
                "analysis_summary": row["analysis_summary"],
                "quality_result": row["quality_result"],
                "testability_score": row["testability_score"],
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "output": output,
            }
        }


async def merge_document_markdown(
    project_id: str,
    document_id: str,
    actor,
    *,
    confirm_preview_id: str = "",
    force_rebuild: bool = False,
) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
    action = "confirm" if confirm_preview_id else "merge"
    try:
        result = await document_merge_orchestrator.merge_document_markdown(
            project_id,
            document_id,
            actor,
            confirm_preview_id=confirm_preview_id,
            force_rebuild=force_rebuild,
        )
    except Exception as exc:
        failure_reason = _exception_message(exc)
        operation_log_service.record_failure(
            log_type="audit",
            module="requirement",
            action=action,
            object_type="requirement",
            object_id=document_id,
            object_name=document["name"] if document else document_id,
            project_id=project_id,
            actor_id=actor["id"],
            actor_name=operation_log_service.actor_display_name(actor),
            source="web",
            failure_reason=failure_reason,
            summary=f"需求归并失败：{document['name'] if document else document_id}",
            after={
                "confirm_preview_id": confirm_preview_id,
                "force_rebuild": force_rebuild,
                "failure_reason": failure_reason,
            },
        )
        raise
    status = result.get("status", "")
    operation_log_service.record_success(
        log_type="audit",
        module="requirement",
        action=action,
        object_type="requirement",
        object_id=document_id,
        object_name=document["name"] if document else document_id,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"需求归并{_merge_status_label(status)}：{document['name'] if document else document_id}",
        after={
            "status": status,
            "version_id": result.get("version_id"),
            "version_no": result.get("version_no"),
            "preview_id": result.get("preview_id"),
            "conflict_count": result.get("conflict_count"),
            "merge_summary": result.get("merge_summary", ""),
        },
    )
    return result


def list_document_conflicts(project_id: str, document_id: str, actor) -> list[dict]:
    return document_merge_orchestrator.list_document_conflicts(project_id, document_id, actor)


def resolve_document_conflict(
    project_id: str,
    document_id: str,
    conflict_id: str,
    *,
    resolution: str,
    resolution_type: str,
    actor,
) -> dict:
    return document_merge_orchestrator.resolve_document_conflict(
        project_id,
        document_id,
        conflict_id,
        resolution=resolution,
        resolution_type=resolution_type,
        actor=actor,
    )



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
        markdown_path = _version_markdown_path(project_id, document_id, version_no)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(payload.markdown_content, encoding="utf-8")

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


def delete_source_file(mapping_id: str, actor) -> dict:
    return document_file_service.delete_source_file(mapping_id, actor)


def delete_document(project_id: str, document_id: str, actor) -> dict:
    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        document_dir = project_requirement_dir(project_id, document_id)
        snapshot = {"name": existing["name"], "status": existing["status"], "current_version_id": existing["current_version_id"]}
        document_repo.delete_graph(db, document_id)

    if document_dir.exists():
        shutil.rmtree(document_dir)

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


def _version_markdown_path(project_id: str, document_id: str, version_no: int) -> Path:
    return project_requirement_dir(project_id, document_id) / "versions" / f"v{version_no}.md"


def _decode_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def _merge_status_label(status: str) -> str:
    return {
        "conflict": "产生冲突",
        "merged": "完成",
        "preview": "生成预览",
    }.get(status, "执行")


def _exception_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("code") or exc.status_code)
        return str(detail)
    return str(exc) or type(exc).__name__
