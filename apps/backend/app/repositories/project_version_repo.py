from sqlite3 import Connection, Row


def list_by_project(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT pv.*,
               CASE WHEN p.default_version_id = pv.id THEN 1 ELSE 0 END AS is_default,
               COUNT(d.id) AS requirement_count
        FROM project_versions pv
        JOIN projects p ON p.id = pv.project_id
        LEFT JOIN source_documents d ON d.project_version_id = pv.id
        WHERE pv.project_id = ?
        GROUP BY pv.id
        ORDER BY pv.version_major DESC, pv.version_minor DESC, pv.version_patch DESC, pv.created_at DESC
        """,
        (project_id,),
    ).fetchall()


def find_by_id(db: Connection, version_id: str) -> Row | None:
    return db.execute(
        """
        SELECT pv.*,
               CASE WHEN p.default_version_id = pv.id THEN 1 ELSE 0 END AS is_default,
               (SELECT COUNT(*) FROM source_documents d WHERE d.project_version_id = pv.id) AS requirement_count
        FROM project_versions pv
        JOIN projects p ON p.id = pv.project_id
        WHERE pv.id = ?
        """,
        (version_id,),
    ).fetchone()


def find_by_project_and_id(db: Connection, project_id: str, version_id: str) -> Row | None:
    row = find_by_id(db, version_id)
    return row if row is not None and row["project_id"] == project_id else None


def create(
    db: Connection,
    *,
    version_id: str,
    project_id: str,
    version: str,
    major: int,
    minor: int,
    patch: int,
    name: str,
    description: str,
    planned_release_at: str | None,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO project_versions (
          id, project_id, version, version_major, version_minor, version_patch,
          name, description, planned_release_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (version_id, project_id, version, major, minor, patch, name, description, planned_release_at, created_by),
    )


def update_metadata(
    db: Connection,
    version_id: str,
    *,
    name: str,
    description: str,
    planned_release_at: str | None,
) -> None:
    db.execute(
        """
        UPDATE project_versions
        SET name = ?, description = ?, planned_release_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (name, description, planned_release_at, version_id),
    )


def set_default(db: Connection, project_id: str, version_id: str) -> None:
    db.execute(
        "UPDATE projects SET default_version_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (version_id, project_id),
    )


def delete(db: Connection, version_id: str) -> None:
    db.execute("DELETE FROM project_versions WHERE id = ?", (version_id,))
