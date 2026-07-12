from sqlite3 import Connection, Row

def list_all(db: Connection, project_id: str | None = None) -> list[Row]:
    where = "WHERE pe.project_id = ?" if project_id else ""
    params = (project_id,) if project_id else ()
    return db.execute(
        f"""
        SELECT pe.*, p.name AS project_name
        FROM project_environments pe
        JOIN projects p ON p.id = pe.project_id
        {where}
        ORDER BY pe.updated_at DESC, pe.created_at DESC
        """,
        params,
    ).fetchall()


def list_visible(db: Connection, actor, project_id: str | None = None) -> list[Row]:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return list_all(db, project_id)
    params: list[object] = [actor["project_scope"]]
    project_filter = ""
    if project_id:
        project_filter = "AND pe.project_id = ?"
        params.append(project_id)
    return db.execute(
        f"""
        SELECT pe.*, p.name AS project_name
        FROM project_environments pe
        JOIN projects p ON p.id = pe.project_id
        WHERE p.name = ? AND p.status != 'archived'
        {project_filter}
        ORDER BY pe.updated_at DESC, pe.created_at DESC
        """,
        params,
    ).fetchall()


def find_by_id(db: Connection, environment_id: str) -> Row | None:
    return db.execute(
        """
        SELECT pe.*, p.name AS project_name
        FROM project_environments pe
        JOIN projects p ON p.id = pe.project_id
        WHERE pe.id = ?
        """,
        (environment_id,),
    ).fetchone()


def find_by_name(db: Connection, project_id: str, name: str, exclude_id: str | None = None) -> Row | None:
    if exclude_id:
        return db.execute(
            """
            SELECT *
            FROM project_environments
            WHERE project_id = ? AND name = ? AND id != ?
            """,
            (project_id, name, exclude_id),
        ).fetchone()
    return db.execute(
        """
        SELECT *
        FROM project_environments
        WHERE project_id = ? AND name = ?
        """,
        (project_id, name),
    ).fetchone()


def create(
    db: Connection,
    *,
    environment_id: str,
    project_id: str,
    name: str,
    site_url: str,
    username: str,
    login_strategy: str,
    captcha_strategy: str,
    reuse_auth_state: bool,
    description: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO project_environments
          (id, project_id, name, site_url, username, login_strategy, captcha_strategy, reuse_auth_state, description, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            environment_id,
            project_id,
            name,
            site_url,
            username,
            login_strategy,
            captcha_strategy,
            int(reuse_auth_state),
            description,
            created_by,
        ),
    )


def delete(db: Connection, environment_id: str) -> None:
    db.execute("DELETE FROM project_environments WHERE id = ?", (environment_id,))


def update(db: Connection, environment_id: str, assignments: list[str], values: list[object]) -> None:
    values.append(environment_id)
    db.execute(f"UPDATE project_environments SET {', '.join(assignments)} WHERE id = ?", values)


def belongs_to_project(db: Connection, environment_id: str, project_id: str) -> bool:
    return db.execute(
        "SELECT 1 FROM project_environments WHERE id = ? AND project_id = ?",
        (environment_id, project_id),
    ).fetchone() is not None
