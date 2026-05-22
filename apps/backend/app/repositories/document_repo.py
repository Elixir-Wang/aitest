from __future__ import annotations

from sqlite3 import Connection, Row


def find_by_project_and_id(db: Connection, project_id: str, document_id: str) -> Row | None:
    return db.execute(
        "SELECT * FROM source_documents WHERE project_id = ? AND id = ?",
        (project_id, document_id),
    ).fetchone()


def find_by_project_and_name(db: Connection, project_id: str, name: str, exclude_id: str | None = None) -> Row | None:
    if exclude_id:
        return db.execute(
            "SELECT * FROM source_documents WHERE project_id = ? AND name = ? AND id != ?",
            (project_id, name, exclude_id),
        ).fetchone()
    return db.execute(
        "SELECT * FROM source_documents WHERE project_id = ? AND name = ?",
        (project_id, name),
    ).fetchone()


def list_by_project(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT d.*,
               COUNT(m.id) AS file_count,
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
        LEFT JOIN source_document_file_mappings m ON m.document_id = d.id
        WHERE d.project_id = ?
        GROUP BY d.id
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
    status: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (document_id, project_id, name, document_type, status, created_by),
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


def next_version_no(db: Connection, document_id: str) -> int:
    row = db.execute(
        "SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version_no FROM source_document_versions WHERE document_id = ?",
        (document_id,),
    ).fetchone()
    return int(row["next_version_no"])


def update_current_version(db: Connection, document_id: str, version_id: str, status: str) -> None:
    db.execute(
        "UPDATE source_documents SET current_version_id = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (version_id, status, document_id),
    )


def update_document_status(db: Connection, document_id: str, status: str) -> None:
    db.execute(
        "UPDATE source_documents SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, document_id),
    )


def update_document_name(db: Connection, document_id: str, name: str) -> None:
    db.execute(
        "UPDATE source_documents SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (name, document_id),
    )


def update_file_mapping_markdown(db: Connection, mapping_id: str, markdown_file_path: str, conversion_summary: str) -> None:
    db.execute(
        """
        UPDATE source_document_file_mappings
        SET markdown_file_path = ?,
            conversion_status = 'success',
            conversion_summary = ?,
            conversion_quality = 100
        WHERE id = ?
        """,
        (markdown_file_path, conversion_summary, mapping_id),
    )


def mark_file_mappings_merged(db: Connection, document_id: str, version_id: str) -> None:
    db.execute(
        """
        UPDATE source_document_file_mappings
        SET version_id = ?, mapping_status = 'merged'
        WHERE document_id = ?
          AND conversion_status IN ('success', 'warning')
          AND mapping_status != 'discarded'
        """,
        (version_id, document_id),
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
    version_id: str | None,
    source_file_path: str,
    original_filename: str,
    file_format: str,
    markdown_file_path: str | None,
    conversion_status: str,
    mapping_status: str,
    conversion_summary: str,
    created_by: str,
    conversion_quality: int | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO source_document_file_mappings
          (id, document_id, version_id, source_file_path, original_filename, file_format, markdown_file_path,
           conversion_status, mapping_status, conversion_summary, conversion_quality, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mapping_id,
            document_id,
            version_id,
            source_file_path,
            original_filename,
            file_format,
            markdown_file_path,
            conversion_status,
            mapping_status,
            conversion_summary,
            conversion_quality,
            created_by,
        ),
    )


def list_file_mappings(db: Connection, document_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT m.*,
               v.version_no AS version_no
        FROM source_document_file_mappings m
        LEFT JOIN source_document_versions v ON v.id = m.version_id
        WHERE m.document_id = ?
        ORDER BY m.created_at DESC, m.id DESC
        """,
        (document_id,),
    ).fetchall()


def find_file_mapping(db: Connection, mapping_id: str) -> Row | None:
    return db.execute(
        """
        SELECT m.*, d.project_id
        FROM source_document_file_mappings m
        JOIN source_documents d ON d.id = m.document_id
        WHERE m.id = ?
        """,
        (mapping_id,),
    ).fetchone()


def delete_file_mapping(db: Connection, mapping_id: str) -> None:
    db.execute("DELETE FROM source_document_file_mappings WHERE id = ?", (mapping_id,))


def list_conflicts(db: Connection, document_id: str, *, status: str | None = None) -> list[Row]:
    if status:
        return db.execute(
            """
            SELECT *
            FROM source_document_merge_conflicts
            WHERE document_id = ? AND status = ?
            ORDER BY created_at DESC, id DESC
            """,
            (document_id, status),
        ).fetchall()
    return db.execute(
        """
        SELECT *
        FROM source_document_merge_conflicts
        WHERE document_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (document_id,),
    ).fetchall()


def create_conflict(
    db: Connection,
    *,
    conflict_id: str,
    document_id: str,
    title: str,
    source_file_names: str,
    fragment_a: str,
    fragment_b: str,
) -> None:
    db.execute(
        """
        INSERT INTO source_document_merge_conflicts
          (id, document_id, title, source_file_names, fragment_a, fragment_b, status)
        VALUES (?, ?, ?, ?, ?, ?, 'open')
        """,
        (conflict_id, document_id, title, source_file_names, fragment_a, fragment_b),
    )


def resolve_conflict(db: Connection, conflict_id: str, resolution: str, resolution_type: str) -> None:
    db.execute(
        """
        UPDATE source_document_merge_conflicts
        SET resolution = ?, resolution_type = ?, status = 'resolved', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (resolution, resolution_type, conflict_id),
    )


def close_open_conflicts(db: Connection, document_id: str) -> None:
    db.execute(
        """
        UPDATE source_document_merge_conflicts
        SET status = 'resolved', updated_at = CURRENT_TIMESTAMP
        WHERE document_id = ? AND status = 'open'
        """,
        (document_id,),
    )
