from __future__ import annotations

from sqlite3 import Connection, Row


def create_log(db: Connection, values: dict) -> None:
    db.execute(
        """
        INSERT INTO operation_logs (
          id, log_type, module, action, object_type, object_id, object_name, project_id,
          actor_id, actor_name, source, result, failure_reason, summary, before_json,
          after_json, task_id, artifact_path, request_id, ip_address, user_agent
        )
        VALUES (
          :id, :log_type, :module, :action, :object_type, :object_id, :object_name, :project_id,
          :actor_id, :actor_name, :source, :result, :failure_reason, :summary, :before_json,
          :after_json, :task_id, :artifact_path, :request_id, :ip_address, :user_agent
        )
        """,
        values,
    )


def list_logs(db: Connection, filters: dict) -> tuple[list[Row], int]:
    where, params = _build_where(filters)
    page = int(filters.get("page") or 1)
    page_size = int(filters.get("page_size") or 20)
    offset = (page - 1) * page_size
    total = db.execute(f"SELECT COUNT(*) AS total FROM operation_logs {where}", params).fetchone()["total"]
    rows = db.execute(
        f"""
        SELECT *
        FROM operation_logs
        {where}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, page_size, offset),
    ).fetchall()
    return rows, total


def get_log(db: Connection, log_id: str) -> Row | None:
    return db.execute("SELECT * FROM operation_logs WHERE id = ?", (log_id,)).fetchone()


def get_retention_policy(db: Connection) -> Row:
    return db.execute("SELECT * FROM operation_log_retention_policy WHERE id = 'default'").fetchone()


def update_retention_policy(
    db: Connection,
    *,
    retention_days: int,
    max_rows: int,
    protect_high_risk: bool,
    updated_by: str,
) -> Row:
    db.execute(
        """
        UPDATE operation_log_retention_policy
        SET retention_days = ?,
            max_rows = ?,
            protect_high_risk = ?,
            updated_by = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 'default'
        """,
        (retention_days, max_rows, int(protect_high_risk), updated_by),
    )
    return get_retention_policy(db)


def count_cleanup_matches(db: Connection, filters: dict) -> int:
    where, params = _build_cleanup_where(filters)
    return db.execute(f"SELECT COUNT(*) AS total FROM operation_logs {where}", params).fetchone()["total"]


def cleanup_logs(db: Connection, filters: dict) -> int:
    where, params = _build_cleanup_where(filters)
    cursor = db.execute(f"DELETE FROM operation_logs {where}", params)
    return cursor.rowcount


def _build_where(filters: dict) -> tuple[str, tuple]:
    clauses = []
    params: list[object] = []
    for key in ("project_id", "log_type", "module", "action", "object_type", "actor_id", "result"):
        value = filters.get(key)
        if value:
            clauses.append(f"{key} = ?")
            params.append(value)
    if filters.get("start_time"):
        clauses.append("created_at >= ?")
        params.append(filters["start_time"])
    if filters.get("end_time"):
        clauses.append("created_at <= ?")
        params.append(filters["end_time"])
    if filters.get("keyword"):
        keyword = f"%{filters['keyword']}%"
        clauses.append("(object_name LIKE ? OR summary LIKE ? OR failure_reason LIKE ?)")
        params.extend([keyword, keyword, keyword])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, tuple(params)


def _build_cleanup_where(filters: dict) -> tuple[str, tuple]:
    clauses = []
    params: list[object] = []
    if filters.get("before_time"):
        clauses.append("created_at < ?")
        params.append(filters["before_time"])
    if filters.get("log_type"):
        clauses.append("log_type = ?")
        params.append(filters["log_type"])
    if filters.get("project_id"):
        clauses.append("project_id = ?")
        params.append(filters["project_id"])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, tuple(params)
