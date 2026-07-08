import sqlite3

from app.core.security import hash_secret


def seed_system_defaults(db: sqlite3.Connection) -> None:
    _migrate_api_environment_auth_types(db)
    _migrate_legacy_site_exploration_assignment(db)
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


def _migrate_legacy_site_exploration_assignment(db: sqlite3.Connection) -> None:
    db.execute(
        """
        INSERT INTO model_assignments (capability_id, model_provider_id)
        SELECT 'page_exploration', model_provider_id
        FROM model_assignments
        WHERE capability_id = 'site_exploration'
          AND NOT EXISTS (
            SELECT 1 FROM model_assignments WHERE capability_id = 'page_exploration'
          )
        """
    )
    db.execute("DELETE FROM model_assignments WHERE capability_id = 'site_exploration'")


def _migrate_api_environment_auth_types(db: sqlite3.Connection) -> None:
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'api_test_environments'"
    ).fetchone()
    table_sql = str(row["sql"] if row else "")
    if "'account_password'" in table_sql and "'cybertron_agent'" in table_sql:
        return

    db.execute("PRAGMA foreign_keys = OFF")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS api_test_environments_new (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          linked_ui_environment_id TEXT,
          name TEXT NOT NULL,
          api_base_url TEXT NOT NULL,
          username TEXT NOT NULL DEFAULT '',
          password_encrypted TEXT NOT NULL DEFAULT '',
          password_hash TEXT NOT NULL DEFAULT '',
          auth_type TEXT NOT NULL CHECK(auth_type IN ('none', 'account_password', 'cybertron_agent')) DEFAULT 'none',
          auth_config_json TEXT NOT NULL DEFAULT '{}',
          variables_json TEXT NOT NULL DEFAULT '{}',
          default_headers_json TEXT NOT NULL DEFAULT '{}',
          timeout_seconds INTEGER NOT NULL DEFAULT 30,
          verify_ssl INTEGER NOT NULL DEFAULT 1,
          auth_state_ttl_seconds INTEGER NOT NULL DEFAULT 86400,
          description TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(linked_ui_environment_id) REFERENCES project_environments(id) ON DELETE SET NULL,
          UNIQUE(project_id, name)
        )
        """
    )
    db.execute(
        """
        INSERT OR IGNORE INTO api_test_environments_new (
          id, project_id, linked_ui_environment_id, name, api_base_url,
          username, password_encrypted, password_hash, auth_type,
          auth_config_json, variables_json, default_headers_json,
          timeout_seconds, verify_ssl, auth_state_ttl_seconds, description,
          created_by, created_at, updated_at
        )
        SELECT
          id, project_id, linked_ui_environment_id, name, api_base_url,
          username, password_encrypted, password_hash,
          CASE WHEN auth_type IN ('account_password', 'cybertron_agent') THEN auth_type ELSE 'none' END,
          CASE WHEN auth_type IN ('account_password', 'cybertron_agent') THEN auth_config_json ELSE '{}' END,
          variables_json, default_headers_json, timeout_seconds, verify_ssl,
          auth_state_ttl_seconds, description, created_by, created_at, updated_at
        FROM api_test_environments
        """
    )
    db.execute("DROP TABLE api_test_environments")
    db.execute("ALTER TABLE api_test_environments_new RENAME TO api_test_environments")
    db.execute("PRAGMA foreign_keys = ON")


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
