from sqlite3 import Connection, Row


def find_by_id(db: Connection, artifact_id: str) -> Row | None:
    """根据ID查找产物"""
    return db.execute("SELECT * FROM exploration_artifacts WHERE id = ?", (artifact_id,)).fetchone()


def list_by_run(db: Connection, run_id: str) -> list[Row]:
    """列出探索任务的所有产物"""
    return db.execute(
        """
        SELECT * FROM exploration_artifacts
        WHERE exploration_run_id = ?
        ORDER BY created_at ASC
        """,
        (run_id,),
    ).fetchall()


def list_by_type(db: Connection, run_id: str, artifact_type: str) -> list[Row]:
    """列出特定类型的产物"""
    return db.execute(
        """
        SELECT * FROM exploration_artifacts
        WHERE exploration_run_id = ? AND artifact_type = ?
        ORDER BY created_at ASC
        """,
        (run_id, artifact_type),
    ).fetchall()


def create(
    db: Connection,
    *,
    artifact_id: str,
    run_id: str,
    artifact_type: str,
    file_path: str,
    title: str = "",
    summary: str = "",
) -> None:
    """创建产物记录"""
    db.execute(
        """
        INSERT INTO exploration_artifacts (
            id, exploration_run_id, artifact_type,
            file_path, title, summary
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (artifact_id, run_id, artifact_type, file_path, title, summary),
    )


def update(
    db: Connection,
    artifact_id: str,
    *,
    title: str | None = None,
    summary: str | None = None,
) -> None:
    """更新产物信息"""
    assignments = []
    values = []

    if title is not None:
        assignments.append("title = ?")
        values.append(title)

    if summary is not None:
        assignments.append("summary = ?")
        values.append(summary)

    if not assignments:
        return

    values.append(artifact_id)
    db.execute(f"UPDATE exploration_artifacts SET {', '.join(assignments)} WHERE id = ?", values)


def count_by_run(db: Connection, run_id: str) -> int:
    """统计探索任务的产物数量"""
    result = db.execute(
        "SELECT COUNT(*) FROM exploration_artifacts WHERE exploration_run_id = ?",
        (run_id,),
    ).fetchone()
    return result[0] if result else 0


def delete(db: Connection, artifact_id: str) -> None:
    """删除产物记录"""
    db.execute("DELETE FROM exploration_artifacts WHERE id = ?", (artifact_id,))
