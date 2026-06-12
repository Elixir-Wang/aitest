from sqlite3 import Connection, Row


ACTIVE_STATUSES = {"queued", "running", "stopping"}


def create_run(
    db: Connection,
    *,
    run_id: str,
    project_id: str,
    document_id: str,
    primary_mapping_id: str,
    status: str,
    summary: str,
    created_by: str,
    previous_current_version_id: str | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO requirement_analysis_runs
          (id, project_id, document_id, primary_mapping_id, status, summary, created_by, previous_current_version_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, project_id, document_id, primary_mapping_id, status, summary, created_by, previous_current_version_id),
    )


def find_run(db: Connection, run_id: str) -> Row | None:
    return db.execute(
        """
        SELECT r.*, p.name AS project_name, d.name AS document_name, m.original_filename AS primary_filename
        FROM requirement_analysis_runs r
        JOIN projects p ON p.id = r.project_id
        JOIN source_documents d ON d.id = r.document_id
        LEFT JOIN source_document_file_mappings m ON m.id = r.primary_mapping_id
        WHERE r.id = ?
        """,
        (run_id,),
    ).fetchone()


def find_run_by_id(db: Connection, run_id: str) -> Row | None:
    return find_run(db, run_id)


def list_by_document(db: Connection, document_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT r.*, a.output_json AS analysis_output_json
        FROM requirement_analysis_runs r
        LEFT JOIN requirement_analyses a ON a.id = r.analysis_id
        WHERE r.document_id = ?
        ORDER BY r.created_at DESC, r.id DESC
        """,
        (document_id,),
    ).fetchall()


def find_active_by_document(db: Connection, document_id: str) -> Row | None:
    return db.execute(
        """
        SELECT *
        FROM requirement_analysis_runs
        WHERE document_id = ? AND status IN ('queued', 'running', 'stopping')
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (document_id,),
    ).fetchone()


def list_active_runs(db: Connection, *, project_id: str | None = None) -> list[Row]:
    project_filter = "AND r.project_id = ?" if project_id else ""
    params: list[str] = []
    if project_id:
        params.append(project_id)
    return db.execute(
        f"""
        SELECT r.*, d.name AS document_name
        FROM requirement_analysis_runs r
        JOIN source_documents d ON d.id = r.document_id
        WHERE r.status IN ('queued', 'running', 'stopping')
          {project_filter}
        ORDER BY r.updated_at ASC, r.id ASC
        """,
        tuple(params),
    ).fetchall()


def list_stale_active_runs(db: Connection, *, project_id: str | None = None, timeout_minutes: int) -> list[Row]:
    project_filter = "AND r.project_id = ?" if project_id else ""
    params: list[str | int] = [f"-{timeout_minutes} minutes"]
    if project_id:
        params.append(project_id)
    return db.execute(
        f"""
        SELECT r.*, d.name AS document_name
        FROM requirement_analysis_runs r
        JOIN source_documents d ON d.id = r.document_id
        WHERE r.status IN ('queued', 'running')
          AND datetime(r.updated_at) <= datetime('now', ?)
          {project_filter}
        ORDER BY r.updated_at ASC, r.id ASC
        """,
        tuple(params),
    ).fetchall()


def update_status(
    db: Connection,
    run_id: str,
    *,
    status: str,
    summary: str | None = None,
    failure_reason: str | None = None,
) -> None:
    assignments = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    values: list[str] = [status]
    if summary is not None:
        assignments.append("summary = ?")
        values.append(summary)
    if failure_reason is not None:
        assignments.append("failure_reason = ?")
        values.append(failure_reason)
    values.append(run_id)
    db.execute(
        f"UPDATE requirement_analysis_runs SET {', '.join(assignments)} WHERE id = ?",
        tuple(values),
    )


def attach_analysis(db: Connection, run_id: str, analysis_id: str) -> None:
    db.execute(
        """
        UPDATE requirement_analysis_runs
        SET analysis_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (analysis_id, run_id),
    )


def clear_analysis(db: Connection, run_id: str) -> None:
    db.execute(
        """
        UPDATE requirement_analysis_runs
        SET analysis_id = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (run_id,),
    )


def try_mark_running(db: Connection, run_id: str) -> bool:
    cursor = db.execute(
        """
        UPDATE requirement_analysis_runs
        SET status = 'running',
            summary = '需求分析智能体正在分析。',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'queued'
        """,
        (run_id,),
    )
    return cursor.rowcount > 0


def try_mark_stopping(db: Connection, run_id: str, *, from_statuses: tuple[str, ...]) -> bool:
    if not from_statuses:
        return False
    placeholders = ", ".join("?" for _ in from_statuses)
    cursor = db.execute(
        f"""
        UPDATE requirement_analysis_runs
        SET status = 'stopping',
            summary = '正在停止需求分析。',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status IN ({placeholders})
        """,
        (run_id, *from_statuses),
    )
    return cursor.rowcount > 0
