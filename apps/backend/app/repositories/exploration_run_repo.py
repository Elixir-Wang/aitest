from sqlite3 import Connection, Row


def find_by_id(db: Connection, run_id: str) -> Row | None:
    """根据ID查找探索任务"""
    return db.execute("SELECT * FROM exploration_runs WHERE id = ?", (run_id,)).fetchone()


def find_detail_by_id(db: Connection, run_id: str) -> Row | None:
    """根据ID查找探索任务，并补齐详情页展示所需的关联信息。"""
    return db.execute(
        """
        SELECT er.*,
               p.name AS project_name,
               pe.name AS environment_name,
               pe.site_url AS environment_site_url,
               pe.login_strategy AS environment_login_strategy,
               pe.reuse_auth_state AS environment_reuse_auth_state,
               COALESCE(sd.name, '') AS requirement_doc_title
        FROM exploration_runs er
        JOIN projects p ON p.id = er.project_id
        JOIN project_environments pe ON pe.id = er.environment_id
        LEFT JOIN source_documents sd ON sd.id = er.requirement_doc_id
        WHERE er.id = ?
        """,
        (run_id,),
    ).fetchone()


def list_by_project(db: Connection, project_id: str, limit: int = 100) -> list[Row]:
    """列出项目的探索任务"""
    return db.execute(
        """
        SELECT * FROM exploration_runs
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (project_id, limit),
    ).fetchall()


def list_running(db: Connection, project_id: str | None = None) -> list[Row]:
    """列出运行中的探索任务"""
    if project_id:
        return db.execute(
            """
            SELECT * FROM exploration_runs
            WHERE project_id = ? AND status IN ('running', 'queued', 'stopping')
            ORDER BY created_at DESC
            """,
            (project_id,),
        ).fetchall()
    return db.execute(
        """
        SELECT * FROM exploration_runs
        WHERE status IN ('running', 'queued', 'stopping')
        ORDER BY created_at DESC
        """
    ).fetchall()


def list_all(db: Connection, project_id: str | None = None, limit: int = 100) -> list[Row]:
    """列出所有探索任务（支持全局和按项目筛选）"""
    if project_id:
        return db.execute(
            """
            SELECT * FROM exploration_runs
            WHERE project_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
    return db.execute(
        """
        SELECT * FROM exploration_runs
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def create(
    db: Connection,
    *,
    run_id: str,
    project_id: str,
    environment_id: str,
    title: str,
    created_by: str,
    exploration_mode: str,
    scope: str = "",
    forbidden_paths: str = "",
    goal: str = "",
    login_strategy: str = "skip_login",
    max_pages: int = 50,
    max_actions: int = 1000,
    timeout_minutes: int = 120,
    requirement_doc_id: str = "",
    notes: str = "",
) -> None:
    """创建探索任务"""
    db.execute(
        """
        INSERT INTO exploration_runs (
            id, project_id, environment_id, requirement_doc_id,
            title, status, exploration_mode, scope, forbidden_paths, login_strategy,
            goal, notes, max_pages, max_actions, timeout_minutes,
            created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            project_id,
            environment_id,
            requirement_doc_id,
            title,
            "pending",
            exploration_mode,
            scope,
            forbidden_paths,
            _resolve_environment_login_strategy(db, environment_id, login_strategy),
            goal,
            notes,
            max_pages,
            max_actions,
            timeout_minutes,
            created_by,
        ),
    )


def _resolve_environment_login_strategy(db: Connection, environment_id: str, fallback: str) -> str:
    environment = db.execute(
        "SELECT login_strategy FROM project_environments WHERE id = ?",
        (environment_id,),
    ).fetchone()
    if environment and environment["login_strategy"]:
        return environment["login_strategy"]
    return fallback


def update_status(
    db: Connection,
    run_id: str,
    status: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    result_summary: str = "",
) -> None:
    """更新探索任务状态"""
    assignments = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    values = [status]

    if started_at is not None:
        assignments.append("started_at = ?")
        values.append(started_at)

    if finished_at is not None:
        assignments.append("finished_at = ?")
        values.append(finished_at)

    if result_summary:
        assignments.append("result_summary = ?")
        values.append(result_summary)

    values.append(run_id)

    db.execute(f"UPDATE exploration_runs SET {', '.join(assignments)} WHERE id = ?", values)


def reset_completion_state(db: Connection, run_id: str) -> None:
    """清理上一轮完成态，准备记录本轮探索输出。"""
    db.execute(
        """
        UPDATE exploration_runs
        SET
            artifact_root = '',
            result_summary = '',
            started_at = NULL,
            finished_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (run_id,),
    )


def update_artifact_root(db: Connection, run_id: str, artifact_root: str) -> None:
    """更新产物根路径"""
    db.execute(
        "UPDATE exploration_runs SET artifact_root = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (artifact_root, run_id),
    )


def update(
    db: Connection,
    run_id: str,
    **kwargs,
) -> None:
    """更新探索任务字段

    支持的字段：
    - title, exploration_mode, scope, forbidden_paths, goal, notes
    - environment_id, requirement_doc_id
    - max_pages, max_actions, timeout_minutes
    """
    allowed_fields = {
        "title", "exploration_mode", "scope", "forbidden_paths", "goal", "notes",
        "environment_id", "requirement_doc_id",
        "max_pages", "max_actions", "timeout_minutes"
    }

    assignments = ["updated_at = CURRENT_TIMESTAMP"]
    values = []

    for field, value in kwargs.items():
        if field in allowed_fields:
            assignments.append(f"{field} = ?")
            values.append(value)

    if not values:
        return

    values.append(run_id)
    db.execute(
        f"UPDATE exploration_runs SET {', '.join(assignments)} WHERE id = ?",
        values
    )


def delete(db: Connection, run_id: str) -> None:
    """删除探索任务（级联删除相关记录）"""
    db.execute("DELETE FROM exploration_runs WHERE id = ?", (run_id,))
