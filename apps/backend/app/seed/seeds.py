import sqlite3

from app.core.security import hash_secret


def seed_system_defaults(db: sqlite3.Connection) -> None:
    _migrate_api_environment_auth_types(db)
    _ensure_api_test_case_structure_columns(db)
    _ensure_api_generation_batch_structure(db)
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


def _ensure_api_test_case_structure_columns(db: sqlite3.Connection) -> None:
    row = db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'api_test_cases'").fetchone()
    if not row:
        return
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_test_cases)").fetchall()}
    missing_columns = {
        "coverage": "ALTER TABLE api_test_cases ADD COLUMN coverage TEXT NOT NULL DEFAULT 'positive'",
        "preconditions_json": "ALTER TABLE api_test_cases ADD COLUMN preconditions_json TEXT NOT NULL DEFAULT '[]'",
        "test_data_json": "ALTER TABLE api_test_cases ADD COLUMN test_data_json TEXT NOT NULL DEFAULT '{}'",
    }
    for column, statement in missing_columns.items():
        if column not in columns:
            db.execute(statement)
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_test_cases)").fetchall()}
    if "status" in columns:
        _drop_api_test_case_status_column(db)


def _ensure_api_generation_batch_structure(db: sqlite3.Connection) -> None:
    run_row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'api_generation_runs'"
    ).fetchone()
    run_sql = str(run_row["sql"] if run_row else "")
    if run_row and "partial_success" not in run_sql:
        db.execute("PRAGMA foreign_keys = OFF")
        db.execute("DROP TABLE IF EXISTS api_generation_runs_new")
        db.execute(
            """
            CREATE TABLE api_generation_runs_new (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              api_environment_id TEXT,
              task_id TEXT NOT NULL UNIQUE,
              status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'partial_success', 'failed', 'cancelled', 'interrupted')),
              endpoint_ids_json TEXT NOT NULL DEFAULT '[]',
              source_test_case_ids_json TEXT NOT NULL DEFAULT '[]',
              generation_goal TEXT NOT NULL DEFAULT '',
              options_json TEXT NOT NULL DEFAULT '{}',
              result_summary_json TEXT NOT NULL DEFAULT '{}',
              error_message TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              FOREIGN KEY(api_environment_id) REFERENCES api_test_environments(id) ON DELETE SET NULL
            )
            """
        )
        db.execute(
            """
            INSERT INTO api_generation_runs_new (
              id, project_id, api_environment_id, task_id, status,
              endpoint_ids_json, source_test_case_ids_json, generation_goal,
              options_json, result_summary_json, error_message, created_by,
              created_at, updated_at, finished_at
            )
            SELECT
              id, project_id, api_environment_id, task_id, status,
              endpoint_ids_json, source_test_case_ids_json, generation_goal,
              options_json, result_summary_json, error_message, created_by,
              created_at, updated_at, finished_at
            FROM api_generation_runs
            """
        )
        db.execute("DROP TABLE api_generation_runs")
        db.execute("ALTER TABLE api_generation_runs_new RENAME TO api_generation_runs")
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_generation_runs_project_created "
            "ON api_generation_runs(project_id, created_at)"
        )
        db.commit()
        db.execute("PRAGMA foreign_keys = ON")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS api_generation_items (
          id TEXT PRIMARY KEY,
          generation_run_id TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed')) DEFAULT 'queued',
          attempt_count INTEGER NOT NULL DEFAULT 0,
          generated_case_count INTEGER NOT NULL DEFAULT 0,
          error_message TEXT NOT NULL DEFAULT '',
          started_at TEXT,
          finished_at TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(generation_run_id) REFERENCES api_generation_runs(id) ON DELETE CASCADE,
          FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE CASCADE,
          UNIQUE(generation_run_id, endpoint_id)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_generation_items_run_status "
        "ON api_generation_items(generation_run_id, status)"
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS api_generation_item_attempts (
          id TEXT PRIMARY KEY,
          generation_item_id TEXT NOT NULL,
          attempt_no INTEGER NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')) DEFAULT 'running',
          generated_case_count INTEGER NOT NULL DEFAULT 0,
          error_message TEXT NOT NULL DEFAULT '',
          started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          finished_at TEXT,
          FOREIGN KEY(generation_item_id) REFERENCES api_generation_items(id) ON DELETE CASCADE,
          UNIQUE(generation_item_id, attempt_no)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_generation_item_attempts_item "
        "ON api_generation_item_attempts(generation_item_id, attempt_no)"
    )

    case_row = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'api_test_cases'"
    ).fetchone()
    if case_row:
        columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_test_cases)")}
        if "generation_item_id" not in columns:
            db.execute("ALTER TABLE api_test_cases ADD COLUMN generation_item_id TEXT REFERENCES api_generation_items(id) ON DELETE SET NULL")
        if "generation_attempt_id" not in columns:
            db.execute("ALTER TABLE api_test_cases ADD COLUMN generation_attempt_id TEXT REFERENCES api_generation_item_attempts(id) ON DELETE SET NULL")
    foreign_key_violations = db.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_violations:
        raise RuntimeError(f"Foreign key violations remain after API generation batch migration: {foreign_key_violations}")


