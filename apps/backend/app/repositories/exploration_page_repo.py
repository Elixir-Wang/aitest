from sqlite3 import Connection, Row


def find_by_id(db: Connection, page_id: str) -> Row | None:
    """根据ID查找页面"""
    return db.execute("SELECT * FROM exploration_pages WHERE id = ?", (page_id,)).fetchone()


def list_by_run(db: Connection, run_id: str) -> list[Row]:
    """列出探索任务的所有页面"""
    return db.execute(
        """
        SELECT * FROM exploration_pages
        WHERE exploration_run_id = ?
        ORDER BY created_at ASC
        """,
        (run_id,),
    ).fetchall()


def list_by_module(db: Connection, run_id: str, module_key: str) -> list[Row]:
    """列出特定模块的页面"""
    return db.execute(
        """
        SELECT * FROM exploration_pages
        WHERE exploration_run_id = ? AND module_key = ?
        ORDER BY created_at ASC
        """,
        (run_id, module_key),
    ).fetchall()


def find_by_url(db: Connection, run_id: str, entry_path: str) -> Row | None:
    """根据URL路径查找页面"""
    return db.execute(
        """
        SELECT * FROM exploration_pages
        WHERE exploration_run_id = ? AND entry_path = ?
        """,
        (run_id, entry_path),
    ).fetchone()


def create(
    db: Connection,
    *,
    page_id: str,
    run_id: str,
    title: str,
    url: str,
    entry_path: str,
    module_key: str = "",
    structure_summary: str = "",
    screenshot_path: str = "",
    snapshot_path: str = "",
    trace_path: str = "",
) -> None:
    """创建页面记录"""
    db.execute(
        """
        INSERT INTO exploration_pages (
            id, exploration_run_id, module_key, title, url,
            entry_path, structure_summary, screenshot_path,
            snapshot_path, trace_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            page_id,
            run_id,
            module_key,
            title,
            url,
            entry_path,
            structure_summary,
            screenshot_path,
            snapshot_path,
            trace_path,
        ),
    )


def update(
    db: Connection,
    page_id: str,
    *,
    title: str | None = None,
    structure_summary: str | None = None,
    screenshot_path: str | None = None,
    snapshot_path: str | None = None,
    trace_path: str | None = None,
) -> None:
    """更新页面信息"""
    assignments = []
    values = []

    if title is not None:
        assignments.append("title = ?")
        values.append(title)

    if structure_summary is not None:
        assignments.append("structure_summary = ?")
        values.append(structure_summary)

    if screenshot_path is not None:
        assignments.append("screenshot_path = ?")
        values.append(screenshot_path)

    if snapshot_path is not None:
        assignments.append("snapshot_path = ?")
        values.append(snapshot_path)

    if trace_path is not None:
        assignments.append("trace_path = ?")
        values.append(trace_path)

    if not assignments:
        return

    values.append(page_id)
    db.execute(f"UPDATE exploration_pages SET {', '.join(assignments)} WHERE id = ?", values)


def count_by_run(db: Connection, run_id: str) -> int:
    """统计探索任务的页面数量"""
    result = db.execute(
        "SELECT COUNT(*) FROM exploration_pages WHERE exploration_run_id = ?",
        (run_id,),
    ).fetchone()
    return result[0] if result else 0


def delete(db: Connection, page_id: str) -> None:
    """删除页面记录"""
    db.execute("DELETE FROM exploration_pages WHERE id = ?", (page_id,))
