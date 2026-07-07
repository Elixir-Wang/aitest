"""需求分析任务（run）的生命周期：启动、停止、取消、查询、failure 恢复。

包括 task_service 的回调、定时取消、failure/cancel 语义、与 documents 子模块的协作。
所有需要读写 ``requirement_analysis_runs`` 表的服务都集中在此。
"""
from __future__ import annotations

import asyncio
import secrets
import shutil
from pathlib import Path

from fastapi import HTTPException

from app.agents.requirement_analysis.service import (
    build_requirement_analysis_output_json,
    next_analysis_id,
    normalize_analysis_output_markdown,
    write_requirement_analysis_artifacts,
)
from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import project_requirement_dir, resolve_stored_path
from app.repositories import (
    document_repo,
    requirement_analysis_run_repo,
    requirement_clarification_answer_repo,
)
from app.services import operation_log_service, task_service

from ._constants import (
    DOCUMENT_PENDING_REVIEW_STATUS,
    DOCUMENT_VERSIONED_STATUS,
    REQUIREMENT_ANALYSIS_RUN_TIMEOUT_MINUTES,
    REQUIREMENT_ANALYSIS_RUN_TIMEOUT_SECONDS,
)
from .analysis import analyze_requirement_with_agent
from .serdes import (
    serialize_requirement_analysis,
    serialize_requirement_analysis_run,
    serialize_requirement_clarification_answer,
)


class RequirementAnalysisCancelledError(Exception):
    pass


def start_requirement_review_run(project_id: str, document_id: str, actor) -> dict:
    actor_data = dict(actor)
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        primary_file = document_repo.find_primary_file_mapping(db, document_id)
        if not primary_file:
            raise api_error(409, "DOCUMENT_PRIMARY_FILE_REQUIRED", "请先选择主需求文件后再进行需求分析。")
        if primary_file["conversion_status"] not in {"success", "warning"} or not primary_file["markdown_file_path"]:
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
            previous_current_version_id=previous_current_version_id,
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


def stop_requirement_analysis_run(project_id: str, document_id: str, run_id: str, actor) -> dict:
    actor_data = dict(actor)
    with connect() as db:
        run = requirement_analysis_run_repo.find_run(db, run_id)
        if not run or run["project_id"] != project_id or run["document_id"] != document_id:
            raise api_error(404, "NOT_FOUND", "需求分析任务不存在。")

        status = run["status"]
        if status == "cancelled":
            return _requirement_analysis_run_task(run_id, actor_data, run)
        if status in {"completed", "needs_clarification", "blocked", "failed"}:
            raise api_error(409, "REQUIREMENT_ANALYSIS_NOT_RUNNING", "只有排队中或分析中的任务可以停止。")
        if status == "stopping":
            _finalize_cancelled_requirement_analysis_run(run_id, actor_data)
            with connect() as db:
                run = requirement_analysis_run_repo.find_run(db, run_id)
            return _requirement_analysis_run_task(run_id, actor_data, run)

        if status == "queued":
            marked = requirement_analysis_run_repo.try_mark_stopping(db, run_id, from_statuses=("queued",))
        else:
            marked = requirement_analysis_run_repo.try_mark_stopping(db, run_id, from_statuses=("running",))

    if not marked:
        with connect() as db:
            run = requirement_analysis_run_repo.find_run(db, run_id)
        if not run:
            raise api_error(404, "NOT_FOUND", "需求分析任务不存在。")
        if run["status"] == "stopping":
            _finalize_cancelled_requirement_analysis_run(run_id, actor_data)
            with connect() as db:
                run = requirement_analysis_run_repo.find_run(db, run_id)
        return _requirement_analysis_run_task(run_id, actor_data, run)

    _finalize_cancelled_requirement_analysis_run(run_id, actor_data)

    with connect() as db:
        run = requirement_analysis_run_repo.find_run(db, run_id)
    return _requirement_analysis_run_task(run_id, actor_data, run)


