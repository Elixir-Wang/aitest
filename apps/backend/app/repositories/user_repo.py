from __future__ import annotations

from sqlite3 import Connection, Row


def find_by_login(db: Connection, login_name: str) -> Row | None:
    return db.execute(
        "SELECT * FROM users WHERE lower(username) = lower(?) OR lower(email) = lower(?)",
        (login_name, login_name),
    ).fetchone()


def find_by_id(db: Connection, user_id: str) -> Row | None:
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def list_all(db: Connection) -> list[Row]:
    return db.execute("SELECT * FROM users ORDER BY created_at DESC, username ASC").fetchall()


def create(
    db: Connection,
    *,
    user_id: str,
    username: str,
    email: str,
    nickname: str | None,
    password_hash: str,
    role: str,
    status: str,
    project_scope: str,
    description: str,
) -> None:
    db.execute(
        """
        INSERT INTO users (id, username, email, nickname, password_hash, role, status, project_scope, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, username, email, nickname, password_hash, role, status, project_scope, description),
    )


def update(db: Connection, user_id: str, assignments: list[str], values: list[object]) -> None:
    values.append(user_id)
    db.execute(f"UPDATE users SET {', '.join(assignments)} WHERE id = ?", values)


def update_login_time(db: Connection, user_id: str) -> None:
    db.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))


def delete(db: Connection, user_id: str) -> None:
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))

