from __future__ import annotations

from sqlite3 import Connection, Row


def list_by_project(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT pe.*, p.name AS project_name
        FROM project_environments pe
        JOIN projects p ON p.id = pe.project_id
        WHERE pe.project_id = ?
        ORDER BY pe.updated_at DESC, pe.created_at DESC
        """,
        (project_id,),
    ).fetchall()


def list_visible(db: Connection, actor: Row) -> list[Row]:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return db.execute(
            """
            SELECT pe.*, p.name AS project_name
            FROM project_environments pe
            JOIN projects p ON p.id = pe.project_id
            WHERE p.status != 'archived'
            ORDER BY pe.updated_at DESC, pe.created_at DESC
            """
        ).fetchall()

    return db.execute(
        """
        SELECT pe.*, p.name AS project_name
        FROM project_environments pe
        JOIN projects p ON p.id = pe.project_id
        WHERE p.status != 'archived' AND p.name = ?
        ORDER BY pe.updated_at DESC, pe.created_at DESC
        """,
        (actor["project_scope"],),
    ).fetchall()


def find_by_id(db: Connection, environment_id: str) -> Row | None:
    return db.execute(
        """
        SELECT pe.*, p.name AS project_name
        FROM project_environments pe
        JOIN projects p ON p.id = pe.project_id
        WHERE pe.id = ?
        """,
        (environment_id,),
    ).fetchone()


def create(
    db: Connection,
    *,
    environment_id: str,
    project_id: str,
    name: str,
    site_url: str,
    username: str,
    password_mask: str,
    description: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO project_environments
          (id, project_id, name, site_url, username, password_mask, description, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (environment_id, project_id, name, site_url, username, password_mask, description, created_by),
    )


def delete(db: Connection, environment_id: str) -> None:
    db.execute("DELETE FROM project_environments WHERE id = ?", (environment_id,))


def update(db: Connection, environment_id: str, assignments: list[str], values: list[object]) -> None:
    values.append(environment_id)
    db.execute(f"UPDATE project_environments SET {', '.join(assignments)} WHERE id = ?", values)
