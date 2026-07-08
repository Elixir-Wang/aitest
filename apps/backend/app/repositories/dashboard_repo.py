from datetime import date, datetime, timedelta
from sqlite3 import Connection


def get_current_stats(db: Connection, project_ids: list[str]) -> dict:
    placeholders = ",".join("?" for _ in project_ids)
    row = db.execute(
        f"""
        SELECT
          COUNT(*) AS case_assets,
          SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS adopted_cases
        FROM test_cases
        WHERE project_id IN ({placeholders})
        """,
        project_ids,
    ).fetchone()
    case_assets = int(row["case_assets"] or 0)
    adopted_cases = int(row["adopted_cases"] or 0)
    return {
        "caseAssets": case_assets,
        "adoptedCases": adopted_cases,
        "automationCases": case_assets,
    }


def get_trend(db: Connection, project_ids: list[str], days: int) -> list[dict]:
    if days <= 0:
        return []

    placeholders = ",".join("?" for _ in project_ids)
    anchor_date = _trend_anchor_date(db, project_ids)
    start_date = anchor_date - timedelta(days=days - 1)
    opening = db.execute(
        f"""
        SELECT
          COUNT(*) AS case_assets,
          SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS adopted_cases
        FROM test_cases
        WHERE project_id IN ({placeholders})
          AND date(created_at) < ?
        """,
        (*project_ids, start_date.isoformat()),
    ).fetchone()
    rows = db.execute(
        f"""
        SELECT
          date(created_at) AS stat_date,
          COUNT(*) AS case_assets,
          SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS adopted_cases
        FROM test_cases
        WHERE project_id IN ({placeholders})
          AND date(created_at) <= ?
        GROUP BY stat_date
        ORDER BY stat_date ASC
        """,
        (*project_ids, anchor_date.isoformat()),
    ).fetchall()

    daily_counts = {
        row["stat_date"]: {
            "caseAssets": int(row["case_assets"] or 0),
            "adoptedCases": int(row["adopted_cases"] or 0),
        }
        for row in rows
    }

    trend = []
    cumulative_case_assets = int(opening["case_assets"] or 0)
    cumulative_adopted_cases = int(opening["adopted_cases"] or 0)
    for offset in range(days):
        stat_date = start_date + timedelta(days=offset)
        date_key = stat_date.isoformat()
        counts = daily_counts.get(date_key, {"caseAssets": 0, "adoptedCases": 0})
        cumulative_case_assets += counts["caseAssets"]
        cumulative_adopted_cases += counts["adoptedCases"]
        trend.append(
            {
                "date": date_key,
                "caseAssets": cumulative_case_assets,
                "adoptedCases": cumulative_adopted_cases,
                "automationCases": cumulative_case_assets,
            }
        )
    return trend


def _trend_anchor_date(db: Connection, project_ids: list[str]) -> date:
    placeholders = ",".join("?" for _ in project_ids)
    row = db.execute(
        f"""
        SELECT MAX(date(created_at)) AS latest_case_date
        FROM test_cases
        WHERE project_id IN ({placeholders})
        """,
        project_ids,
    ).fetchone()
    today = date.today()
    if not row or not row["latest_case_date"]:
        return today
    latest_case_date = datetime.strptime(row["latest_case_date"], "%Y-%m-%d").date()
    return max(today, latest_case_date)