async def execute_requirement_review_run(run_id: str, actor) -> None:
    actor_data = dict(actor)
    with connect() as db:
        run = requirement_analysis_run_repo.find_run(db, run_id)
        if not run:
            return
        if not requirement_analysis_run_repo.try_mark_running(db, run_id):
            return
        project_id = run["project_id"]
        document_id = run["document_id"]

    if _requirement_analysis_run_is_stopping(run_id):
        _finalize_cancelled_requirement_analysis_run(run_id, actor_data)
        return

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
    except RequirementAnalysisCancelledError:
        _finalize_cancelled_requirement_analysis_run(run_id, actor_data)
        return
    except asyncio.TimeoutError:
        _mark_run_failed_due_to_timeout(run_id, document_id)
        return
    except Exception as exc:
        if isinstance(exc, RequirementAnalysisCancelledError) or _requirement_analysis_run_is_stopping(run_id):
            _finalize_cancelled_requirement_analysis_run(run_id, actor_data)
            return
        _mark_run_failed_due_to_exception(run_id, document_id, exc)
        return

    if _requirement_analysis_run_is_stopping(run_id):
        with connect() as db:
            document_repo.delete_requirement_analysis(db, result["id"])
        _finalize_cancelled_requirement_analysis_run(run_id, actor_data, extra_analysis_id=result["id"])
        return

    status = result["status"]
    if status == "needs_clarification":
        summary = result["analysis_summary"] or "需求分析完成，存在待确认问题。"
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


async def review_primary_requirement_file(project_id: str, document_id: str, actor, *, task_id: str) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        primary_file = document_repo.find_primary_file_mapping(db, document_id)
        if not primary_file:
            raise api_error(409, "DOCUMENT_PRIMARY_FILE_REQUIRED", "请先选择主需求文件后再进行需求分析。")
        if primary_file["conversion_status"] not in {"success", "warning"} or not primary_file["markdown_file_path"]:
            raise api_error(409, "DOCUMENT_PRIMARY_FILE_NOT_READY", "请先完成主需求标准文件转换后再进行需求分析。")

        markdown_path = resolve_stored_path(primary_file["markdown_file_path"]) or Path(primary_file["markdown_file_path"])
        if not markdown_path.exists():
            raise api_error(404, "DOCUMENT_MARKDOWN_MISSING", "主需求标准文件不存在。")

    _ensure_requirement_analysis_run_not_stopping(task_id)

    try:
        analysis_output = await analyze_requirement_with_agent(task_id)
    except RequirementAnalysisCancelledError:
        raise
    except Exception as exc:
        raise api_error(502, "REQUIREMENT_ANALYSIS_AGENT_FAILED", f"需求分析智能体运行失败：{exc}") from exc

    _ensure_requirement_analysis_run_not_stopping(task_id)

    artifact_paths = write_requirement_analysis_artifacts(task_id, analysis_output)
    output_data = build_requirement_analysis_output_json(analysis_output, artifact_paths)
    output_data = normalize_analysis_output_markdown(output_data)

    analysis_id = next_analysis_id()

    pending_count = len(output_data.get("clarification_items") or [])

    with connect() as db:
        document_repo.create_requirement_analysis(
            db,
            analysis_id=analysis_id,
            project_id=project_id,
            document_id=document_id,
            version_id=None,
            primary_mapping_id=primary_file["id"],
            status=analysis_output.status,
            analysis_summary=output_data.get("summary") or "",
            output_json=output_data,
            quality_result="passed" if analysis_output.status == "completed" else "warning",
            testability_score=0,
            draft_content_hash="",
            created_by=actor["id"],
        )

    result = {
        "id": analysis_id,
        "project_id": project_id,
        "document_id": document_id,
        "version_id": None,
        "primary_mapping_id": primary_file["id"],
        "quality_result": "passed" if analysis_output.status == "completed" else "warning",
        "created_by": actor["id"],
        "created_at": "",
        "draft_content_hash": "",
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
            "pending_count": pending_count,
        },
        task_id=task_id,
    )
    return result


def _requirement_analysis_run_task(run_id: str, actor, run: dict | None = None) -> dict:
    task = task_service.get_task_by_source(actor, source_type="requirement_analysis_run", source_id=run_id)
    if task:
        return task
    if run is None:
        with connect() as db:
            run = requirement_analysis_run_repo.find_run(db, run_id)
    if not run:
        raise api_error(404, "NOT_FOUND", "需求分析任务不存在。")
    status_group, status_label = task_service.REQUIREMENT_ANALYSIS_STATUS.get(run["status"], ("completed", run["status"]))
    return {
        "id": f"requirement_analysis:{run_id}",
        "source_type": "requirement_analysis_run",
        "source_id": run_id,
        "project_id": run["project_id"],
        "project_name": run["project_name"] if "project_name" in run.keys() else "",
        "module": "requirement",
        "module_label": "需求分析",
        "title": run["document_name"] if "document_name" in run.keys() else "",
        "status": run["status"],
        "status_label": status_label,
        "status_group": status_group,
        "summary": run["summary"],
        "created_at": run["created_at"],
        "updated_at": run["updated_at"],
        "detail_url": f"/projects/{run['project_id']}/requirements/{run['document_id']}",
    }


