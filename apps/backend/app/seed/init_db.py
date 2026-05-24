from __future__ import annotations

import sqlite3
from pathlib import Path, PureWindowsPath

from app.core.db import connect
from app.core.security import hash_secret
from app.core.storage import PROJECT_FILE_STORAGE_ROOT, store_path


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
              api_key TEXT NOT NULL DEFAULT '',
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
              preview_file_path TEXT,
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
              run_id TEXT,
              document_id TEXT NOT NULL,
              conflict_type TEXT NOT NULL DEFAULT 'contradiction',
              severity TEXT NOT NULL DEFAULT 'medium',
              title TEXT NOT NULL,
              source_refs TEXT NOT NULL DEFAULT '[]',
              source_file_names TEXT NOT NULL DEFAULT '',
              fragment_a TEXT NOT NULL DEFAULT '',
              fragment_b TEXT NOT NULL DEFAULT '',
              agent_suggestion TEXT NOT NULL DEFAULT '',
              resolution TEXT NOT NULL DEFAULT '',
              resolution_type TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN ('open', 'resolved', 'ignored')) DEFAULT 'open',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS requirement_merge_runs (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              document_id TEXT NOT NULL,
              base_version_id TEXT,
              output_version_id TEXT,
              merge_mode TEXT NOT NULL,
              status TEXT NOT NULL,
              input_mapping_ids TEXT NOT NULL DEFAULT '[]',
              resolved_conflict_ids TEXT NOT NULL DEFAULT '[]',
              merge_summary TEXT NOT NULL DEFAULT '',
              diff_summary TEXT NOT NULL DEFAULT '',
              affected_modules TEXT NOT NULL DEFAULT '[]',
              output_preview_path TEXT,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS requirement_source_coverage_items (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              document_id TEXT NOT NULL,
              version_id TEXT,
              mapping_id TEXT NOT NULL,
              source_heading TEXT NOT NULL DEFAULT '',
              source_excerpt TEXT NOT NULL DEFAULT '',
              target_module TEXT NOT NULL DEFAULT '',
              target_heading TEXT NOT NULL DEFAULT '',
              coverage_status TEXT NOT NULL,
              reason TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(run_id) REFERENCES requirement_merge_runs(id) ON DELETE CASCADE,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS document_version_change_logs (
              id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              version_id TEXT NOT NULL,
              source_action TEXT NOT NULL,
              change_summary TEXT NOT NULL DEFAULT '',
              diff_summary TEXT NOT NULL DEFAULT '',
              affected_modules TEXT NOT NULL DEFAULT '[]',
              source_mapping_ids TEXT NOT NULL DEFAULT '[]',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              FOREIGN KEY(version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS requirement_analyses (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              document_id TEXT NOT NULL,
              version_id TEXT NOT NULL,
              status TEXT NOT NULL,
              analysis_summary TEXT NOT NULL DEFAULT '',
              output_json TEXT NOT NULL,
              quality_result TEXT NOT NULL,
              testability_score INTEGER NOT NULL DEFAULT 0,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              FOREIGN KEY(version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE
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
              artifact_root TEXT NOT NULL DEFAULT '',
              result_summary TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              started_at TEXT,
              finished_at TEXT,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS exploration_module_coverages (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              module_key TEXT NOT NULL,
              module_name TEXT NOT NULL,
              entry_path TEXT NOT NULL DEFAULT '',
              planned_page_count INTEGER NOT NULL DEFAULT 0,
              explored_page_count INTEGER NOT NULL DEFAULT 0,
              blocked_page_count INTEGER NOT NULL DEFAULT 0,
              action_count INTEGER NOT NULL DEFAULT 0,
              field_count INTEGER NOT NULL DEFAULT 0,
              state_transition_count INTEGER NOT NULL DEFAULT 0,
              completion_status TEXT NOT NULL,
              completion_summary TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE,
              UNIQUE(exploration_run_id, module_key)
            );

            CREATE TABLE IF NOT EXISTS exploration_pages (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              module_key TEXT NOT NULL DEFAULT '',
              title TEXT NOT NULL DEFAULT '',
              url TEXT NOT NULL DEFAULT '',
              entry_path TEXT NOT NULL DEFAULT '',
              structure_summary TEXT NOT NULL DEFAULT '',
              screenshot_path TEXT NOT NULL DEFAULT '',
              snapshot_path TEXT NOT NULL DEFAULT '',
              trace_path TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exploration_elements (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              page_id TEXT,
              module_key TEXT NOT NULL DEFAULT '',
              element_name TEXT NOT NULL,
              element_type TEXT NOT NULL DEFAULT '',
              recommended_locator TEXT NOT NULL DEFAULT '',
              fallback_locator TEXT NOT NULL DEFAULT '',
              stability_note TEXT NOT NULL DEFAULT '',
              source_ref TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE,
              FOREIGN KEY(page_id) REFERENCES exploration_pages(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS exploration_blockers (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              module_key TEXT NOT NULL DEFAULT '',
              page_ref TEXT NOT NULL DEFAULT '',
              reason_type TEXT NOT NULL DEFAULT '',
              reason TEXT NOT NULL,
              evidence_path TEXT NOT NULL DEFAULT '',
              impact_scope TEXT NOT NULL DEFAULT '',
              suggested_action TEXT NOT NULL DEFAULT '',
              is_blocking INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exploration_artifacts (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              artifact_type TEXT NOT NULL,
              file_path TEXT NOT NULL,
              title TEXT NOT NULL DEFAULT '',
              summary TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exploration_document_versions (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              version_no INTEGER NOT NULL,
              markdown_path TEXT NOT NULL,
              change_summary TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE,
              UNIQUE(exploration_run_id, version_no)
            );
            """
        )
        _ensure_column(db, "model_providers", "description", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "model_providers", "api_key", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "code", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "default_site_url", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "created_by", "TEXT NOT NULL DEFAULT 'system'")
        _ensure_column(db, "exploration_runs", "artifact_root", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "exploration_runs", "result_summary", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "exploration_runs", "started_at", "TEXT")
        _ensure_column(db, "exploration_runs", "finished_at", "TEXT")
        _migrate_source_documents(db)
        _migrate_file_mappings(db)
        _migrate_merge_conflicts(db)
        _migrate_stored_paths(db)
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
              preview_file_path TEXT,
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
    _ensure_column(db, "source_document_file_mappings", "preview_file_path", "TEXT")
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


def _migrate_merge_conflicts(db: sqlite3.Connection) -> None:
    _ensure_column(db, "source_document_merge_conflicts", "run_id", "TEXT")
    _ensure_column(db, "source_document_merge_conflicts", "conflict_type", "TEXT NOT NULL DEFAULT 'contradiction'")
    _ensure_column(db, "source_document_merge_conflicts", "severity", "TEXT NOT NULL DEFAULT 'medium'")
    _ensure_column(db, "source_document_merge_conflicts", "source_refs", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(db, "source_document_merge_conflicts", "agent_suggestion", "TEXT NOT NULL DEFAULT ''")


def _migrate_stored_paths(db: sqlite3.Connection) -> None:
    for table, columns in {
        "source_document_versions": ("file_path",),
        "source_document_file_mappings": ("source_file_path", "markdown_file_path", "preview_file_path"),
        "requirement_merge_runs": ("output_preview_path",),
    }.items():
        table_exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if not table_exists:
            continue
        existing_columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        for column in columns:
            if column not in existing_columns:
                continue
            rows = db.execute(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != ''").fetchall()
            for row in rows:
                normalized = _normalize_stored_path(row[column])
                if normalized and normalized != row[column]:
                    db.execute(f"UPDATE {table} SET {column} = ? WHERE id = ?", (normalized, row["id"]))


def _normalize_stored_path(path_value: str) -> str | None:
    stored = store_path(path_value)
    if stored != path_value:
        return stored

    normalized = path_value.replace("\\", "/")
    marker = "/data/projects/"
    if marker in normalized:
        return normalized.split(marker, 1)[1]

    windows_parts = PureWindowsPath(path_value).parts
    if "projects" in windows_parts:
        projects_index = windows_parts.index("projects")
        return Path(*windows_parts[projects_index + 1 :]).as_posix()

    path = Path(path_value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(PROJECT_FILE_STORAGE_ROOT).as_posix()
    except ValueError:
        return path_value


def _sync_seed_password(db: sqlite3.Connection, user_id: str, password: str) -> None:
    db.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (hash_secret(password), user_id),
    )
