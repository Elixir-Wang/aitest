import asyncio
import hashlib
import json
import re
import secrets
import shutil
from pathlib import Path

from fastapi import HTTPException
from fastapi import UploadFile
from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import project_requirement_dir, resolve_stored_path, store_path
from app.agents.requirement_analysis.auxiliary_enhancement.service import enhance_requirement_with_auxiliary_articles
from app.agents.requirement_analysis.service_adapter import analyze_requirement as analyze_requirement_with_agent
from app.repositories import document_repo, requirement_analysis_run_repo, requirement_clarification_answer_repo
from app.schemas.document import RequirementAnalysisFinalizeIn, RequirementClarificationAnswerIn, SourceDocumentUpdateIn
from app.schemas.requirement_analysis import (
    RequirementAnalysisInput,
    RequirementAnalysisAuxiliaryDocument,
    RequirementAuxiliaryArticleForEnhancement,
    RequirementAuxiliaryDocument,
    RequirementAuxiliaryEnhancementInput,
    RequirementAuxiliaryEnhancementOutput,
    RequirementEnhancementQuestion,
)
from app.services import operation_log_service, task_service
from app.services.document import file_service as document_file_service
from app.services.document import serializer as document_serializer

DOCUMENT_VERSIONED_STATUS = "versioned"
DOCUMENT_PENDING_REVIEW_STATUS = "pending_review"
CONVERSION_SUCCESS_STATUS = "success"
CONVERSION_FAILED_STATUS = "failed"
REQUIREMENT_ANALYSIS_RUN_TIMEOUT_MINUTES = 120
REQUIREMENT_ANALYSIS_RUN_TIMEOUT_SECONDS = REQUIREMENT_ANALYSIS_RUN_TIMEOUT_MINUTES * 60
REQUIREMENT_AUXILIARY_ENHANCEMENT_ENABLED = False


def list_documents(project_id: str, actor) -> list[dict]:
    task_service.recover_stale_requirement_analysis_runs(project_id=project_id)
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


def get_document_version_detail(project_id: str, document_id: str, version_id: str) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        version = document_repo.find_version(db, version_id)
        if not version or version["document_id"] != document_id:
            raise api_error(404, "DOCUMENT_VERSION_NOT_FOUND", "需求版本不存在。")

        markdown_content = _read_version_markdown(version)
        return {
            **_serialize_version(version),
            "markdown_content": markdown_content,
            "is_current": document["current_version_id"] == version_id,
        }


def switch_document_current_version(project_id: str, document_id: str, version_id: str, actor) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        version = document_repo.find_version(db, version_id)
        if not version or version["document_id"] != document_id:
            raise api_error(404, "DOCUMENT_VERSION_NOT_FOUND", "需求版本不存在。")
        if version["source_action"] not in {"requirement_analysis", "requirement_analysis_finalize"}:
            raise api_error(409, "DOCUMENT_VERSION_NOT_FINAL_REQUIREMENT", "只能切换最终需求版本。")

        markdown_content = _read_version_markdown(version)
        previous_version_id = document["current_version_id"]
        document_repo.update_current_version(db, document_id, version_id, DOCUMENT_VERSIONED_STATUS)

    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="switch_final_requirement_version",
        object_type="requirement",
        object_id=document_id,
        object_name=document["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"切换最终需求版本：{document['name']} -> v{version['version_no']}",
        before={"current_version_id": previous_version_id},
        after={"current_version_id": version_id, "version_no": version["version_no"]},
    )
    return {
        "document": {
            "id": document_id,
            "current_version_id": version_id,
        },
        "version": _serialize_version(version),
        "markdown_content": markdown_content,
    }


def get_document_detail(project_id: str, document_id: str, actor) -> dict:
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


async def analyze_document_requirement(project_id: str, document_id: str, actor) -> dict:
    return await review_primary_requirement_file(project_id, document_id, actor)


def start_requirement_review_run(project_id: str, document_id: str, actor) -> dict:
    actor_data = dict(actor)
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        primary_file = document_repo.find_primary_file_mapping(db, document_id)
        if not primary_file:
            raise api_error(409, "DOCUMENT_PRIMARY_FILE_REQUIRED", "请先选择主需求文件后再进行需求分析。")
        if primary_file["conversion_status"] not in {CONVERSION_SUCCESS_STATUS, "warning"} or not primary_file["markdown_file_path"]:
            raise api_error(409, "DOCUMENT_PRIMARY_FILE_NOT_READY", "请先完成主需求标准文件转换后再进行需求分析。")

        active_run = requirement_analysis_run_repo.find_active_by_document(db, document_id)
        if active_run:
            raise api_error(409, "REQUIREMENT_ANALYSIS_RUN_ACTIVE", "当前需求已有评审任务正在执行，请等待完成后再发起。")

        previous_current_version_id = document["current_version_id"]
        run_id = f"reqrun-{secrets.token_hex(8)}"
        document_repo.clear_current_version(db, document_id, DOCUMENT_PENDING_REVIEW_STATUS)
        requirement_analysis_run_repo.create_run(
            db,
            run_id=run_id,
            project_id=project_id,
            document_id=document_id,
            primary_mapping_id=primary_file["id"],
            status="queued",
            summary="需求分析已提交，等待智能体分析。",
            created_by=actor_data["id"],
        )

    _record_requirement_review_task_event(
        run_id,
        actor_data,
        action="submit_requirement_analysis",
        result="success",
        summary="需求分析已提交，等待智能体分析。",
        status="queued",
        after={
            "status": "queued",
            "current_version_id": None,
            "previous_current_version_id": previous_current_version_id,
        },
    )
    task = task_service.get_task_by_source(actor_data, source_type="requirement_analysis_run", source_id=run_id)
    if task:
        return task
    return {
        "id": f"requirement_analysis:{run_id}",
        "source_type": "requirement_analysis_run",
        "source_id": run_id,
        "project_id": project_id,
        "project_name": "",
        "module": "requirement",
        "module_label": "需求分析",
        "title": document["name"],
        "status": "queued",
        "status_label": "排队中",
        "status_group": "running",
        "summary": "需求分析已提交，等待智能体分析。",
        "created_at": "",
        "updated_at": "",
        "detail_url": f"/projects/{project_id}/requirements/{document_id}",
    }


