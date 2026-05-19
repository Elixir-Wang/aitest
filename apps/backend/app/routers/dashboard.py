from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import connect
from ..schemas import DashboardOut
from ..security import current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOut)
def dashboard_overview(
    project_id: str = Query(default="all"),
    days: int = Query(default=17, ge=1, le=90),
    actor=Depends(current_user),
) -> dict:
    with connect() as db:
        visible_projects = _visible_projects(db, actor)
        if not visible_projects:
            return _empty_dashboard(project_id)

        project_ids = [project["id"] for project in visible_projects]
        selected_project = None
        if project_id != "all":
            selected_project = next((project for project in visible_projects if project["id"] == project_id), None)
            if not selected_project:
                raise HTTPException(status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在或无权访问。"})
            project_ids = [project_id]

        trend = _trend(db, project_ids, days)
        latest = trend[-1] if trend else {"caseAssets": 0, "adoptedCases": 0, "automationCases": 0}
        previous = trend[-8] if len(trend) >= 8 else (trend[0] if trend else latest)
        generated_cases = _latest_generated_cases(db, project_ids)
        active_project_count = sum(1 for project in visible_projects if project["status"] == "active")

        return {
            "scope": "all" if project_id == "all" else "project",
            "project_id": selected_project["id"] if selected_project else None,
            "project_name": selected_project["name"] if selected_project else None,
            "metrics": [
                {
                    "label": "项目数",
                    "value": str(active_project_count if project_id == "all" else 1),
                    "helper": f"活跃项目 {active_project_count if project_id == 'all' else 1} 个",
                },
                {
                    "label": "用例资产数",
                    "value": str(latest["caseAssets"]),
                    "helper": f"已采纳 {latest['adoptedCases']} 条",
                },
                {
                    "label": "测试用例采纳率",
                    "value": _percent(latest["adoptedCases"], generated_cases),
                    "helper": _delta_helper(latest["adoptedCases"], previous["adoptedCases"], "较上周"),
                },
                {
                    "label": "自动化用例数量",
                    "value": str(latest["automationCases"]),
                    "helper": f"可执行 {latest['automationCases']} 条",
                },
            ],
            "trend": trend,
        }


def _visible_projects(db, actor) -> list:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return db.execute("SELECT * FROM projects WHERE status != 'archived' ORDER BY created_at ASC").fetchall()
    return db.execute(
        "SELECT * FROM projects WHERE status != 'archived' AND name = ? ORDER BY created_at ASC",
        (actor["project_scope"],),
    ).fetchall()


def _trend(db, project_ids: list[str], days: int) -> list[dict]:
    placeholders = ",".join("?" for _ in project_ids)
    rows = db.execute(
        f"""
        SELECT
          stat_date,
          SUM(case_assets) AS case_assets,
          SUM(adopted_cases) AS adopted_cases,
          SUM(automation_cases) AS automation_cases
        FROM dashboard_daily_stats
        WHERE project_id IN ({placeholders})
        GROUP BY stat_date
        ORDER BY stat_date DESC
        LIMIT ?
        """,
        (*project_ids, days),
    ).fetchall()
    return [
        {
            "date": row["stat_date"],
            "caseAssets": row["case_assets"],
            "adoptedCases": row["adopted_cases"],
            "automationCases": row["automation_cases"],
        }
        for row in reversed(rows)
    ]


def _latest_generated_cases(db, project_ids: list[str]) -> int:
    placeholders = ",".join("?" for _ in project_ids)
    row = db.execute(
        f"""
        SELECT SUM(generated_cases) AS generated_cases
        FROM dashboard_daily_stats
        WHERE project_id IN ({placeholders})
          AND stat_date = (
            SELECT MAX(stat_date)
            FROM dashboard_daily_stats
            WHERE project_id IN ({placeholders})
          )
        """,
        (*project_ids, *project_ids),
    ).fetchone()
    return int(row["generated_cases"] or 0)


def _percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0%"
    return f"{round(numerator / denominator * 100)}%"


def _delta_helper(current: int, previous: int, label: str) -> str:
    if previous <= 0:
        return f"{label} -"
    delta = round((current - previous) / previous * 100)
    sign = "+" if delta >= 0 else ""
    return f"{label} {sign}{delta}%"


def _empty_dashboard(project_id: str) -> dict:
    return {
        "scope": "all" if project_id == "all" else "project",
        "project_id": None if project_id == "all" else project_id,
        "project_name": None,
        "metrics": [
            {"label": "项目数", "value": "0", "helper": "活跃项目 0 个"},
            {"label": "用例资产数", "value": "0", "helper": "已采纳 0 条"},
            {"label": "测试用例采纳率", "value": "0%", "helper": "较上周 -"},
            {"label": "自动化用例数量", "value": "0", "helper": "可执行 0 条"},
        ],
        "trend": [],
    }
