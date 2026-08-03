import json
from sqlite3 import Row
from typing import Any

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import api_automation_repo, project_repo, report_center_repo


SUPPORTED_REPORT_TYPES = {"performance", "api"}


def list_reports(report_type: str, project_id: str, actor: Row) -> list[dict[str, Any]]:
    if report_type not in SUPPORTED_REPORT_TYPES:
        raise api_error(400, "REPORT_TYPE_INVALID", "暂不支持该报告类型。")

    with connect() as db:
        visible_projects = project_repo.list_visible(db, actor)
        if project_id != "all":
            selected = next((project for project in visible_projects if project["id"] == project_id), None)
            if not selected:
                raise api_error(404, "PROJECT_NOT_FOUND", "项目不存在或无权访问。")
            visible_projects = [selected]

        project_ids = [str(project["id"]) for project in visible_projects]
        if report_type == "api":
            return [_serialize_api_report(row) for row in report_center_repo.list_api_reports(db, project_ids)]
        return [_serialize_performance_report(row) for row in report_center_repo.list_performance_reports(db, project_ids)]


def delete_report(report_type: str, report_id: str, actor: Row) -> None:
    if report_type not in SUPPORTED_REPORT_TYPES:
        raise api_error(400, "REPORT_TYPE_INVALID", "暂不支持该报告类型。")

    with connect() as db:
        report = (
            report_center_repo.find_api_report(db, report_id)
            if report_type == "api"
            else report_center_repo.find_performance_report(db, report_id)
        )
        visible_project_ids = {str(project["id"]) for project in project_repo.list_visible(db, actor)}
        if not report or str(report["project_id"]) not in visible_project_ids:
            raise api_error(404, "REPORT_NOT_FOUND", "报告不存在或无权访问。")
        if report_type == "api":
            report_center_repo.delete_api_report(db, report_id)
        else:
            report_center_repo.delete_performance_report(db, report_id)


def get_api_report(report_id: str, actor: Row) -> dict[str, Any]:
    with connect() as db:
        report = report_center_repo.find_api_report(db, report_id)
        visible_project_ids = {str(project["id"]) for project in project_repo.list_visible(db, actor)}
        if not report or str(report["project_id"]) not in visible_project_ids:
            raise api_error(404, "REPORT_NOT_FOUND", "报告不存在或无权访问。")
        child_rows = api_automation_repo.list_batch_api_runs(db, report_id)
        counts = _api_counts(child_rows)
        return {
            "id": report["id"],
            "project_id": report["project_id"],
            "project_name": report["project_name"],
            "name": report["name"],
            "result": report["result"],
            "status": report["status"],
            "environment": {
                "id": report["api_environment_id"],
                "name": report["environment_name"] or "",
                "api_base_url": report["api_base_url"] or "",
            },
            "counts": counts,
            "pass_rate": counts["passed"] / counts["total"] if counts["total"] else 0,
            "runs": [_serialize_api_report_run(row) for row in child_rows],
            "error_message": report["error_message"],
            "created_at": report["created_at"],
            "started_at": report["started_at"],
            "finished_at": report["finished_at"],
        }


def _serialize_performance_report(row: Row) -> dict[str, Any]:
    report_snapshot = _loads(row["report_snapshot_json"])
    metric_snapshot = _loads(row["metric_snapshot_json"])
    verdict = str(report_snapshot.get("verdict") or metric_snapshot.get("verdict") or "indeterminate")
    quality = metric_snapshot.get("quality") if isinstance(metric_snapshot.get("quality"), dict) else {}
    analysis_id = str(row["id"])
    project_id = str(row["project_id"])
    test_id = str(row["test_id"])
    run_id = str(row["run_id"])
    status = _analysis_status(str(row["legacy_status"]), str(row["analysis_status"] or ""))
    generation_mode = str(row["generation_mode"] or report_snapshot.get("generation_mode") or "")
    if not generation_mode and status == "completed":
        generation_mode = "ai_primary"
    generation_status = (
        "degraded"
        if generation_mode == "deterministic_fallback"
        else "failed"
        if status == "failed"
        else "generated"
        if status == "completed"
        else "generating"
    )
    return {
        "id": analysis_id,
        "report_type": "performance",
        "project_id": project_id,
        "project_name": str(row["project_name"]),
        "test_id": test_id,
        "test_name": str(row["test_name"]),
        "run_id": run_id,
        "analysis_id": analysis_id,
        "analysis_version": int(row["analysis_version"]),
        "name": f"{row['test_name']} - 性能智能分析报告",
        "status": status,
        "generation_mode": generation_mode,
        "generation_status": generation_status,
        "verdict": verdict,
        "quality_status": str(quality.get("status") or "invalid"),
        "error_message": str(row["error_message"] or ""),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "href": (
            f"/projects/{project_id}/performance-tests/{test_id}/runs/{run_id}"
            f"/analysis/{analysis_id}"
        ),
    }


def _serialize_api_report(row: Row) -> dict[str, Any]:
    scenario_count = int(row["scenario_count"] or 0)
    passed_count = int(row["passed_count"] or 0)
    return {
        "id": str(row["id"]),
        "report_type": "api",
        "project_id": str(row["project_id"]),
        "project_name": str(row["project_name"]),
        "name": str(row["name"]),
        "status": "completed",
        "generation_mode": "deterministic",
        "generation_status": "generated",
        "verdict": _api_verdict(str(row["result"])),
        "quality_status": "complete",
        "environment_name": str(row["environment_name"] or ""),
        "scenario_count": scenario_count,
        "passed_count": passed_count,
        "pass_rate": passed_count / scenario_count if scenario_count else 0,
        "error_message": str(row["error_message"] or ""),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "href": f"/reports/api/{row['id']}",
    }


def _serialize_api_report_run(row: Row) -> dict[str, Any]:
    snapshot = _loads(row["execution_snapshot_json"])
    scenario = snapshot.get("scenario") if isinstance(snapshot.get("scenario"), dict) else {}
    return {
        "id": str(row["id"]),
        "scenario_id": str(scenario.get("id") or ""),
        "scenario_name": str(scenario.get("name") or "未命名场景"),
        "step_count": int(scenario.get("step_count") or 0),
        "status": str(row["status"]),
        "summary": _loads(row["summary_json"]),
        "error_message": str(row["error_message"] or ""),
        "created_at": str(row["created_at"]),
        "finished_at": row["finished_at"],
    }


def _api_counts(rows: list[Row]) -> dict[str, int]:
    statuses = [str(row["status"]) for row in rows]
    return {
        "total": len(statuses),
        "passed": statuses.count("passed"),
        "observed": statuses.count("observed"),
        "failed": statuses.count("failed"),
        "error": sum(status in {"cancelled", "interrupted"} for status in statuses),
    }


def _api_verdict(result: str) -> str:
    if result == "passed":
        return "pass"
    if result == "observed":
        return "conditional_pass"
    if result in {"failed", "error"}:
        return "fail"
    return "indeterminate"


def _loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _analysis_status(legacy_status: str, stored_status: str) -> str:
    if legacy_status in {"waiting_approval", "rejected"} and stored_status == "collecting":
        return "completed"
    if stored_status in {"collecting", "analyzing", "completed", "failed"}:
        return stored_status
    return "completed" if legacy_status in {"waiting_approval", "rejected"} else legacy_status