def _drop_api_test_case_status_column(db: sqlite3.Connection) -> None:
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_test_cases)")}
    generation_item_id = "generation_item_id" if "generation_item_id" in columns else "NULL"
    generation_attempt_id = "generation_attempt_id" if "generation_attempt_id" in columns else "NULL"
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS api_test_cases_new (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          endpoint_id TEXT,
          source_test_case_id TEXT,
          generation_run_id TEXT,
          generation_item_id TEXT,
          generation_attempt_id TEXT,
          title TEXT NOT NULL,
          priority TEXT NOT NULL DEFAULT 'P2',
          coverage TEXT NOT NULL DEFAULT 'positive',
          source TEXT NOT NULL CHECK(source IN ('ai_generated', 'manual', 'approved_test_case')) DEFAULT 'ai_generated',
          tags_json TEXT NOT NULL DEFAULT '[]',
          preconditions_json TEXT NOT NULL DEFAULT '[]',
          request_json TEXT NOT NULL DEFAULT '{}',
          test_data_json TEXT NOT NULL DEFAULT '{}',
          expected_json TEXT NOT NULL DEFAULT '{}',
          assertions_json TEXT NOT NULL DEFAULT '[]',
          variables_json TEXT NOT NULL DEFAULT '{}',
          data_origin_json TEXT NOT NULL DEFAULT '{}',
          data_file_path TEXT NOT NULL DEFAULT '',
          notes TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          updated_by TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE SET NULL,
          FOREIGN KEY(source_test_case_id) REFERENCES test_cases(id) ON DELETE SET NULL,
          FOREIGN KEY(generation_run_id) REFERENCES api_generation_runs(id) ON DELETE SET NULL,
          FOREIGN KEY(generation_item_id) REFERENCES api_generation_items(id) ON DELETE SET NULL,
          FOREIGN KEY(generation_attempt_id) REFERENCES api_generation_item_attempts(id) ON DELETE SET NULL
        )
        """
    )
    db.execute(
        f"""
        INSERT OR IGNORE INTO api_test_cases_new (
          id, project_id, endpoint_id, source_test_case_id, generation_run_id,
          generation_item_id, generation_attempt_id,
          title, priority, coverage, source, tags_json, preconditions_json,
          request_json, test_data_json, expected_json, assertions_json, variables_json,
          data_origin_json, data_file_path, notes, created_by, updated_by, created_at, updated_at
        )
        SELECT
          id, project_id, endpoint_id, source_test_case_id, generation_run_id,
          {generation_item_id}, {generation_attempt_id},
          title, priority, coverage, source, tags_json, preconditions_json,
          request_json, test_data_json, expected_json, assertions_json, variables_json,
          data_origin_json, data_file_path, notes, created_by, updated_by, created_at, updated_at
        FROM api_test_cases
        """
    )
    db.execute("DROP TABLE api_test_cases")
    db.execute("ALTER TABLE api_test_cases_new RENAME TO api_test_cases")
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_test_cases_project_endpoint ON api_test_cases(project_id, endpoint_id)"
    )
    db.execute("PRAGMA foreign_keys = ON")


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
