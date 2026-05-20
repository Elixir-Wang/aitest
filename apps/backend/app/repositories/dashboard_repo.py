from __future__ import annotations

from sqlite3 import Connection


def get_trend(db: Connection, project_ids: list[str], days: int) -> list[dict]:
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


def latest_generated_cases(db: Connection, project_ids: list[str]) -> int:
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

