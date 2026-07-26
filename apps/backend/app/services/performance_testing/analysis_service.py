import secrets
import threading
from datetime import datetime, timezone

from app.agents.performance_testing.diagnosis.service import PROMPT_VERSION, diagnose_performance
from app.core.db import connect
from app.core.exceptions import api_error
from app.core.logging import logger
from app.repositories import performance_analysis_repo, project_repo
from app.services.performance_testing import run_repo
from app.services.performance_testing.analysis_evidence import collect_performance_evidence, has_analyzable_evidence
from app.services.performance_testing.metric_snapshot_service import (
    CALCULATOR_VERSION,
    build_metric_snapshot,
    build_report_snapshot,
)


TERMINAL_RUN_STATUSES = {"completed", "stopped", "failed", "cancelled"}


def create_analysis(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        run = run_repo.get_run(db, run_id)
        if not run or run["project_id"] != project_id:
            raise api_error(404, "PERFORMANCE_RUN_NOT_FOUND", "性能测试运行不存在。")
        if run["status"] not in TERMINAL_RUN_STATUSES:
            raise api_error(409, "PERFORMANCE_ANALYSIS_RUN_ACTIVE", "请等待本轮压测结束后再启动 AI 分析。")
        if performance_analysis_repo.find_active_analysis_for_run(db, run_id):
            raise api_error(409, "PERFORMANCE_ANALYSIS_ALREADY_RUNNING", "该运行已有正在执行的 AI 分析。")

    evidence = collect_performance_evidence(project_id, run_id)
    if not has_analyzable_evidence(evidence):
        raise api_error(400, "PERFORMANCE_ANALYSIS_NO_EVIDENCE", "当前运行没有可供分析的请求、失败或异常证据。")

    analysis_id = f"perfanalysis-{secrets.token_hex(8)}"
    with connect() as db:
        if performance_analysis_repo.find_active_analysis_for_run(db, run_id):
            raise api_error(409, "PERFORMANCE_ANALYSIS_ALREADY_RUNNING", "该运行已有正在执行的 AI 分析。")
        performance_analysis_repo.create_analysis_session(
            db,
            analysis_id=analysis_id,
            project_id=project_id,
            run_id=run_id,
            analysis_version=performance_analysis_repo.next_analysis_version(db, run_id),
            created_by=str(actor["id"]),
        )
        row = performance_analysis_repo.find_analysis_session(db, analysis_id)
        return performance_analysis_repo.serialize_analysis_session(row)


def schedule_automatic_analysis(project_id: str, run_id: str, created_by: str) -> str:
    """Create the terminal-run report and execute it outside the Locust monitor thread."""
    try:
        created = create_analysis(
            project_id,
            run_id,
            {"id": created_by or "system", "role": "admin", "project_scope": "全部项目"},
        )
    except Exception as exc:
        logger.warning(
            "performance_analysis_auto_schedule_skipped | project_id={} run_id={} error_type={} error={}",
            project_id,
            run_id,
            type(exc).__name__,
            str(exc),
        )
        return ""
    thread = threading.Thread(
        target=execute_analysis,
        args=(str(created["id"]),),
        name=f"performance-analysis-{run_id}",
        daemon=True,
    )
    thread.start()
    return str(created["id"])


def execute_analysis(analysis_id: str) -> None:
    try:
        with connect() as db:
            row = performance_analysis_repo.find_analysis_session(db, analysis_id)
            if not row or row["status"] != "collecting":
                return
            project_id = str(row["project_id"])
            run_id = str(row["run_id"])
            performance_analysis_repo.update_analysis_session(db, analysis_id, status="analyzing")

        evidence = collect_performance_evidence(project_id, run_id)
        metric_snapshot = build_metric_snapshot(evidence)
        with connect() as db:
            performance_analysis_repo.update_analysis_session(
                db,
                analysis_id,
                analysis_status="analyzing",
                analysis_stage="ai_diagnosis",
                metric_snapshot=metric_snapshot,
                calculator_version=CALCULATOR_VERSION,
                source_fingerprint=metric_snapshot["source_fingerprint"],
            )
        diagnosis, model_name = diagnose_performance({**evidence, "metric_snapshot": metric_snapshot})
        report_snapshot = build_report_snapshot(metric_snapshot, diagnosis)
        proposal = {
            "changes": [change.model_dump(mode="json") for change in diagnosis.proposed_changes],
            "requires_second_approval": diagnosis.requires_second_approval,
            "can_auto_rerun": diagnosis.can_auto_rerun,
            "readonly": False,
        }
        applicable_changes = [
            change
            for change in proposal["changes"]
            if performance_analysis_repo.is_applicable_change(change)
        ]
        with connect() as db:
            performance_analysis_repo.update_analysis_session(
                db,
                analysis_id,
                status="waiting_approval",
                analysis_status="completed",
                analysis_stage="report_ready",
                repair_status="available" if applicable_changes else "not_applicable",
                category=diagnosis.category,
                summary=diagnosis.direct_cause,
                direct_cause=diagnosis.direct_cause,
                root_cause=diagnosis.root_cause,
                confidence=diagnosis.confidence,
                evidence=[item.model_dump(mode="json") for item in diagnosis.evidence],
                missing_evidence=diagnosis.missing_evidence,
                proposal=proposal,
                report_snapshot=report_snapshot,
                prompt_version=PROMPT_VERSION,
                model_name=model_name,
                finished_at=_now(),
            )
    except Exception as exc:
        logger.exception(
            "performance_analysis_failed | analysis_id={} project_id={} run_id={} "
            "error_type={} status_code={} error={}",
            analysis_id,
            locals().get("project_id", ""),
            locals().get("run_id", ""),
            type(exc).__name__,
            getattr(exc, "status_code", ""),
            str(exc),
        )
        with connect() as db:
            if performance_analysis_repo.find_analysis_session(db, analysis_id):
                performance_analysis_repo.update_analysis_session(
                    db,
                    analysis_id,
                    status="failed",
                    analysis_status="failed",
                    analysis_stage="failed",
                    error_message=_analysis_error_message(exc),
                    finished_at=_now(),
                )


def get_analysis(project_id: str, analysis_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = performance_analysis_repo.find_analysis_session(db, analysis_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "PERFORMANCE_ANALYSIS_NOT_FOUND", "性能分析不存在。")
        return performance_analysis_repo.serialize_analysis_session(row)


def list_run_analyses(project_id: str, run_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        run = run_repo.get_run(db, run_id)
        if not run or run["project_id"] != project_id:
            raise api_error(404, "PERFORMANCE_RUN_NOT_FOUND", "性能测试运行不存在。")
        return [
            performance_analysis_repo.serialize_analysis_session(row)
            for row in performance_analysis_repo.list_analysis_sessions(db, project_id, run_id)
        ]


def reject_analysis(project_id: str, analysis_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = performance_analysis_repo.find_analysis_session(db, analysis_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "PERFORMANCE_ANALYSIS_NOT_FOUND", "性能分析不存在。")
        if row["status"] != "waiting_approval" or row["repair_status"] != "available":
            raise api_error(409, "PERFORMANCE_ANALYSIS_REVIEW_INVALID", "当前分析状态不能驳回。")
        performance_analysis_repo.update_analysis_session(
            db,
            analysis_id,
            status="rejected",
            analysis_status="completed",
            repair_status="rejected",
        )
        updated = performance_analysis_repo.find_analysis_session(db, analysis_id)
        return performance_analysis_repo.serialize_analysis_session(updated)


def _require_visible_project(db, project_id: str, actor) -> None:
    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "NOT_FOUND", "项目不存在。")
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return
    if project["name"] == actor["project_scope"]:
        return
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _analysis_error_message(exc: Exception) -> str:
    """Turn provider errors into an actionable message without exposing raw details."""
    status_code = getattr(exc, "status_code", None)
    error_text = str(exc).lower()
    error_type = type(exc).__name__.lower()
    is_rate_limited = (
        status_code == 429
        or "ratelimit" in error_type
        or "rate_limit" in error_text
        or "rate limit" in error_text
    )
    if is_rate_limited:
        return "AI 分析执行失败：触发模型接口 429 频率限制，可能是请求过于频繁或模型配额不足。请稍后重试或检查模型配额。"
    return f"AI 分析执行失败：{type(exc).__name__}。请检查后台日志或重新分析。"


__all__ = [
    "create_analysis",
    "schedule_automatic_analysis",
    "execute_analysis",
    "get_analysis",
    "list_run_analyses",
    "reject_analysis",
]