async def execute_requirement_review_run(run_id: str, actor) -> None:
    actor_data = dict(actor)
    with connect() as db:
        run = requirement_analysis_run_repo.find_run(db, run_id)
        if not run:
            return
        if run["status"] != "queued":
            return
        requirement_analysis_run_repo.update_status(
            db,
            run_id,
            status="running",
            summary="需求分析智能体正在分析。",
        )
        project_id = run["project_id"]
        document_id = run["document_id"]

    _record_requirement_review_task_event(
        run_id,
        actor_data,
        action="start_requirement_analysis",
        result="success",
        summary="需求分析智能体正在分析。",
        status="running",
    )

    try:
        result = await asyncio.wait_for(
            review_primary_requirement_file(project_id, document_id, actor_data, task_id=run_id),
            timeout=REQUIREMENT_ANALYSIS_RUN_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        failure_reason = _requirement_review_timeout_message()
        with connect() as db:
            latest_final_version = document_repo.find_latest_final_requirement_version(db, document_id)
            if latest_final_version:
                document_repo.update_current_version(
                    db,
                    document_id,
                    latest_final_version["id"],
                    DOCUMENT_VERSIONED_STATUS,
                )
            requirement_analysis_run_repo.update_status(
                db,
                run_id,
                status="failed",
                summary="需求分析失败。",
                failure_reason=failure_reason,
            )
        _record_requirement_review_task_event(
            run_id,
            actor_data,
            action="fail_requirement_analysis",
            result="failed",
            summary="需求分析失败。",
            status="failed",
            failure_reason=failure_reason,
        )
        return
    except Exception as exc:
        failure_reason = _exception_message(exc)
        with connect() as db:
            latest_final_version = document_repo.find_latest_final_requirement_version(db, document_id)
            if latest_final_version:
                document_repo.update_current_version(
                    db,
                    document_id,
                    latest_final_version["id"],
                    DOCUMENT_VERSIONED_STATUS,
                )
            requirement_analysis_run_repo.update_status(
                db,
                run_id,
                status="failed",
                summary="需求分析失败。",
                failure_reason=failure_reason,
            )
        _record_requirement_review_task_event(
            run_id,
            actor_data,
            action="fail_requirement_analysis",
            result="failed",
            summary="需求分析失败。",
            status="failed",
            failure_reason=failure_reason,
        )
        return

    status = result["status"]
    if status == "needs_clarification":
        summary = result["analysis_summary"] or "需求分析完成，存在待确认问题。"
        log_result = "partial_success"
    elif status == "blocked":
        summary = result["analysis_summary"] or "需求分析阻塞。"
        log_result = "partial_success"
    else:
        summary = result["analysis_summary"] or "需求分析完成。"
        log_result = "success"

    with connect() as db:
        requirement_analysis_run_repo.attach_analysis(db, run_id, result["id"])
        requirement_analysis_run_repo.update_status(db, run_id, status=status, summary=summary)

    _record_requirement_review_task_event(
        run_id,
        actor_data,
        action="finish_requirement_analysis",
        result=log_result,
        summary=summary,
        status=status,
        after={"analysis_id": result["id"], "status": status},
    )


async def review_primary_requirement_file(project_id: str, document_id: str, actor, *, task_id: str | None = None) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        primary_file = document_repo.find_primary_file_mapping(db, document_id)
        if not primary_file:
            raise api_error(409, "DOCUMENT_PRIMARY_FILE_REQUIRED", "请先选择主需求文件后再进行需求分析。")
        if primary_file["conversion_status"] not in {CONVERSION_SUCCESS_STATUS, "warning"} or not primary_file["markdown_file_path"]:
            raise api_error(409, "DOCUMENT_PRIMARY_FILE_NOT_READY", "请先完成主需求标准文件转换后再进行需求分析。")

        markdown_path = resolve_stored_path(primary_file["markdown_file_path"]) or Path(primary_file["markdown_file_path"])
        if not markdown_path.exists():
            raise api_error(404, "DOCUMENT_MARKDOWN_MISSING", "主需求标准文件不存在。")

        primary_markdown_content = markdown_path.read_text(encoding="utf-8")
        auxiliary_documents = [
            RequirementAnalysisAuxiliaryDocument(
                mapping_id=document.mapping_id,
                filename=document.filename,
                markdown_content=document.markdown_content,
            )
            for document in _collect_auxiliary_documents(db, document_id, primary_file["id"])
        ]

    analysis_input = RequirementAnalysisInput(
        project_id=project_id,
        document_id=document_id,
        document_name=document["name"],
        run_id=task_id or "",
        primary_mapping_id=primary_file["id"],
        primary_filename=primary_file["original_filename"],
        primary_markdown_content=primary_markdown_content,
        auxiliary_documents=auxiliary_documents,
    )
    try:
        analysis_output = await analyze_requirement_with_agent(analysis_input)
    except Exception as exc:
        raise api_error(502, "REQUIREMENT_ANALYSIS_AGENT_FAILED", f"需求分析智能体运行失败：{exc}") from exc

    preliminary_markdown = analysis_output.preliminary_requirement_markdown.strip()
    if not preliminary_markdown:
        raise api_error(502, "REQUIREMENT_ANALYSIS_EMPTY_DRAFT", "需求分析智能体未返回初步需求。")

    analysis_id = f"reqana-{secrets.token_hex(8)}"
    output_data = analysis_output.model_dump()
    output_data.setdefault("analysis_report_markdown", "")
    pending_count = len(output_data.get("clarification_questions", [])) + len(output_data.get("conflicts", []))
    supplement_count = len(output_data.get("applied_supplements", []))
    draft_content_hash = _content_hash(preliminary_markdown)

    with connect() as db:
        document_repo.create_requirement_analysis(
            db,
            analysis_id=analysis_id,
            project_id=project_id,
            document_id=document_id,
            version_id=None,
            primary_mapping_id=primary_file["id"],
            status=analysis_output.status,
            analysis_summary=analysis_output.analysis_summary,
            output_json=output_data,
            quality_result=analysis_output.quality_gate.result,
            testability_score=analysis_output.quality_gate.testability_score,
            draft_content_hash=draft_content_hash,
            created_by=actor["id"],
        )

    result = {
        "id": analysis_id,
        "project_id": project_id,
        "document_id": document_id,
        "version_id": None,
        "primary_mapping_id": primary_file["id"],
        "quality_result": analysis_output.quality_gate.result,
        "testability_score": analysis_output.quality_gate.testability_score,
        "created_by": actor["id"],
        "created_at": "",
        "draft_content_hash": draft_content_hash,
        "finalized_version_id": None,
        "finalized_at": None,
        "finalized_by": None,
        **output_data,
    }
    operation_log_service.record_success(
        log_type="agent",
        module="requirement",
        action="run",
        object_type="requirement_analysis",
        object_id=analysis_id,
        object_name=document["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="agent",
        summary=f"执行需求分析：{document['name']}",
        after={
            "status": analysis_output.status,
            "quality_result": analysis_output.quality_gate.result,
            "supplement_count": supplement_count,
            "pending_count": pending_count,
        },
        task_id=task_id,
    )
    return result


def _record_requirement_review_task_event(
    run_id: str,
    actor,
    *,
    action: str,
    result: str,
    summary: str,
    status: str,
    failure_reason: str = "",
    after: dict | None = None,
) -> None:
    with connect() as db:
        run = requirement_analysis_run_repo.find_run(db, run_id)
    if not run:
        return
    operation_log_service.record_task_event(
        module="requirement",
        action=action,
        object_type="requirement_analysis_run",
        object_id=run_id,
        object_name=run["document_name"],
        project_id=run["project_id"],
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="agent",
        result=result,
        failure_reason=failure_reason,
        summary=summary,
        after=after or {"status": status},
        task_id=run_id,
    )


def _exception_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("code") or exc)
        return str(detail)
    return str(exc) or type(exc).__name__


def _requirement_review_timeout_message() -> str:
    return f"需求分析运行超过 {REQUIREMENT_ANALYSIS_RUN_TIMEOUT_MINUTES} 分钟，已自动标记为失败。"


def get_latest_requirement_analysis(project_id: str, document_id: str, actor) -> dict:
    _ = actor
    task_service.recover_stale_requirement_analysis_runs(project_id=project_id)
    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        latest_run = document_repo.find_latest_requirement_analysis_run(db, document_id)
        if latest_run:
            if not latest_run["analysis_id"]:
                return {"analysis": None}
            run_analysis = document_repo.find_requirement_analysis(db, latest_run["analysis_id"])
            return {"analysis": _serialize_requirement_analysis(run_analysis) if run_analysis else None}
        row = document_repo.find_latest_requirement_analysis(db, document_id)
        if not row:
            return {"analysis": None}
        return {"analysis": _serialize_requirement_analysis(row)}


async def enhance_requirement_analysis_with_auxiliary_documents(
    project_id: str,
    document_id: str,
    analysis_id: str,
    actor,
) -> dict:
    if not REQUIREMENT_AUXILIARY_ENHANCEMENT_ENABLED:
        raise api_error(
            409,
            "REQUIREMENT_AUXILIARY_ENHANCEMENT_DISABLED",
            "辅助文档增强智能体暂未接入需求分析流程。",
        )

    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        analysis = document_repo.find_requirement_analysis(db, analysis_id)
        if not analysis or analysis["project_id"] != project_id or analysis["document_id"] != document_id:
            raise api_error(404, "REQUIREMENT_ANALYSIS_NOT_FOUND", "需求分析结果不存在。")
        if analysis["finalized_version_id"]:
            raise api_error(409, "REQUIREMENT_ANALYSIS_FINALIZED", "该初步需求已转为最终需求，不能继续增强。")

        primary_mapping_id = analysis["primary_mapping_id"] or ""
        primary_file = document_repo.find_primary_file_mapping(db, document_id)
        if primary_mapping_id and (not primary_file or primary_file["id"] != primary_mapping_id):
            raise api_error(409, "REQUIREMENT_ANALYSIS_PRIMARY_CHANGED", "主需求文件已变更，请重新执行需求分析。")

        output = json.loads(analysis["output_json"])
        questions = _requirement_enhancement_questions(output)
        if not questions:
            raise api_error(409, "REQUIREMENT_ANALYSIS_NO_PENDING_QUESTIONS", "当前需求分析没有可增强的待确认问题。")
        auxiliary_documents = _collect_auxiliary_documents(db, document_id, primary_mapping_id)

    if not auxiliary_documents:
        raise api_error(409, "REQUIREMENT_ANALYSIS_NO_AUXILIARY_DOCUMENTS", "当前需求没有可用于增强的辅助文档。")

    enhancement_input = RequirementAuxiliaryEnhancementInput(
        project_id=project_id,
        document_id=document_id,
        analysis_id=analysis_id,
        primary_mapping_id=primary_mapping_id,
        primary_filename=primary_file["original_filename"] if primary_file else "",
        questions=questions,
        auxiliary_articles=[
            RequirementAuxiliaryArticleForEnhancement(
                mapping_id=document.mapping_id,
                filename=document.filename,
                markdown_content=document.markdown_content,
            )
            for document in auxiliary_documents
        ],
    )

    try:
        enhancement_output = await enhance_requirement_with_auxiliary_articles(enhancement_input)
    except Exception as exc:
        raise api_error(502, "REQUIREMENT_AUXILIARY_ENHANCEMENT_FAILED", f"辅助文档增强智能体运行失败：{exc}") from exc

    _validate_auxiliary_enhancement_sources(enhancement_output, enhancement_input.auxiliary_articles)
    merged_output = _merge_requirement_auxiliary_enhancement(output, enhancement_output)
    quality_gate = merged_output.get("quality_gate") or {}
    preliminary_markdown = str(merged_output.get("preliminary_requirement_markdown") or "").strip()
    draft_content_hash = _content_hash(preliminary_markdown)

    with connect() as db:
        document_repo.update_requirement_analysis_output(
            db,
            analysis_id=analysis_id,
            status=str(merged_output.get("status") or analysis["status"]),
            analysis_summary=str(merged_output.get("analysis_summary") or analysis["analysis_summary"]),
            output_json=merged_output,
            quality_result=str(quality_gate.get("result") or analysis["quality_result"]),
            testability_score=int(quality_gate.get("testability_score") or analysis["testability_score"] or 0),
            draft_content_hash=draft_content_hash,
        )
        updated_analysis = document_repo.find_requirement_analysis(db, analysis_id)

    operation_log_service.record_change(
        log_type="agent",
        module="requirement",
        action="enhance_requirement_analysis",
        object_type="requirement_analysis",
        object_id=analysis_id,
        object_name=document["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="agent",
        summary=f"从辅助文档增强需求分析：{document['name']}",
        before={"analysis_id": analysis_id},
        after={
            "applied_supplement_count": len(enhancement_output.applied_supplements),
            "resolved_question_count": len(enhancement_output.resolved_question_options),
            "new_conflict_count": len(enhancement_output.new_conflicts),
        },
    )

    return {"analysis": _serialize_requirement_analysis(updated_analysis)}


def list_requirement_clarification_answers(project_id: str, document_id: str, analysis_id: str, actor) -> dict:
    _ = actor
    with connect() as db:
        analysis = document_repo.find_requirement_analysis(db, analysis_id)
        if not analysis or analysis["project_id"] != project_id or analysis["document_id"] != document_id:
            raise api_error(404, "REQUIREMENT_ANALYSIS_NOT_FOUND", "需求分析结果不存在。")
        rows = requirement_clarification_answer_repo.list_answers(db, analysis_id)
        return {"answers": [_serialize_requirement_clarification_answer(row) for row in rows]}


def save_requirement_clarification_answer(
    project_id: str,
    document_id: str,
    analysis_id: str,
    payload: RequirementClarificationAnswerIn,
    actor,
) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        analysis = document_repo.find_requirement_analysis(db, analysis_id)
        if not analysis or analysis["project_id"] != project_id or analysis["document_id"] != document_id:
            raise api_error(404, "REQUIREMENT_ANALYSIS_NOT_FOUND", "需求分析结果不存在。")
        if analysis["finalized_version_id"]:
            raise api_error(409, "REQUIREMENT_ANALYSIS_FINALIZED", "该初步需求已转为最终需求，不能继续修改。")

        output = json.loads(analysis["output_json"])
        question, question_bucket, question_index = _find_requirement_analysis_question(output, payload.question_id)
        if question is None or question_bucket is None or question_index is None:
            raise api_error(404, "REQUIREMENT_CLARIFICATION_QUESTION_NOT_FOUND", "待确认问题不存在。")

        answer_markdown, selected_option_id, user_note = _resolve_clarification_answer(question, payload)
        apply_status = "not_applicable" if payload.answer_type == "defer" else "applied"
        insertion_anchor = ""
        failure_reason = ""
        preliminary_markdown = str(output.get("preliminary_requirement_markdown") or "").strip()
        if not preliminary_markdown:
            raise api_error(409, "REQUIREMENT_ANALYSIS_EMPTY_DRAFT", "初步需求为空，不能写入答复。")

        if apply_status == "applied":
            preliminary_markdown, insertion_anchor = _apply_clarification_answer_to_markdown(
                preliminary_markdown,
                question=question,
                answer_markdown=answer_markdown,
            )
            output["preliminary_requirement_markdown"] = preliminary_markdown

        answer_id = f"reqanswer-{secrets.token_hex(8)}"
        answer_snapshot = {
            "id": answer_id,
            "question_id": payload.question_id,
            "answer_type": payload.answer_type,
            "selected_option_id": selected_option_id,
            "answer_markdown": answer_markdown,
            "user_note": user_note,
            "apply_status": apply_status,
            "insertion_anchor": insertion_anchor,
            "failure_reason": failure_reason,
        }
        output[question_bucket][question_index] = {
            **question,
            "answer": answer_snapshot,
        }

        quality_gate = output.get("quality_gate") or {}
        draft_content_hash = _content_hash(str(output.get("preliminary_requirement_markdown") or ""))
        document_repo.update_requirement_analysis_output(
            db,
            analysis_id=analysis_id,
            status=str(output.get("status") or analysis["status"]),
            analysis_summary=str(output.get("analysis_summary") or analysis["analysis_summary"]),
            output_json=output,
            quality_result=str(quality_gate.get("result") or analysis["quality_result"]),
            testability_score=int(quality_gate.get("testability_score") or analysis["testability_score"] or 0),
            draft_content_hash=draft_content_hash,
        )
        requirement_clarification_answer_repo.upsert_answer(
            db,
            answer_id=answer_id,
            project_id=project_id,
            document_id=document_id,
            analysis_id=analysis_id,
            question_id=payload.question_id,
            answer_type=payload.answer_type,
            selected_option_id=selected_option_id,
            answer_markdown=answer_markdown,
            user_note=user_note,
            apply_status=apply_status,
            insertion_anchor=insertion_anchor,
            failure_reason=failure_reason,
            created_by=actor["id"],
        )
        saved_answer = requirement_clarification_answer_repo.find_answer(db, analysis_id, payload.question_id)
        updated_analysis = document_repo.find_requirement_analysis(db, analysis_id)

    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="answer_requirement_clarification",
        object_type="requirement_analysis",
        object_id=analysis_id,
        object_name=document["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"答复待确认问题：{question.get('question', payload.question_id)}",
        before={"question_id": payload.question_id},
        after={
            "question_id": payload.question_id,
            "answer_type": payload.answer_type,
            "apply_status": apply_status,
            "insertion_anchor": insertion_anchor,
        },
    )

    return {
        "answer": _serialize_requirement_clarification_answer(saved_answer),
        "analysis": _serialize_requirement_analysis(updated_analysis),
    }


def finalize_requirement_analysis(
    project_id: str,
    document_id: str,
    payload: RequirementAnalysisFinalizeIn,
    actor,
) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        analysis = document_repo.find_requirement_analysis(db, payload.analysis_id)
        if not analysis or analysis["project_id"] != project_id or analysis["document_id"] != document_id:
            raise api_error(404, "REQUIREMENT_ANALYSIS_NOT_FOUND", "需求分析结果不存在。")

        latest = document_repo.find_latest_requirement_analysis(db, document_id)
        if not latest or latest["id"] != analysis["id"]:
            raise api_error(409, "REQUIREMENT_ANALYSIS_STALE", "该需求分析不是最新结果，请刷新后重试。")
        latest_run = document_repo.find_latest_requirement_analysis_run(db, document_id)
        if latest_run and latest_run["analysis_id"] != analysis["id"]:
            raise api_error(409, "REQUIREMENT_ANALYSIS_STALE", "该需求分析不是最新结果，请刷新后重试。")

        output = json.loads(analysis["output_json"])
        preliminary_markdown = str(output.get("preliminary_requirement_markdown") or "").strip()
        if not preliminary_markdown:
            raise api_error(409, "REQUIREMENT_ANALYSIS_EMPTY_DRAFT", "初步需求为空，不能转为最终需求。")

        current_hash = _content_hash(preliminary_markdown)
        stored_hash = analysis["draft_content_hash"] or current_hash
        finalized_version_id = analysis["finalized_version_id"]
        if finalized_version_id:
            if stored_hash != current_hash:
                raise api_error(409, "REQUIREMENT_ANALYSIS_DRAFT_CHANGED", "初步需求内容已变化，请重新执行需求分析。")
            finalized_version = document_repo.find_version(db, finalized_version_id)
            if finalized_version:
                finalized_path = resolve_stored_path(finalized_version["file_path"]) or Path(finalized_version["file_path"])
                markdown_content = finalized_path.read_text(encoding="utf-8") if finalized_path.exists() else preliminary_markdown
                return {
                    "analysis": _serialize_requirement_analysis(analysis),
                    "version": _serialize_version(finalized_version),
                    "document": {
                        "id": document["id"],
                        "current_version_id": document["current_version_id"],
                    },
                    "markdown_content": markdown_content,
                }

        if analysis["status"] == "blocked" or analysis["quality_result"] == "blocked":
            raise api_error(409, "REQUIREMENT_ANALYSIS_BLOCKED", "存在阻塞问题，不能转为最终需求。")

        quality_gate = output.get("quality_gate") or {}
        if quality_gate.get("result") == "blocked":
            raise api_error(409, "REQUIREMENT_ANALYSIS_BLOCKED", "存在阻塞问题，不能转为最终需求。")

        primary_mapping_id = analysis["primary_mapping_id"] or ""
        if primary_mapping_id:
            current_primary = document_repo.find_primary_file_mapping(db, document_id)
            if not current_primary or current_primary["id"] != primary_mapping_id:
                raise api_error(409, "REQUIREMENT_ANALYSIS_PRIMARY_CHANGED", "主需求文件已变更，请重新执行需求分析。")

        unresolved_count = _active_unresolved_count(output)
        has_quality_warning = (
            analysis["quality_result"] == "warning"
            or quality_gate.get("result") == "warning"
            or bool(quality_gate.get("warning_issues") or [])
        )
        if (unresolved_count > 0 or has_quality_warning) and not payload.confirm_unresolved:
            raise api_error(
                409,
                "REQUIREMENT_ANALYSIS_CONFIRM_REQUIRED",
                "当前初步需求仍存在待确认问题或质量警告，请确认后再转为最终需求。",
            )

        supplement_count = len(output.get("applied_supplements") or [])
        version_id = f"docver-{secrets.token_hex(8)}"
        version_no = document_repo.next_version_no(db, document_id)
        version_path = _version_markdown_path(project_id, document_id, version_no)
        version_path.parent.mkdir(parents=True, exist_ok=True)
        version_path.write_text(preliminary_markdown + "\n", encoding="utf-8")
        diff_summary = f"由需求分析结果生成最终需求。辅助补强 {supplement_count} 项，待确认 {unresolved_count} 项。"

        document_repo.create_version(
            db,
            version_id=version_id,
            document_id=document_id,
            version_no=version_no,
            file_path=store_path(version_path) or str(version_path),
            source_action="requirement_analysis_finalize",
            change_summary="初步需求转为最终需求",
            diff_summary=diff_summary,
            created_by=actor["id"],
        )
        document_repo.update_current_version(db, document_id, version_id, DOCUMENT_VERSIONED_STATUS)
        document_repo.mark_requirement_analysis_finalized(
            db,
            analysis_id=analysis["id"],
            version_id=version_id,
            finalized_by=actor["id"],
        )
        document_repo.create_document_version_change_log(
            db,
            log_id=f"doclog-{secrets.token_hex(8)}",
            document_id=document_id,
            version_id=version_id,
            source_action="requirement_analysis_finalize",
            change_summary="初步需求转为最终需求",
            diff_summary=diff_summary,
            affected_modules=[],
            source_mapping_ids=[primary_mapping_id] if primary_mapping_id else [],
            created_by=actor["id"],
        )
        if primary_mapping_id:
            document_repo.link_file_mapping_to_version(db, primary_mapping_id, version_id)

        finalized_analysis = document_repo.find_requirement_analysis(db, analysis["id"])
        version = document_repo.find_version(db, version_id)

    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="finalize_requirement_analysis",
        object_type="requirement_analysis",
        object_id=payload.analysis_id,
        object_name=document["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"初步需求转为最终需求：{document['name']}",
        before={"current_version_id": document["current_version_id"], "analysis_id": payload.analysis_id},
        after={"current_version_id": version_id, "version_no": version_no},
    )

    return {
        "analysis": _serialize_requirement_analysis(finalized_analysis),
        "version": _serialize_version(version),
        "document": {
            "id": document_id,
            "current_version_id": version_id,
        },
        "markdown_content": preliminary_markdown + "\n",
    }


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
        markdown_path = _version_markdown_path(project_id, document_id, version_no)
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


def _collect_auxiliary_documents(db, document_id: str, primary_mapping_id: str) -> list[RequirementAuxiliaryDocument]:
    auxiliary_documents: list[RequirementAuxiliaryDocument] = []
    for row in document_repo.list_file_mappings(db, document_id):
        if row["id"] == primary_mapping_id:
            continue
        if row["conversion_status"] not in {CONVERSION_SUCCESS_STATUS, "warning"}:
            continue
        markdown_path_value = row["markdown_file_path"]
        if not markdown_path_value:
            continue
        markdown_path = resolve_stored_path(markdown_path_value) or Path(markdown_path_value)
        if not markdown_path.exists():
            continue
        markdown_content = markdown_path.read_text(encoding="utf-8")
        if not markdown_content.strip():
            continue
        auxiliary_documents.append(
            RequirementAuxiliaryDocument(
                mapping_id=row["id"],
                filename=row["original_filename"],
                markdown_content=markdown_content,
            )
        )
    return auxiliary_documents


def _requirement_enhancement_questions(output: dict) -> list[RequirementEnhancementQuestion]:
    questions: list[RequirementEnhancementQuestion] = []
    seen_ids: set[str] = set()
    for bucket in ("clarification_questions", "conflicts"):
        for index, item in enumerate(output.get(bucket) or []):
            question_id = str(item.get("id") or f"{bucket}-{index + 1}")
            if question_id in seen_ids:
                continue
            seen_ids.add(question_id)
            questions.append(
                RequirementEnhancementQuestion(
                    id=question_id,
                    module_key=str(item.get("module_key") or ""),
                    module_name=str(item.get("module_name") or ""),
                    question=str(item.get("question") or item.get("description") or ""),
                    impact=str(item.get("impact") or ""),
                    severity=str(item.get("severity") or "major"),
                    primary_excerpt=str(item.get("primary_excerpt") or item.get("source_excerpt") or ""),
                )
            )
    return [question for question in questions if question.question.strip()]


def _merge_requirement_auxiliary_enhancement(
    output: dict,
    enhancement: RequirementAuxiliaryEnhancementOutput,
) -> dict:
    merged = json.loads(json.dumps(output, ensure_ascii=False))
    merged.setdefault("applied_supplements", [])
    merged.setdefault("clarification_questions", [])
    merged.setdefault("conflicts", [])
    merged.setdefault("next_actions", [])

    existing_supplement_ids = {str(item.get("id") or "") for item in merged["applied_supplements"]}
    for supplement in enhancement.applied_supplements:
        item = supplement.model_dump()
        if item["id"] not in existing_supplement_ids:
            merged["applied_supplements"].append(item)
            existing_supplement_ids.add(item["id"])

    question_index = {
        str(item.get("id") or ""): item
        for item in [*merged.get("clarification_questions", []), *merged.get("conflicts", [])]
    }
    for resolution in enhancement.resolved_question_options:
        question = question_index.get(resolution.question_id)
        if not question:
            continue
        if resolution.recommended_options:
            question["recommended_options"] = [option.model_dump() for option in resolution.recommended_options]
        if resolution.evidence:
            question["evidence"] = [evidence.model_dump() for evidence in resolution.evidence]
        question["auxiliary_resolution"] = {
            "resolution": resolution.resolution,
            "reason": resolution.reason,
        }

    existing_conflict_ids = {str(item.get("id") or "") for item in merged["conflicts"]}
    for conflict in enhancement.new_conflicts:
        item = conflict.model_dump()
        if item["id"] not in existing_conflict_ids:
            merged["conflicts"].append(item)
            existing_conflict_ids.add(item["id"])

    summary = enhancement.enhancement_summary.strip()
    if summary:
        current_summary = str(merged.get("analysis_summary") or "").strip()
        merged["analysis_summary"] = f"{current_summary}\n\n辅助文档增强：{summary}".strip()

    if enhancement.applied_supplements:
        merged["next_actions"] = [
            *merged.get("next_actions", []),
            f"已从辅助文档增强 {len(enhancement.applied_supplements)} 项，请确认补强内容是否可进入最终需求。",
        ]

    quality_gate = merged.get("quality_gate") or {}
    if merged.get("conflicts"):
        merged["status"] = "blocked" if quality_gate.get("result") == "blocked" else "needs_clarification"
    elif merged.get("clarification_questions"):
        merged["status"] = "needs_clarification"
    else:
        merged["status"] = "completed"
    return merged


def _validate_auxiliary_enhancement_sources(
    enhancement: RequirementAuxiliaryEnhancementOutput,
    articles: list[RequirementAuxiliaryArticleForEnhancement],
) -> None:
    mapping_ids = {article.mapping_id for article in articles}
    filenames = {article.filename for article in articles}

    for evidence in _iter_auxiliary_enhancement_evidence(enhancement):
        if evidence.mapping_id and evidence.mapping_id not in mapping_ids:
            raise api_error(502, "REQUIREMENT_AUXILIARY_ENHANCEMENT_INVALID_SOURCE", "辅助文档增强返回了输入之外的来源。")
        if evidence.filename and evidence.filename not in filenames:
            raise api_error(502, "REQUIREMENT_AUXILIARY_ENHANCEMENT_INVALID_SOURCE", "辅助文档增强返回了输入之外的来源。")


def _iter_auxiliary_enhancement_evidence(enhancement: RequirementAuxiliaryEnhancementOutput):
    for supplement in enhancement.applied_supplements:
        yield supplement.evidence
    for resolution in enhancement.resolved_question_options:
        yield from resolution.evidence
    for conflict in enhancement.new_conflicts:
        yield from conflict.evidence


def _serialize_requirement_analysis(row) -> dict:
    output = json.loads(row["output_json"])
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "document_id": row["document_id"],
        "version_id": row["version_id"],
        "primary_mapping_id": row["primary_mapping_id"],
        "status": row["status"],
        "analysis_summary": row["analysis_summary"],
        "quality_result": row["quality_result"],
        "testability_score": row["testability_score"],
        "draft_content_hash": row["draft_content_hash"],
        "finalized_version_id": row["finalized_version_id"],
        "finalized_at": row["finalized_at"],
        "finalized_by": row["finalized_by"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "output": output,
    }


def _serialize_requirement_clarification_answer(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "document_id": row["document_id"],
        "analysis_id": row["analysis_id"],
        "question_id": row["question_id"],
        "answer_type": row["answer_type"],
        "selected_option_id": row["selected_option_id"],
        "answer_markdown": row["answer_markdown"],
        "user_note": row["user_note"],
        "apply_status": row["apply_status"],
        "insertion_anchor": row["insertion_anchor"],
        "failure_reason": row["failure_reason"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_version(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "version_no": row["version_no"],
        "file_path": row["file_path"],
        "source_action": row["source_action"],
        "change_summary": row["change_summary"],
        "diff_summary": row["diff_summary"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


def _read_version_markdown(version) -> str:
    markdown_path = resolve_stored_path(version["file_path"]) or Path(version["file_path"])
    if not markdown_path.exists():
        raise api_error(404, "DOCUMENT_VERSION_FILE_NOT_FOUND", "需求版本文件不存在。")
    return markdown_path.read_text(encoding="utf-8")


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def _find_requirement_analysis_question(output: dict, question_id: str) -> tuple[dict | None, str | None, int | None]:
    for bucket in ("clarification_questions", "conflicts"):
        items = output.get(bucket) or []
        for index, item in enumerate(items):
            if item.get("id") == question_id:
                return item, bucket, index
    return None, None, None


def _resolve_clarification_answer(question: dict, payload: RequirementClarificationAnswerIn) -> tuple[str, str, str]:
    if payload.answer_type == "defer":
        return "", "", payload.custom_answer.strip()
    if payload.answer_type == "custom":
        answer = payload.custom_answer.strip()
        if not answer:
            raise api_error(422, "REQUIREMENT_CLARIFICATION_CUSTOM_ANSWER_REQUIRED", "请填写自定义答复。")
        return answer, payload.selected_option_id.strip(), answer
    selected_option_id = payload.selected_option_id.strip()
    if not selected_option_id:
        raise api_error(422, "REQUIREMENT_CLARIFICATION_OPTION_REQUIRED", "请选择推荐选项。")
    for option in question.get("recommended_options") or []:
        if option.get("id") == selected_option_id:
            answer = str(option.get("answer_markdown") or "").strip()
            if not answer:
                raise api_error(422, "REQUIREMENT_CLARIFICATION_OPTION_EMPTY", "推荐选项缺少可写入内容。")
            return answer, selected_option_id, payload.custom_answer.strip()
    raise api_error(404, "REQUIREMENT_CLARIFICATION_OPTION_NOT_FOUND", "推荐选项不存在。")


def _apply_clarification_answer_to_markdown(
    markdown_content: str,
    *,
    question: dict,
    answer_markdown: str,
) -> tuple[str, str]:
    question_id = question.get("id") or ""
    module_name = str(question.get("module_name") or "").strip()
    module_key = str(question.get("module_key") or "").strip()
    question_text = str(question.get("question") or "").strip()
    block = _clarification_answer_markdown_block(question_id, question_text, answer_markdown)
    without_old_block = _replace_or_remove_clarification_block(markdown_content, question_id, replacement="")
    insertion_anchor = module_name or module_key or "人工确认补充"
    if _has_clarification_section(without_old_block):
        return _append_to_clarification_section(without_old_block, block), insertion_anchor
    if module_name or module_key:
        updated = _append_to_matching_section(without_old_block, block, [module_name, module_key])
        if updated != without_old_block:
            return updated, insertion_anchor
    separator = "\n\n" if without_old_block.strip() else ""
    return f"{without_old_block.rstrip()}{separator}## 人工确认补充\n\n{block}\n", "人工确认补充"


def _clarification_answer_markdown_block(question_id: str, question: str, answer_markdown: str) -> str:
    return "\n".join(
        [
            f"<!-- clarification-answer:{question_id}:start -->",
            "> 人工确认",
            f"> 问题：{question}",
            "> 答案：",
            *[f"> {line}" if line else ">" for line in answer_markdown.strip().splitlines()],
            f"<!-- clarification-answer:{question_id}:end -->",
        ]
    )


def _replace_or_remove_clarification_block(markdown_content: str, question_id: str, *, replacement: str) -> str:
    pattern = re.compile(
        rf"\n*<!-- clarification-answer:{re.escape(question_id)}:start -->.*?<!-- clarification-answer:{re.escape(question_id)}:end -->\n*",
        re.DOTALL,
    )
    return pattern.sub(f"\n\n{replacement}\n\n" if replacement else "\n", markdown_content).strip()


def _has_clarification_section(markdown_content: str) -> bool:
    return bool(re.search(r"^##\s+人工确认补充\s*$", markdown_content, flags=re.MULTILINE))


def _append_to_clarification_section(markdown_content: str, block: str) -> str:
    return f"{markdown_content.rstrip()}\n\n{block}\n"


def _append_to_matching_section(markdown_content: str, block: str, candidates: list[str]) -> str:
    lines = markdown_content.splitlines()
    heading_index = None
    heading_level = None
    normalized_candidates = [candidate for candidate in candidates if candidate]
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        title = match.group(2)
        if any(candidate in title for candidate in normalized_candidates):
            heading_index = index
            heading_level = len(match.group(1))
            break
    if heading_index is None or heading_level is None:
        return markdown_content
    insert_at = len(lines)
    for index in range(heading_index + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+.+?\s*$", lines[index])
        if match and len(match.group(1)) <= heading_level:
            insert_at = index
            break
    next_lines = [*lines[:insert_at], "", block, "", *lines[insert_at:]]
    return "\n".join(next_lines).strip() + "\n"


def _active_unresolved_count(output: dict) -> int:
    count = 0
    for item in [*(output.get("clarification_questions") or []), *(output.get("conflicts") or [])]:
        answer = item.get("answer") or {}
        if answer.get("apply_status") in {"applied", "not_applicable"}:
            continue
        count += 1
    return count


def _version_markdown_path(project_id: str, document_id: str, version_no: int) -> Path:
    return project_requirement_dir(project_id, document_id) / "versions" / f"v{version_no}.md"
