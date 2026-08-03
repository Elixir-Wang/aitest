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
          analysis.generation_mode,
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


def find_performance_report(db: Connection, report_id: str) -> Row | None:
    return db.execute(
        "SELECT id, project_id FROM performance_analysis_sessions WHERE id = ?",
        (report_id,),
    ).fetchone()


def delete_performance_report(db: Connection, report_id: str) -> None:
    db.execute("DELETE FROM performance_analysis_sessions WHERE id = ?", (report_id,))


def list_api_reports(db: Connection, project_ids: list[str]) -> list[Row]:
    if not project_ids:
        return []
    placeholders = ", ".join("?" for _ in project_ids)
    return db.execute(
        f"""
        SELECT
          batches.id,
          batches.project_id,
          projects.name AS project_name,
          batches.api_environment_id,
          environments.name AS environment_name,
          batches.name,
          batches.status,
          batches.result,
          batches.error_message,
          batches.created_at,
          batches.updated_at,
          batches.finished_at,
          COUNT(runs.id) AS scenario_count,
          COALESCE(SUM(CASE WHEN runs.status = 'passed' THEN 1 ELSE 0 END), 0) AS passed_count
        FROM api_batch_runs AS batches
        JOIN projects ON projects.id = batches.project_id
        LEFT JOIN api_test_environments AS environments ON environments.id = batches.api_environment_id
        LEFT JOIN api_automation_runs AS runs ON runs.batch_run_id = batches.id
        WHERE batches.project_id IN ({placeholders})
          AND batches.status = 'completed'
          AND batches.report_deleted_at IS NULL
        GROUP BY batches.id
        ORDER BY batches.updated_at DESC, batches.created_at DESC
        """,
        project_ids,
    ).fetchall()


def find_api_report(db: Connection, report_id: str) -> Row | None:
    return db.execute(
        """
        SELECT batches.*, projects.name AS project_name, environments.name AS environment_name,
               environments.api_base_url
        FROM api_batch_runs AS batches
        JOIN projects ON projects.id = batches.project_id
        LEFT JOIN api_test_environments AS environments ON environments.id = batches.api_environment_id
        WHERE batches.id = ? AND batches.report_deleted_at IS NULL
        """,
        (report_id,),
    ).fetchone()


def delete_api_report(db: Connection, report_id: str) -> None:
    db.execute(
        "UPDATE api_batch_runs SET report_deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (report_id,),
    )
