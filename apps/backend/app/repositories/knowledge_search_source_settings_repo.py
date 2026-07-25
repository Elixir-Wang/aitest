from sqlite3 import Connection, Row


def list_by_scope(db: Connection, scope_key: str) -> list[Row]:
    return db.execute(
        """
        SELECT scope_key, source_type, enabled, created_by, updated_by, created_at, updated_at
        FROM knowledge_search_source_settings
        WHERE scope_key = ?
        ORDER BY source_type
        """,
        (scope_key,),
    ).fetchall()


def replace_scope(db: Connection, scope_key: str, values: dict[str, bool], *, actor_id: str) -> None:
    db.execute("DELETE FROM knowledge_search_source_settings WHERE scope_key = ?", (scope_key,))
    db.executemany(
        """
        INSERT INTO knowledge_search_source_settings (scope_key, source_type, enabled, created_by, updated_by)
        VALUES (?, ?, ?, ?, ?)
        """,
        [(scope_key, source_type, int(enabled), actor_id, actor_id) for source_type, enabled in values.items()],
    )


def delete_scope(db: Connection, scope_key: str) -> None:
    db.execute("DELETE FROM knowledge_search_source_settings WHERE scope_key = ?", (scope_key,))
