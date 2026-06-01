from sqlite3 import Connection, Row


def create(db: Connection, token: str, user_id: str, expires_at: str) -> None:
    db.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))


def delete(db: Connection, token: str) -> None:
    db.execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_user_by_active_token(db: Connection, token: str) -> Row | None:
    return db.execute(
        """
        SELECT users.* FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ? AND sessions.expires_at > CURRENT_TIMESTAMP
        """,
        (token,),
    ).fetchone()

