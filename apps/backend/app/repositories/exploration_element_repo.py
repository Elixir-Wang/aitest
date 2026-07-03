from sqlite3 import Connection, Row


def find_by_id(db: Connection, element_id: str) -> Row | None:
    """根据ID查找元素"""
    return db.execute("SELECT * FROM exploration_elements WHERE id = ?", (element_id,)).fetchone()


def list_by_run(db: Connection, run_id: str) -> list[Row]:
    """列出探索任务的所有元素"""
    return db.execute(
        """
        SELECT * FROM exploration_elements
        WHERE exploration_run_id = ?
        ORDER BY created_at ASC
        """,
        (run_id,),
    ).fetchall()


def list_by_page(db: Connection, page_id: str) -> list[Row]:
    """列出页面的所有元素"""
    return db.execute(
        """
        SELECT * FROM exploration_elements
        WHERE page_id = ?
        ORDER BY created_at ASC
        """,
        (page_id,),
    ).fetchall()


def list_by_module(db: Connection, run_id: str, module_key: str) -> list[Row]:
    """列出特定模块的元素"""
    return db.execute(
        """
        SELECT * FROM exploration_elements
        WHERE exploration_run_id = ? AND module_key = ?
        ORDER BY created_at ASC
        """,
        (run_id, module_key),
    ).fetchall()


def create(
    db: Connection,
    *,
    element_id: str,
    run_id: str,
    element_name: str,
    page_id: str | None = None,
    module_key: str = "",
    element_type: str = "",
    recommended_locator: str = "",
    fallback_locator: str = "",
    stability_note: str = "",
    source_ref: str = "",
) -> None:
    """创建元素记录"""
    db.execute(
        """
        INSERT INTO exploration_elements (
            id, exploration_run_id, page_id, module_key,
            element_name, element_type, recommended_locator,
            fallback_locator, stability_note, source_ref
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            element_id,
            run_id,
            page_id,
            module_key,
            element_name,
            element_type,
            recommended_locator,
            fallback_locator,
            stability_note,
            source_ref,
        ),
    )


def update(
    db: Connection,
    element_id: str,
    *,
    recommended_locator: str | None = None,
    fallback_locator: str | None = None,
    stability_note: str | None = None,
) -> None:
    """更新元素信息"""
    assignments = []
    values = []

    if recommended_locator is not None:
        assignments.append("recommended_locator = ?")
        values.append(recommended_locator)

    if fallback_locator is not None:
        assignments.append("fallback_locator = ?")
        values.append(fallback_locator)

    if stability_note is not None:
        assignments.append("stability_note = ?")
        values.append(stability_note)

    if not assignments:
        return

    values.append(element_id)
    db.execute(f"UPDATE exploration_elements SET {', '.join(assignments)} WHERE id = ?", values)


def count_by_run(db: Connection, run_id: str) -> int:
    """统计探索任务的元素数量"""
    result = db.execute(
        "SELECT COUNT(*) FROM exploration_elements WHERE exploration_run_id = ?",
        (run_id,),
    ).fetchone()
    return result[0] if result else 0


def count_by_page(db: Connection, page_id: str) -> int:
    """统计页面的元素数量"""
    result = db.execute(
        "SELECT COUNT(*) FROM exploration_elements WHERE page_id = ?",
        (page_id,),
    ).fetchone()
    return result[0] if result else 0


def delete(db: Connection, element_id: str) -> None:
    """删除元素记录"""
    db.execute("DELETE FROM exploration_elements WHERE id = ?", (element_id,))
