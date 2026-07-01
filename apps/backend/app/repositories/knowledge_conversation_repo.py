import json
from sqlite3 import Connection, Row


def list_by_project(db: Connection, project_id: str, created_by: str) -> list[Row]:
    return db.execute(
        """
        SELECT * FROM knowledge_conversations
        WHERE project_id = ? AND created_by = ?
        ORDER BY updated_at DESC, created_at DESC
        """,
        (project_id, created_by),
    ).fetchall()


def find_by_project_and_id(db: Connection, project_id: str, conversation_id: str, created_by: str) -> Row | None:
    return db.execute(
        """
        SELECT * FROM knowledge_conversations
        WHERE project_id = ? AND id = ? AND created_by = ?
        """,
        (project_id, conversation_id, created_by),
    ).fetchone()


def create(db: Connection, *, conversation_id: str, project_id: str, title: str, created_by: str) -> Row:
    db.execute(
        """
        INSERT INTO knowledge_conversations (id, project_id, title, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (conversation_id, project_id, title, created_by),
    )
    return db.execute("SELECT * FROM knowledge_conversations WHERE id = ?", (conversation_id,)).fetchone()


def rename(db: Connection, conversation_id: str, title: str) -> None:
    db.execute(
        """
        UPDATE knowledge_conversations
        SET title = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (title, conversation_id),
    )


def touch(db: Connection, conversation_id: str) -> None:
    db.execute(
        """
        UPDATE knowledge_conversations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (conversation_id,),
    )


def delete(db: Connection, conversation_id: str) -> None:
    db.execute("DELETE FROM knowledge_conversations WHERE id = ?", (conversation_id,))


def list_messages(db: Connection, conversation_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT * FROM knowledge_conversation_messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (conversation_id,),
    ).fetchall()


def create_message(
    db: Connection,
    *,
    message_id: str,
    conversation_id: str,
    role: str,
    content: str,
    source_refs: list[dict] | None = None,
    used_requirement_versions: list[str] | None = None,
) -> Row:
    db.execute(
        """
        INSERT INTO knowledge_conversation_messages
          (id, conversation_id, role, content, source_refs_json, used_requirement_versions_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            conversation_id,
            role,
            content,
            json.dumps(source_refs or [], ensure_ascii=False),
            json.dumps(used_requirement_versions or [], ensure_ascii=False),
        ),
    )
    touch(db, conversation_id)
    return db.execute("SELECT * FROM knowledge_conversation_messages WHERE id = ?", (message_id,)).fetchone()
