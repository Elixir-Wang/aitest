from __future__ import annotations

import sqlite3

from app.core.db import connect
from app.core.security import hash_secret


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              username TEXT NOT NULL UNIQUE,
              email TEXT NOT NULL UNIQUE,
              nickname TEXT,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('admin', 'tester', 'guest')),
              status TEXT NOT NULL CHECK(status IN ('enabled', 'disabled')),
              project_scope TEXT NOT NULL DEFAULT '全部项目',
              description TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              expires_at TEXT NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS model_providers (
              id TEXT PRIMARY KEY,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              base_url TEXT NOT NULL,
              api_key_env TEXT NOT NULL DEFAULT '',
              api_key_hash TEXT NOT NULL DEFAULT '',
              api_key_mask TEXT NOT NULL DEFAULT '',
              description TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN ('enabled', 'disabled')),
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(provider, model, base_url),
              FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS agent_model_assignments (
              agent_id TEXT PRIMARY KEY,
              model_provider_id TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(model_provider_id) REFERENCES model_providers(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS projects (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              code TEXT NOT NULL DEFAULT '',
              default_site_url TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN ('active', 'archived')),
              description TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL DEFAULT 'system',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS source_documents (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              name TEXT NOT NULL,
              document_type TEXT NOT NULL,
              current_version_id TEXT,
              status TEXT NOT NULL DEFAULT 'collecting',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              UNIQUE(project_id, name)
            );

            CREATE TABLE IF NOT EXISTS source_document_versions (
              id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              version_no INTEGER NOT NULL,
              markdown_content TEXT NOT NULL DEFAULT '',
              file_path TEXT NOT NULL,
              source_action TEXT NOT NULL,
              change_summary TEXT NOT NULL DEFAULT '',
              diff_summary TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              UNIQUE(document_id, version_no)
            );

            CREATE TABLE IF NOT EXISTS source_document_file_mappings (
              id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              version_id TEXT,
              source_file_path TEXT NOT NULL,
              original_filename TEXT NOT NULL DEFAULT '',
              file_format TEXT NOT NULL DEFAULT '',
              markdown_file_path TEXT,
              conversion_status TEXT NOT NULL DEFAULT 'pending',
              mapping_status TEXT NOT NULL DEFAULT 'pending_merge',
              conversion_summary TEXT NOT NULL DEFAULT '',
              conversion_quality INTEGER,
              created_by TEXT NOT NULL DEFAULT 'system',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              FOREIGN KEY(version_id) REFERENCES source_document_versions(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS source_document_merge_conflicts (
              id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              title TEXT NOT NULL,
              source_file_names TEXT NOT NULL DEFAULT '',
              fragment_a TEXT NOT NULL DEFAULT '',
              fragment_b TEXT NOT NULL DEFAULT '',
              resolution TEXT NOT NULL DEFAULT '',
              resolution_type TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN ('open', 'resolved')) DEFAULT 'open',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS dashboard_daily_stats (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              stat_date TEXT NOT NULL,
              case_assets INTEGER NOT NULL,
              adopted_cases INTEGER NOT NULL,
              automation_cases INTEGER NOT NULL,
              generated_cases INTEGER NOT NULL,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              UNIQUE(project_id, stat_date)
            );

            CREATE TABLE IF NOT EXISTS project_environments (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              name TEXT NOT NULL,
              site_url TEXT NOT NULL,
              username TEXT NOT NULL DEFAULT '',
              password_mask TEXT NOT NULL DEFAULT '',
              description TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              UNIQUE(project_id, name)
            );

            CREATE TABLE IF NOT EXISTS exploration_runs (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              environment_id TEXT NOT NULL,
              title TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'waiting_human', 'partial', 'completed', 'blocked')) DEFAULT 'queued',
              scope TEXT NOT NULL DEFAULT '',
              forbidden_paths TEXT NOT NULL DEFAULT '',
              login_strategy TEXT NOT NULL DEFAULT 'reuse_state',
              description TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE RESTRICT
            );
            """
        )
        _ensure_column(db, "model_providers", "description", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "model_providers", "api_key_env", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "code", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "default_site_url", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "created_by", "TEXT NOT NULL DEFAULT 'system'")
        _migrate_source_documents(db)
        _migrate_file_mappings(db)
        _seed_user(db, "u-admin", "admin", "admin@example.com", "平台管理员", "admin", "admin", "enabled", "全部项目", "平台管理员，负责用户、模型和项目权限维护。")
        _sync_seed_password(db, "u-admin", "admin")


def _seed_user(db: sqlite3.Connection, user_id: str, username: str, email: str, nickname: str, password: str, role: str, status: str, project_scope: str, description: str) -> None:
    exists = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if exists:
        return
    db.execute(
        """
        INSERT INTO users (id, username, email, nickname, password_hash, role, status, project_scope, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, username, email, nickname, hash_secret(password), role, status, project_scope, description),
    )


def _ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column in columns:
        return
    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migrate_source_documents(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(source_documents)").fetchall()}
    if "original_file_path" not in columns:
        return
    db.executescript(
        """
        PRAGMA foreign_keys=off;
        CREATE TABLE IF NOT EXISTS source_documents_new (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          name TEXT NOT NULL,
          document_type TEXT NOT NULL,
          current_version_id TEXT,
          status TEXT NOT NULL DEFAULT 'collecting',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          UNIQUE(project_id, name)
        );
        INSERT OR IGNORE INTO source_documents_new
          (id, project_id, name, document_type, current_version_id, status, created_by, created_at, updated_at)
        SELECT id, project_id, name, document_type, current_version_id, status, created_by, created_at, updated_at
        FROM source_documents;
        DROP TABLE source_documents;
        ALTER TABLE source_documents_new RENAME TO source_documents;
        PRAGMA foreign_keys=on;
        """
    )


def _migrate_file_mappings(db: sqlite3.Connection) -> None:
    columns = {row["name"]: row for row in db.execute("PRAGMA table_info(source_document_file_mappings)").fetchall()}
    version_id_column = columns.get("version_id")
    if (version_id_column and version_id_column["notnull"]) or "conversion_status" not in columns:
        db.executescript(
            """
            PRAGMA foreign_keys=off;
            CREATE TABLE IF NOT EXISTS source_document_file_mappings_new (
              id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              version_id TEXT,
              source_file_path TEXT NOT NULL,
              original_filename TEXT NOT NULL DEFAULT '',
              file_format TEXT NOT NULL DEFAULT '',
              markdown_file_path TEXT,
              conversion_status TEXT NOT NULL DEFAULT 'success',
              mapping_status TEXT NOT NULL DEFAULT 'pending_merge',
              conversion_summary TEXT NOT NULL DEFAULT '',
              conversion_quality INTEGER,
              created_by TEXT NOT NULL DEFAULT 'system',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              FOREIGN KEY(version_id) REFERENCES source_document_versions(id) ON DELETE SET NULL
            );
            INSERT OR IGNORE INTO source_document_file_mappings_new
              (id, document_id, version_id, source_file_path, original_filename, file_format, markdown_file_path,
               conversion_status, mapping_status, conversion_summary, created_by, created_at)
            SELECT id, document_id, version_id, source_file_path, source_file_path, 'unknown', markdown_file_path,
                   'success', mapping_status, conversion_summary, 'system', created_at
            FROM source_document_file_mappings;
            DROP TABLE source_document_file_mappings;
            ALTER TABLE source_document_file_mappings_new RENAME TO source_document_file_mappings;
            PRAGMA foreign_keys=on;
            """
        )
        return

    _ensure_column(db, "source_document_file_mappings", "original_filename", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(db, "source_document_file_mappings", "file_format", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(db, "source_document_file_mappings", "conversion_status", "TEXT NOT NULL DEFAULT 'success'")
    _ensure_column(db, "source_document_file_mappings", "conversion_quality", "INTEGER")
    _ensure_column(db, "source_document_file_mappings", "created_by", "TEXT NOT NULL DEFAULT 'system'")
    db.execute(
        """
        UPDATE source_document_file_mappings
        SET original_filename = CASE WHEN original_filename = '' THEN source_file_path ELSE original_filename END,
            file_format = CASE WHEN file_format = '' THEN 'unknown' ELSE file_format END
        """
    )


def _sync_seed_password(db: sqlite3.Connection, user_id: str, password: str) -> None:
    db.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (hash_secret(password), user_id),
    )
