import json
from sqlite3 import Row
from typing import Any

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import project_repo, report_center_repo


SUPPORTED_REPORT_TYPES = {"performance"}


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

        rows = report_center_repo.list_performance_reports(
            db,
            [str(project["id"]) for project in visible_projects],
        )
        return [_serialize_performance_report(row) for row in rows]


def delete_report(report_type: str, report_id: str, actor: Row) -> None:
    if report_type not in SUPPORTED_REPORT_TYPES:
        raise api_error(400, "REPORT_TYPE_INVALID", "暂不支持该报告类型。")

    with connect() as db:
        report = report_center_repo.find_performance_report(db, report_id)
        visible_project_ids = {str(project["id"]) for project in project_repo.list_visible(db, actor)}
        if not report or str(report["project_id"]) not in visible_project_ids:
            raise api_error(404, "REPORT_NOT_FOUND", "报告不存在或无权访问。")
        report_center_repo.delete_performance_report(db, report_id)


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
