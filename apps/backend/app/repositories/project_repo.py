from __future__ import annotations

from sqlite3 import Connection, Row


def list_visible(db: Connection, actor: Row) -> list[Row]:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return db.execute("SELECT * FROM projects WHERE status != 'archived' ORDER BY created_at ASC").fetchall()
    return db.execute(
        "SELECT * FROM projects WHERE status != 'archived' AND name = ? ORDER BY created_at ASC",
        (actor["project_scope"],),
    ).fetchall()


def list_all(db: Connection) -> list[Row]:
    return db.execute("SELECT * FROM projects ORDER BY created_at ASC, name ASC").fetchall()


def find_by_id(db: Connection, project_id: str) -> Row | None:
    return db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()


def create(db: Connection, *, project_id: str, name: str, status: str, description: str) -> None:
    db.execute(
        """
        INSERT INTO projects (id, name, status, description)
        VALUES (?, ?, ?, ?)
        """,
        (project_id, name, status, description),
    )


def update(db: Connection, project_id: str, assignments: list[str], values: list[object]) -> None:
    values.append(project_id)
    db.execute(f"UPDATE projects SET {', '.join(assignments)} WHERE id = ?", values)


def delete(db: Connection, project_id: str) -> None:
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
