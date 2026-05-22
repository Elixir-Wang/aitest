from __future__ import annotations

from sqlite3 import Connection, Row


BASE_SELECT = """
SELECT er.*, p.name AS project_name, pe.name AS environment_name
FROM exploration_runs er
JOIN projects p ON p.id = er.project_id
JOIN project_environments pe ON pe.id = er.environment_id
"""


def list_by_project(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        f"""
        {BASE_SELECT}
        WHERE er.project_id = ?
        ORDER BY er.updated_at DESC, er.created_at DESC
        """,
        (project_id,),
    ).fetchall()


def list_visible(db: Connection, actor: Row) -> list[Row]:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return db.execute(
            f"""
            {BASE_SELECT}
            WHERE p.status != 'archived'
            ORDER BY er.updated_at DESC, er.created_at DESC
            """
        ).fetchall()

    return db.execute(
        f"""
        {BASE_SELECT}
        WHERE p.status != 'archived' AND p.name = ?
        ORDER BY er.updated_at DESC, er.created_at DESC
        """,
        (actor["project_scope"],),
    ).fetchall()


def find_by_id(db: Connection, run_id: str) -> Row | None:
    return db.execute(f"{BASE_SELECT} WHERE er.id = ?", (run_id,)).fetchone()


def create(
    db: Connection,
    *,
    run_id: str,
    project_id: str,
    environment_id: str,
    title: str,
    scope: str,
    forbidden_paths: str,
    login_strategy: str,
    description: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO exploration_runs
          (id, project_id, environment_id, title, scope, forbidden_paths, login_strategy, description, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, project_id, environment_id, title, scope, forbidden_paths, login_strategy, description, created_by),
    )


def delete(db: Connection, run_id: str) -> None:
    db.execute("DELETE FROM exploration_runs WHERE id = ?", (run_id,))
