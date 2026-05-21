from __future__ import annotations

from sqlite3 import Connection, Row


def find_by_project_and_id(db: Connection, project_id: str, document_id: str) -> Row | None:
    return db.execute(
        "SELECT * FROM source_documents WHERE project_id = ? AND id = ?",
        (project_id, document_id),
    ).fetchone()


def list_by_project(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT d.*,
               v.id AS version_id,
               v.version_no AS version_no,
               v.file_path AS markdown_file_path,
               v.source_action AS source_action,
               v.change_summary AS change_summary,
               v.diff_summary AS diff_summary,
               v.created_by AS version_created_by,
               v.created_at AS version_created_at
        FROM source_documents d
        LEFT JOIN source_document_versions v ON v.id = d.current_version_id
        WHERE d.project_id = ?
        ORDER BY d.created_at DESC
        """,
        (project_id,),
    ).fetchall()


def delete(db: Connection, document_id: str) -> None:
    db.execute("DELETE FROM source_documents WHERE id = ?", (document_id,))


def delete_graph(db: Connection, document_id: str) -> None:
    db.execute("DELETE FROM source_document_file_mappings WHERE document_id = ?", (document_id,))
    db.execute("DELETE FROM source_document_versions WHERE document_id = ?", (document_id,))
    db.execute("DELETE FROM source_documents WHERE id = ?", (document_id,))


def create_document(
    db: Connection,
    *,
    document_id: str,
    project_id: str,
    name: str,
    document_type: str,
    original_file_path: str,
    status: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO source_documents (id, project_id, name, document_type, original_file_path, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (document_id, project_id, name, document_type, original_file_path, status, created_by),
    )


def create_version(
    db: Connection,
    *,
    version_id: str,
    document_id: str,
    version_no: int,
    file_path: str,
    source_action: str,
    change_summary: str,
    diff_summary: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO source_document_versions
          (id, document_id, version_no, markdown_content, file_path, source_action, change_summary, diff_summary, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (version_id, document_id, version_no, "", file_path, source_action, change_summary, diff_summary, created_by),
    )


def update_current_version(db: Connection, document_id: str, version_id: str, status: str) -> None:
    db.execute(
        "UPDATE source_documents SET current_version_id = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (version_id, status, document_id),
    )


def find_versions_by_document(db: Connection, document_id: str) -> list[Row]:
    return db.execute(
        "SELECT id, document_id, version_no, file_path, source_action, change_summary, diff_summary, created_by, created_at FROM source_document_versions WHERE document_id = ? ORDER BY version_no DESC",
        (document_id,),
    ).fetchall()


def create_file_mapping(
    db: Connection,
    *,
    mapping_id: str,
    document_id: str,
    version_id: str,
    source_file_path: str,
    markdown_file_path: str,
    mapping_status: str,
    conversion_summary: str,
) -> None:
    db.execute(
        """
        INSERT INTO source_document_file_mappings
          (id, document_id, version_id, source_file_path, markdown_file_path, mapping_status, conversion_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (mapping_id, document_id, version_id, source_file_path, markdown_file_path, mapping_status, conversion_summary),
    )
