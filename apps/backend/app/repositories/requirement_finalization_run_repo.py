from sqlite3 import Connection, Row


def create_run(
    db: Connection,
    *,
    run_id: str,
    project_id: str,
    document_id: str,
    analysis_id: str,
    status: str,
    summary: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO requirement_finalization_runs
          (id, project_id, document_id, analysis_id, status, summary, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, project_id, document_id, analysis_id, status, summary, created_by),
    )


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
        f"UPDATE requirement_finalization_runs SET {', '.join(assignments)} WHERE id = ?",
        tuple(values),
    )


def find_run(db: Connection, run_id: str) -> Row | None:
    return db.execute(
        """
        SELECT r.*, d.name AS document_name
        FROM requirement_finalization_runs r
        JOIN source_documents d ON d.id = r.document_id
        WHERE r.id = ?
        """,
        (run_id,),
    ).fetchone()