def _requirement_analysis_run_is_stopping(run_id: str) -> bool:
    with connect() as db:
        run = requirement_analysis_run_repo.find_run(db, run_id)
    return bool(run and run["status"] in {"stopping", "cancelled"})


def _ensure_requirement_analysis_run_not_stopping(run_id: str) -> None:
    if _requirement_analysis_run_is_stopping(run_id):
        raise RequirementAnalysisCancelledError("用户已停止需求分析。")


def _restore_document_after_cancelled_analysis(db, document_id: str, run) -> None:
    previous_version_id = run["previous_current_version_id"] if "previous_current_version_id" in run.keys() else None
    if previous_version_id:
        document_repo.update_current_version(db, document_id, previous_version_id, DOCUMENT_VERSIONED_STATUS)
        return
    latest_final_version = document_repo.find_latest_final_requirement_version(db, document_id)
    if latest_final_version:
        document_repo.update_current_version(
            db,
            document_id,
            latest_final_version["id"],
            DOCUMENT_VERSIONED_STATUS,
        )
        return
    document_repo.clear_current_version(db, document_id, DOCUMENT_PENDING_REVIEW_STATUS)


def _delete_requirement_analysis_run_artifacts(project_id: str, document_id: str, run_id: str) -> None:
    run_dir = project_requirement_dir(project_id, document_id) / "analysis_runs" / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)


def _finalize_cancelled_requirement_analysis_run(
    run_id: str,
    actor,
    *,
    extra_analysis_id: str | None = None,
) -> None:
    actor_data = dict(actor)
    with connect() as db:
        run = requirement_analysis_run_repo.find_run(db, run_id)
        if not run:
            return
        if run["status"] == "cancelled":
            return

        analysis_ids: set[str] = set()
        if run["analysis_id"]:
            analysis_ids.add(run["analysis_id"])
        if extra_analysis_id:
            analysis_ids.add(extra_analysis_id)
        for analysis_id in analysis_ids:
            document_repo.delete_requirement_analysis(db, analysis_id)
        requirement_analysis_run_repo.clear_analysis(db, run_id)
        _restore_document_after_cancelled_analysis(db, run["document_id"], run)
        requirement_analysis_run_repo.update_status(
            db,
            run_id,
            status="cancelled",
            summary="用户已停止需求分析。",
            failure_reason="",
        )
        project_id = run["project_id"]
        document_id = run["document_id"]

    _delete_requirement_analysis_run_artifacts(project_id, document_id, run_id)

    _record_requirement_review_task_event(
        run_id,
        actor_data,
        action="cancel_requirement_analysis",
        result="cancelled",
        summary="用户已停止需求分析。",
        status="cancelled",
        after={"status": "cancelled"},
    )


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


def _mark_run_failed_due_to_timeout(run_id: str, document_id: str) -> None:
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
    actor_data: dict = {"id": None, "name": None, "role": "system"}
    _record_requirement_review_task_event(
        run_id,
        actor_data,
        action="fail_requirement_analysis",
        result="failed",
        summary="需求分析失败。",
        status="failed",
        failure_reason=failure_reason,
    )


def _mark_run_failed_due_to_exception(run_id: str, document_id: str, exc: Exception) -> None:
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
    actor_data: dict = {"id": None, "name": None, "role": "system"}
    _record_requirement_review_task_event(
        run_id,
        actor_data,
        action="fail_requirement_analysis",
        result="failed",
        summary="需求分析失败。",
        status="failed",
        failure_reason=failure_reason,
    )


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
            return {"analysis": serialize_requirement_analysis(run_analysis) if run_analysis else None}
        row = document_repo.find_latest_requirement_analysis(db, document_id)
        if not row:
            return {"analysis": None}
        return {"analysis": serialize_requirement_analysis(row)}


def list_requirement_analysis_runs(project_id: str, document_id: str, actor) -> list[dict]:
    _ = actor
    task_service.recover_stale_requirement_analysis_runs(project_id=project_id)
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        rows = requirement_analysis_run_repo.list_by_document(db, document_id)
        return [serialize_requirement_analysis_run(row) for row in rows]


def list_requirement_clarification_answers(project_id: str, document_id: str, analysis_id: str, actor) -> dict:
    _ = actor
    with connect() as db:
        analysis = document_repo.find_requirement_analysis(db, analysis_id)
        if not analysis or analysis["project_id"] != project_id or analysis["document_id"] != document_id:
            raise api_error(404, "REQUIREMENT_ANALYSIS_NOT_FOUND", "需求分析结果不存在。")
        rows = requirement_clarification_answer_repo.list_answers(db, analysis_id)
        return {"answers": [serialize_requirement_clarification_answer(row) for row in rows]}
