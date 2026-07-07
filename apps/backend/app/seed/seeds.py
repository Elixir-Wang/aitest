import sqlite3

from app.core.security import hash_secret


def seed_system_defaults(db: sqlite3.Connection) -> None:
    _seed_operation_log_retention_policy(db)
    _ensure_all_projects_conversation_scope(db)
    _ensure_global_environments_project(db)


def seed_admin_user(db: sqlite3.Connection) -> None:
    db.execute(
        """
        INSERT OR IGNORE INTO users (id, username, email, nickname, password_hash, role, status, project_scope, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "u-admin",
            "admin",
            "admin@example.com",
            "平台管理员",
            hash_secret("admin"),
            "admin",
            "enabled",
            "全部项目",
            "平台管理员，负责用户、模型和项目权限维护。",
        ),
    )
    db.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (hash_secret("admin"), "u-admin"),
    )


def _seed_operation_log_retention_policy(db: sqlite3.Connection) -> None:
    exists = db.execute("SELECT id FROM operation_log_retention_policy WHERE id = 'default'").fetchone()
    if exists:
        return
    db.execute(
        """
        INSERT INTO operation_log_retention_policy (id, retention_days, max_rows, protect_high_risk)
        VALUES ('default', 180, 100000, 1)
        """
    )


def _ensure_all_projects_conversation_scope(db: sqlite3.Connection) -> None:
    exists = db.execute("SELECT id FROM projects WHERE id = '__all_projects__'").fetchone()
    if exists:
        return
    db.execute(
        """
        INSERT INTO projects (id, name, status, description, created_by)
        VALUES ('__all_projects__', '全部项目知识库', 'archived', '系统保留项目，用于全部项目知识库对话历史。', 'system')
        """
    )


def _ensure_global_environments_project(db: sqlite3.Connection) -> None:
    exists = db.execute("SELECT id FROM projects WHERE id = '__global_environments__'").fetchone()
    if exists:
        return
    db.execute(
        """
        INSERT INTO projects (id, name, status, description, created_by)
        VALUES ('__global_environments__', '全局探索环境', 'archived', '系统保留项目，用于存放与业务项目解耦的探索环境。', 'system')
        """
    )
