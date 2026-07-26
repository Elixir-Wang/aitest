from sqlite3 import Connection, Row


def list_performance_reports(db: Connection, project_ids: list[str]) -> list[Row]:
    if not project_ids:
        return []
    placeholders = ", ".join("?" for _ in project_ids)
    return db.execute(
        f"""
        SELECT
          analysis.id,
          analysis.project_id,
          projects.name AS project_name,
          tests.id AS test_id,
          tests.name AS test_name,
          analysis.run_id,
          analysis.analysis_version,
          analysis.status AS legacy_status,
          analysis.analysis_status,
          analysis.report_snapshot_json,
          analysis.metric_snapshot_json,
          analysis.error_message,
          analysis.created_at,
          analysis.updated_at
        FROM performance_analysis_sessions AS analysis
        JOIN performance_test_runs AS runs ON runs.id = analysis.run_id
        JOIN performance_tests AS tests ON tests.id = runs.performance_test_id
        JOIN projects ON projects.id = analysis.project_id
        WHERE analysis.project_id IN ({placeholders})
        ORDER BY analysis.updated_at DESC, analysis.created_at DESC
        """,
        project_ids,
    ).fetchall()
