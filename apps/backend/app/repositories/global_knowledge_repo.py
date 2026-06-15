from sqlite3 import Connection, Row


def list_documents(db: Connection, filters: dict) -> tuple[list[Row], int]:
    where: list[str] = []
    values: list[object] = []
    keyword = str(filters.get("keyword") or "").strip()
    knowledge_type = str(filters.get("knowledge_type") or "").strip()
    status = str(filters.get("status") or "").strip()
    if keyword:
        where.append("(d.name LIKE ? OR d.description LIKE ? OR d.source_note LIKE ?)")
        like = f"%{keyword}%"
        values.extend([like, like, like])
    if knowledge_type:
        where.append("d.knowledge_type = ?")
        values.append(knowledge_type)
    if status:
        where.append("d.status = ?")
        values.append(status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    total = db.execute(f"SELECT COUNT(*) AS total FROM global_knowledge_documents d {where_sql}", values).fetchone()["total"]
    page = max(1, int(filters.get("page") or 1))
    page_size = max(1, min(200, int(filters.get("page_size") or 20)))
    rows = db.execute(
        f"""
        SELECT d.*,
               v.version_no AS current_version_no,
               v.conversion_status AS current_conversion_status,
               COUNT(f.id) AS file_count
        FROM global_knowledge_documents d
        LEFT JOIN global_knowledge_versions v ON v.id = d.current_version_id
        LEFT JOIN global_knowledge_files f ON f.version_id = v.id
        {where_sql}
        GROUP BY d.id
        ORDER BY d.updated_at DESC, d.created_at DESC
        LIMIT ? OFFSET ?
        """,
        [*values, page_size, (page - 1) * page_size],
    ).fetchall()
    return rows, int(total)


def find_document(db: Connection, document_id: str) -> Row | None:
    return db.execute("SELECT * FROM global_knowledge_documents WHERE id = ?", (document_id,)).fetchone()


def find_document_by_name_type(db: Connection, name: str, knowledge_type: str, exclude_id: str | None = None) -> Row | None:
    if exclude_id:
        return db.execute(
            "SELECT * FROM global_knowledge_documents WHERE name = ? AND knowledge_type = ? AND id != ?",
            (name, knowledge_type, exclude_id),
        ).fetchone()
    return db.execute(
        "SELECT * FROM global_knowledge_documents WHERE name = ? AND knowledge_type = ?",
        (name, knowledge_type),
    ).fetchone()


def create_document(
    db: Connection,
    *,
    document_id: str,
    name: str,
    knowledge_type: str,
    scope: str,
    source_note: str,
    description: str,
    status: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO global_knowledge_documents
          (id, name, knowledge_type, scope, source_note, description, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (document_id, name, knowledge_type, scope, source_note, description, status, created_by),
    )


def update_document_metadata(
    db: Connection,
    document_id: str,
    *,
    name: str,
    knowledge_type: str,
    scope: str,
    source_note: str,
    description: str,
) -> None:
    db.execute(
        """
        UPDATE global_knowledge_documents
        SET name = ?, knowledge_type = ?, scope = ?, source_note = ?, description = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (name, knowledge_type, scope, source_note, description, document_id),
    )


def update_document_status(db: Connection, document_id: str, *, status: str, current_version_id: str | None = None) -> None:
    assignments = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    values: list[object] = [status]
    if current_version_id is not None:
        assignments.append("current_version_id = ?")
        values.append(current_version_id)
    if status == "archived":
        assignments.append("archived_at = CURRENT_TIMESTAMP")
    values.append(document_id)
    db.execute(f"UPDATE global_knowledge_documents SET {', '.join(assignments)} WHERE id = ?", values)


def create_version(
    db: Connection,
    *,
    version_id: str,
    document_id: str,
    version_no: str,
    markdown_content: str,
    markdown_path: str,
    change_summary: str,
    conversion_status: str,
    conversion_summary: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO global_knowledge_versions
          (id, document_id, version_no, markdown_content, markdown_path, change_summary,
           conversion_status, conversion_summary, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            document_id,
            version_no,
            markdown_content,
            markdown_path,
            change_summary,
            conversion_status,
            conversion_summary,
            created_by,
        ),
    )


def update_version_conversion(
    db: Connection,
    version_id: str,
    *,
    markdown_content: str,
    markdown_path: str,
    conversion_status: str,
    conversion_summary: str,
) -> None:
    db.execute(
        """
        UPDATE global_knowledge_versions
        SET markdown_content = ?, markdown_path = ?, conversion_status = ?, conversion_summary = ?
        WHERE id = ?
        """,
        (markdown_content, markdown_path, conversion_status, conversion_summary, version_id),
    )


def list_versions(db: Connection, document_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM global_knowledge_versions
        WHERE document_id = ?
        ORDER BY created_at DESC
        """,
        (document_id,),
    ).fetchall()


def find_version(db: Connection, version_id: str) -> Row | None:
    return db.execute("SELECT * FROM global_knowledge_versions WHERE id = ?", (version_id,)).fetchone()


def find_current_version(db: Connection, document_id: str) -> Row | None:
    return db.execute(
        """
        SELECT v.*
        FROM global_knowledge_documents d
        JOIN global_knowledge_versions v ON v.id = d.current_version_id
        WHERE d.id = ?
        """,
        (document_id,),
    ).fetchone()


def create_file(
    db: Connection,
    *,
    file_id: str,
    version_id: str,
    original_filename: str,
    file_path: str,
    file_type: str,
    file_size: int,
) -> None:
    db.execute(
        """
        INSERT INTO global_knowledge_files
          (id, version_id, original_filename, file_path, file_type, file_size)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (file_id, version_id, original_filename, file_path, file_type, file_size),
    )


def list_files_by_version(db: Connection, version_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM global_knowledge_files WHERE version_id = ? ORDER BY created_at ASC",
        (version_id,),
    ).fetchall()


def list_usage_logs(db: Connection, version_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM global_knowledge_usage_logs WHERE global_knowledge_version_id = ? ORDER BY created_at DESC",
        (version_id,),
    ).fetchall()


def list_bases(db: Connection, keyword: str = "") -> list[Row]:
    keyword = keyword.strip()
    values: list[object] = []
    where_sql = ""
    if keyword:
        where_sql = "WHERE b.name LIKE ? OR b.description LIKE ?"
        like = f"%{keyword}%"
        values.extend([like, like])
    return db.execute(
        f"""
        SELECT b.*,
               COUNT(f.id) AS file_count
        FROM global_knowledge_bases b
        LEFT JOIN global_knowledge_vault_files f ON f.knowledge_base_id = b.id
        {where_sql}
        GROUP BY b.id
        ORDER BY b.updated_at DESC, b.created_at DESC
        """,
        values,
    ).fetchall()


def find_base(db: Connection, base_id: str) -> Row | None:
    return db.execute(
        """
        SELECT b.*,
               COUNT(f.id) AS file_count
        FROM global_knowledge_bases b
        LEFT JOIN global_knowledge_vault_files f ON f.knowledge_base_id = b.id
        WHERE b.id = ?
        GROUP BY b.id
        """,
        (base_id,),
    ).fetchone()


def find_base_by_name(db: Connection, name: str, exclude_id: str | None = None) -> Row | None:
    if exclude_id:
        return db.execute("SELECT * FROM global_knowledge_bases WHERE name = ? AND id != ?", (name, exclude_id)).fetchone()
    return db.execute("SELECT * FROM global_knowledge_bases WHERE name = ?", (name,)).fetchone()


def create_base(db: Connection, *, base_id: str, name: str, description: str, root_folder_id: str, created_by: str) -> None:
    db.execute(
        """
        INSERT INTO global_knowledge_bases (id, name, description, status, root_folder_id, created_by)
        VALUES (?, ?, ?, 'available', ?, ?)
        """,
        (base_id, name, description, root_folder_id, created_by),
    )


def touch_base(db: Connection, base_id: str) -> None:
    db.execute("UPDATE global_knowledge_bases SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (base_id,))


def delete_base(db: Connection, base_id: str) -> None:
    db.execute("DELETE FROM global_knowledge_bases WHERE id = ?", (base_id,))


def create_folder(
    db: Connection,
    *,
    folder_id: str,
    base_id: str,
    parent_id: str | None,
    name: str,
    sort_order: int = 0,
) -> None:
    db.execute(
        """
        INSERT INTO global_knowledge_folders (id, knowledge_base_id, parent_id, name, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        (folder_id, base_id, parent_id, name, sort_order),
    )


def find_folder(db: Connection, folder_id: str) -> Row | None:
    return db.execute("SELECT * FROM global_knowledge_folders WHERE id = ?", (folder_id,)).fetchone()


def find_folder_in_base(db: Connection, base_id: str, folder_id: str) -> Row | None:
    return db.execute(
        "SELECT * FROM global_knowledge_folders WHERE knowledge_base_id = ? AND id = ?",
        (base_id, folder_id),
    ).fetchone()


def list_folders_by_base(db: Connection, base_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM global_knowledge_folders
        WHERE knowledge_base_id = ?
        ORDER BY parent_id IS NOT NULL, parent_id, sort_order, name
        """,
        (base_id,),
    ).fetchall()


def list_files_by_base(db: Connection, base_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM global_knowledge_vault_files
        WHERE knowledge_base_id = ?
        ORDER BY folder_id, sort_order, display_name
        """,
        (base_id,),
    ).fetchall()


def list_files_by_folder(db: Connection, folder_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM global_knowledge_vault_files WHERE folder_id = ? ORDER BY sort_order, display_name",
        (folder_id,),
    ).fetchall()


def list_child_folders(db: Connection, base_id: str, parent_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM global_knowledge_folders
        WHERE knowledge_base_id = ? AND parent_id = ?
        ORDER BY sort_order, name
        """,
        (base_id, parent_id),
    ).fetchall()


def find_folder_by_parent_and_name(db: Connection, base_id: str, parent_id: str, name: str) -> Row | None:
    return db.execute(
        """
        SELECT *
        FROM global_knowledge_folders
        WHERE knowledge_base_id = ? AND parent_id = ? AND name = ?
        """,
        (base_id, parent_id, name),
    ).fetchone()


def find_vault_file_by_folder_and_name(db: Connection, folder_id: str, display_name: str) -> Row | None:
    return db.execute(
        "SELECT * FROM global_knowledge_vault_files WHERE folder_id = ? AND display_name = ?",
        (folder_id, display_name),
    ).fetchone()


def update_folder_sort_order(db: Connection, folder_id: str, sort_order: int) -> None:
    db.execute(
        "UPDATE global_knowledge_folders SET sort_order = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (sort_order, folder_id),
    )


def update_vault_file_sort_order(db: Connection, file_id: str, sort_order: int) -> None:
    db.execute(
        "UPDATE global_knowledge_vault_files SET sort_order = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (sort_order, file_id),
    )


def create_vault_file(
    db: Connection,
    *,
    file_id: str,
    base_id: str,
    folder_id: str,
    original_filename: str,
    display_name: str,
    file_type: str,
    file_size: int,
    raw_path: str,
    markdown_path: str,
    markdown_content: str,
    conversion_status: str,
    conversion_summary: str,
) -> None:
    db.execute(
        """
        INSERT INTO global_knowledge_vault_files
          (id, knowledge_base_id, folder_id, original_filename, display_name, file_type, file_size,
           raw_path, markdown_path, markdown_content, conversion_status, conversion_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_id,
            base_id,
            folder_id,
            original_filename,
            display_name,
            file_type,
            file_size,
            raw_path,
            markdown_path,
            markdown_content,
            conversion_status,
            conversion_summary,
        ),
    )


def find_vault_file(db: Connection, base_id: str, file_id: str) -> Row | None:
    return db.execute(
        "SELECT * FROM global_knowledge_vault_files WHERE knowledge_base_id = ? AND id = ?",
        (base_id, file_id),
    ).fetchone()


def delete_vault_file(db: Connection, file_id: str) -> None:
    db.execute("DELETE FROM global_knowledge_vault_files WHERE id = ?", (file_id,))


def descendant_folder_ids(db: Connection, base_id: str, folder_id: str) -> list[str]:
    rows = db.execute(
        """
        WITH RECURSIVE folder_tree(id) AS (
          SELECT id FROM global_knowledge_folders WHERE knowledge_base_id = ? AND id = ?
          UNION ALL
          SELECT child.id
          FROM global_knowledge_folders child
          JOIN folder_tree parent ON child.parent_id = parent.id
          WHERE child.knowledge_base_id = ?
        )
        SELECT id FROM folder_tree
        """,
        (base_id, folder_id, base_id),
    ).fetchall()
    return [row["id"] for row in rows]


def delete_folders(db: Connection, folder_ids: list[str]) -> None:
    if not folder_ids:
        return
    placeholders = ",".join("?" for _ in folder_ids)
    db.execute(f"DELETE FROM global_knowledge_folders WHERE id IN ({placeholders})", folder_ids)
