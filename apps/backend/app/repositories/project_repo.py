from sqlite3 import Connection, Row

SYSTEM_RESERVED_PROJECT_IDS = ("__all_projects__", "__global_environments__")

PROJECT_ASSET_TABLES = (
    "source_documents",
    "exploration_runs",
    "test_cases",
    "automation_cases",
    "automation_runs",
)


def list_visible(db: Connection, actor: Row) -> list[Row]:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return db.execute("SELECT * FROM projects WHERE status != 'archived' ORDER BY created_at ASC").fetchall()
    return db.execute(
        "SELECT * FROM projects WHERE status != 'archived' AND name = ? ORDER BY created_at ASC",
        (actor["project_scope"],),
    ).fetchall()


def list_all(db: Connection) -> list[Row]:
    placeholders = ", ".join("?" for _ in SYSTEM_RESERVED_PROJECT_IDS)
    return db.execute(
        f"SELECT * FROM projects WHERE id NOT IN ({placeholders}) ORDER BY created_at ASC, name ASC",
        SYSTEM_RESERVED_PROJECT_IDS,
    ).fetchall()


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


def has_project_assets(db: Connection, project_id: str) -> bool:
    for table in PROJECT_ASSET_TABLES:
        if not _table_exists(db, table):
            continue
        if db.execute(f"SELECT 1 FROM {table} WHERE project_id = ? LIMIT 1", (project_id,)).fetchone():
            return True
    return False


def list_requirement_names(db: Connection, project_id: str) -> list[str]:
    if not _table_exists(db, "source_documents"):
        return []
    rows = db.execute(
        "SELECT name FROM source_documents WHERE project_id = ? ORDER BY created_at ASC",
        (project_id,),
    ).fetchall()
    return [row["name"] for row in rows]


def _table_exists(db: Connection, table: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None
