from sqlite3 import Connection, Row

from app.core.environment_scope import GLOBAL_ENVIRONMENT_PROJECT_ID


def list_all(db: Connection) -> list[Row]:
    return db.execute(
        """
        SELECT pe.*
        FROM project_environments pe
        ORDER BY pe.updated_at DESC, pe.created_at DESC
        """
    ).fetchall()


def find_by_id(db: Connection, environment_id: str) -> Row | None:
    return db.execute(
        """
        SELECT pe.*
        FROM project_environments pe
        WHERE pe.id = ?
        """,
        (environment_id,),
    ).fetchone()


def find_by_name(db: Connection, name: str, exclude_id: str | None = None) -> Row | None:
    if exclude_id:
        return db.execute(
            """
            SELECT *
            FROM project_environments
            WHERE project_id = ? AND name = ? AND id != ?
            """,
            (GLOBAL_ENVIRONMENT_PROJECT_ID, name, exclude_id),
        ).fetchone()
    return db.execute(
        """
        SELECT *
        FROM project_environments
        WHERE project_id = ? AND name = ?
        """,
        (GLOBAL_ENVIRONMENT_PROJECT_ID, name),
    ).fetchone()


def create(
    db: Connection,
    *,
    environment_id: str,
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
            GLOBAL_ENVIRONMENT_PROJECT_ID,
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
