from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import dashboard_repo, project_repo


def dashboard_overview(project_id: str, days: int, actor) -> dict:
    with connect() as db:
        visible_projects = project_repo.list_visible(db, actor)
        if not visible_projects:
            return _empty_dashboard(project_id)

        project_ids = [project["id"] for project in visible_projects]
        selected_project = None
        if project_id != "all":
            selected_project = next((project for project in visible_projects if project["id"] == project_id), None)
            if not selected_project:
                raise api_error(404, "PROJECT_NOT_FOUND", "项目不存在或无权访问。")
            project_ids = [project_id]

        latest = dashboard_repo.get_current_stats(db, project_ids)
        trend = dashboard_repo.get_trend(db, project_ids, days)
        previous = trend[-8] if len(trend) >= 8 else (trend[0] if trend else latest)
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
                    "value": _percent(latest["adoptedCases"], latest["caseAssets"]),
                    "helper": _delta_helper(latest["adoptedCases"], previous["adoptedCases"], "较上周"),
                },
                {
                    "label": "自动化用例数量",
                    "value": str(latest["automationCases"]),
                    "helper": f"用例数量 {latest['automationCases']} 条",
                },
            ],
            "trend": trend,
        }


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
            {"label": "自动化用例数量", "value": "0", "helper": "用例数量 0 条"},
        ],
        "trend": [],
    }
