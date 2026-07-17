import sqlite3

from app.core.security import hash_secret


def seed_system_defaults(db: sqlite3.Connection) -> None:
    _drop_legacy_performance_run_tables(db)
    _ensure_performance_test_columns(db)
    _ensure_api_test_script_columns(db)
    _ensure_api_automation_run_columns(db)
    _ensure_api_script_generation_runs(db)
    _ensure_api_scenario_columns(db)
    _migrate_project_environment_scope(db)
    _migrate_api_environment_auth_types(db)
    _ensure_test_case_display_order(db)
    _ensure_api_test_case_structure_columns(db)
    _ensure_api_test_case_oracle_columns(db)
    _ensure_api_oracle_feedback_tables(db)
    _ensure_api_generation_batch_structure(db)
    _backfill_legacy_api_scenario_endpoints(db)
    _migrate_legacy_site_exploration_assignment(db)
    _seed_operation_log_retention_policy(db)
    _ensure_all_projects_conversation_scope(db)


def _ensure_api_script_generation_runs(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS api_script_generation_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          task_id TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')),
          endpoint_ids_json TEXT NOT NULL DEFAULT '[]',
          api_environment_id TEXT,
          force INTEGER NOT NULL DEFAULT 0,
          suite_path TEXT NOT NULL DEFAULT '',
          changed_files_json TEXT NOT NULL DEFAULT '[]',
          result_summary_json TEXT NOT NULL DEFAULT '{}',
          error_message TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          started_at TEXT,
          finished_at TEXT,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(api_environment_id) REFERENCES api_test_environments(id) ON DELETE SET NULL
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_script_generation_runs_project_created "
        "ON api_script_generation_runs(project_id, created_at)"
    )


def _drop_legacy_performance_run_tables(db: sqlite3.Connection) -> None:
    db.execute("DROP TABLE IF EXISTS performance_analysis_runs")


def _ensure_performance_test_columns(db: sqlite3.Connection) -> None:
    row = db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'performance_tests'").fetchone()
    if not row:
        return
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(performance_tests)").fetchall()}
    additions = {
        "data_config_json": "ALTER TABLE performance_tests ADD COLUMN data_config_json TEXT NOT NULL DEFAULT '{}'",
        "circuit_breaker_json": "ALTER TABLE performance_tests ADD COLUMN circuit_breaker_json TEXT NOT NULL DEFAULT '{}'",
    }
    for column, statement in additions.items():
        if column not in columns:
            db.execute(statement)


def _ensure_api_automation_run_columns(db: sqlite3.Connection) -> None:
    row = db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'api_automation_runs'").fetchone()
    if not row:
        return
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_automation_runs)").fetchall()}
    if "execution_snapshot_json" not in columns:
        db.execute("ALTER TABLE api_automation_runs ADD COLUMN execution_snapshot_json TEXT NOT NULL DEFAULT '{}'")
    if "target_type" not in columns:
        db.execute("ALTER TABLE api_automation_runs ADD COLUMN target_type TEXT NOT NULL DEFAULT 'scripts'")
    if "target_ids_json" not in columns:
        db.execute("ALTER TABLE api_automation_runs ADD COLUMN target_ids_json TEXT NOT NULL DEFAULT '[]'")
    if "scenario_result_path" not in columns:
        db.execute("ALTER TABLE api_automation_runs ADD COLUMN scenario_result_path TEXT NOT NULL DEFAULT ''")
    if "observation_result_path" not in columns:
        db.execute("ALTER TABLE api_automation_runs ADD COLUMN observation_result_path TEXT NOT NULL DEFAULT ''")
    table_sql_row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'api_automation_runs'"
    ).fetchone()
    if table_sql_row and "'observed'" not in str(table_sql_row["sql"] or ""):
        _rebuild_api_automation_runs_with_observed_status(db)


def _rebuild_api_automation_runs_with_observed_status(db: sqlite3.Connection) -> None:
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("DROP TABLE IF EXISTS api_automation_runs_new")
    db.execute(
        """
        CREATE TABLE api_automation_runs_new (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          api_environment_id TEXT,
          task_id TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'passed', 'observed', 'failed', 'cancelled', 'interrupted')),
          script_ids_json TEXT NOT NULL DEFAULT '[]',
          target_type TEXT NOT NULL DEFAULT 'scripts',
          target_ids_json TEXT NOT NULL DEFAULT '[]',
          execution_snapshot_json TEXT NOT NULL DEFAULT '{}',
          command_summary TEXT NOT NULL DEFAULT '',
          stdout_path TEXT NOT NULL DEFAULT '',
          stderr_path TEXT NOT NULL DEFAULT '',
          json_report_path TEXT NOT NULL DEFAULT '',
          scenario_result_path TEXT NOT NULL DEFAULT '',
          observation_result_path TEXT NOT NULL DEFAULT '',
          summary_json TEXT NOT NULL DEFAULT '{}',
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
        INSERT INTO api_automation_runs_new (
          id, project_id, api_environment_id, task_id, status, script_ids_json,
          target_type, target_ids_json, execution_snapshot_json, command_summary,
          stdout_path, stderr_path, json_report_path, scenario_result_path,
          observation_result_path, summary_json, error_message, created_by,
          created_at, updated_at, finished_at
        )
        SELECT
          id, project_id, api_environment_id, task_id, status, script_ids_json,
          target_type, target_ids_json, execution_snapshot_json, command_summary,
          stdout_path, stderr_path, json_report_path, scenario_result_path,
          observation_result_path, summary_json, error_message, created_by,
          created_at, updated_at, finished_at
        FROM api_automation_runs
        """
    )
    db.execute("DROP TABLE api_automation_runs")
    db.execute("ALTER TABLE api_automation_runs_new RENAME TO api_automation_runs")
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_runs_project_created ON api_automation_runs(project_id, created_at)"
    )
    db.execute("PRAGMA foreign_keys = ON")


def _ensure_api_scenario_columns(db: sqlite3.Connection) -> None:
    scenario = db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'api_scenarios'").fetchone()
    if scenario:
        columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_scenarios)").fetchall()}
        additions = {
            "revision": "ALTER TABLE api_scenarios ADD COLUMN revision INTEGER NOT NULL DEFAULT 0",
            "published_snapshot_json": "ALTER TABLE api_scenarios ADD COLUMN published_snapshot_json TEXT NOT NULL DEFAULT '{}'",
            "published_hash": "ALTER TABLE api_scenarios ADD COLUMN published_hash TEXT NOT NULL DEFAULT ''",
        }
        for column, statement in additions.items():
            if column not in columns:
                db.execute(statement)
    steps = db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'api_scenario_steps'").fetchone()
    if not steps:
        return
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_scenario_steps)").fetchall()}
    additions = {
        "step_type": "ALTER TABLE api_scenario_steps ADD COLUMN step_type TEXT NOT NULL DEFAULT 'api_request'",
        "api_test_case_id": "ALTER TABLE api_scenario_steps ADD COLUMN api_test_case_id TEXT REFERENCES api_test_cases(id) ON DELETE SET NULL",
        "bindings_json": "ALTER TABLE api_scenario_steps ADD COLUMN bindings_json TEXT NOT NULL DEFAULT '[]'",
        "control_config_json": "ALTER TABLE api_scenario_steps ADD COLUMN control_config_json TEXT NOT NULL DEFAULT '{}'",
        "on_failure": "ALTER TABLE api_scenario_steps ADD COLUMN on_failure TEXT NOT NULL DEFAULT 'stop'",
        "enabled": "ALTER TABLE api_scenario_steps ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1",
    }
    for column, statement in additions.items():
        if column not in columns:
            db.execute(statement)


def _backfill_legacy_api_scenario_endpoints(db: sqlite3.Connection) -> None:
    steps = db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'api_scenario_steps'").fetchone()
    cases = db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'api_test_cases'").fetchone()
    if not steps or not cases:
        return
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_scenario_steps)").fetchall()}
    if not {"endpoint_id", "api_test_case_id"} <= columns:
        return
    db.execute(
        """
        UPDATE api_scenario_steps
        SET endpoint_id = (
          SELECT endpoint_id
          FROM api_test_cases
          WHERE api_test_cases.id = api_scenario_steps.api_test_case_id
        )
        WHERE endpoint_id IS NULL AND api_test_case_id IS NOT NULL
        """
    )


def _ensure_test_case_display_order(db: sqlite3.Connection) -> None:
    row = db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'test_cases'").fetchone()
    if not row:
        return
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(test_cases)").fetchall()}
    if "display_order" not in columns:
        db.execute("ALTER TABLE test_cases ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0")
        rows = db.execute(
            """
            SELECT id, test_case_set_id, module, priority
            FROM test_cases
            ORDER BY test_case_set_id, created_at, id
            """
        ).fetchall()
        cases_by_set: dict[str, list[sqlite3.Row]] = {}
        for case in rows:
            cases_by_set.setdefault(str(case["test_case_set_id"]), []).append(case)

        priority_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        for cases in cases_by_set.values():
            module_order: dict[str, int] = {}
            for case in cases:
                module = str(case["module"] or "").strip()
                module_order.setdefault(module, len(module_order))
            ordered_cases = sorted(
                enumerate(cases),
                key=lambda item: (
                    module_order[str(item[1]["module"] or "").strip()],
                    priority_rank.get(str(item[1]["priority"] or "").strip().upper(), 4),
                    item[0],
                ),
            )
            db.executemany(
                "UPDATE test_cases SET display_order = ? WHERE id = ?",
                [(display_order, case["id"]) for display_order, (_, case) in enumerate(ordered_cases)],
            )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_test_cases_set_display_order ON test_cases(test_case_set_id, display_order)"
    )


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
        "test_description": "ALTER TABLE api_test_cases ADD COLUMN test_description TEXT NOT NULL DEFAULT ''",
    }
    for column, statement in missing_columns.items():
        if column not in columns:
            db.execute(statement)
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_test_cases)").fetchall()}
    if "status" in columns or "tags_json" in columns:
        _drop_deprecated_api_test_case_columns(db)


def _ensure_api_test_case_oracle_columns(db: sqlite3.Connection) -> None:
    row = db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'api_test_cases'").fetchone()
    if not row:
        return
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_test_cases)").fetchall()}
    if "test_point_key" not in columns:
        db.execute("ALTER TABLE api_test_cases ADD COLUMN test_point_key TEXT NOT NULL DEFAULT ''")
    if "oracle_status" not in columns:
        db.execute(
            "ALTER TABLE api_test_cases ADD COLUMN oracle_status TEXT NOT NULL DEFAULT 'confirmed'"
        )
    db.execute(
        "UPDATE api_test_cases SET test_point_key = 'legacy.' || id WHERE test_point_key = ''"
    )
    db.execute(
        "UPDATE api_test_cases SET oracle_status = 'confirmed' "
        "WHERE oracle_status IS NULL OR oracle_status NOT IN ('confirmed', 'inferred', 'needs_confirmation')"
    )


def _ensure_api_oracle_feedback_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS api_test_case_versions (
          id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          version INTEGER NOT NULL,
          snapshot_json TEXT NOT NULL DEFAULT '{}',
          change_source TEXT NOT NULL DEFAULT 'oracle_approval',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(case_id) REFERENCES api_test_cases(id) ON DELETE CASCADE,
          UNIQUE(case_id, version)
        );
        CREATE INDEX IF NOT EXISTS idx_api_test_case_versions_case
          ON api_test_case_versions(case_id, version);
        CREATE TABLE IF NOT EXISTS api_endpoint_oracle_facts (
          id TEXT PRIMARY KEY,
          endpoint_id TEXT NOT NULL,
          test_point_key TEXT NOT NULL,
          assertions_json TEXT NOT NULL DEFAULT '[]',
          evidence_run_ids_json TEXT NOT NULL DEFAULT '[]',
          approved_by TEXT NOT NULL,
          approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE CASCADE,
          UNIQUE(endpoint_id, test_point_key)
        );
        CREATE TABLE IF NOT EXISTS api_oracle_proposals (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          run_id TEXT NOT NULL,
          test_point_key TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected', 'superseded')) DEFAULT 'pending',
          current_snapshot_json TEXT NOT NULL DEFAULT '{}',
          proposed_snapshot_json TEXT NOT NULL DEFAULT '{}',
          reasoning TEXT NOT NULL DEFAULT '',
          confidence REAL NOT NULL DEFAULT 0,
          review_scope TEXT NOT NULL DEFAULT '',
          review_comment TEXT NOT NULL DEFAULT '',
          reviewed_by TEXT,
          reviewed_at TEXT,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES api_test_cases(id) ON DELETE CASCADE,
          FOREIGN KEY(run_id) REFERENCES api_automation_runs(id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_api_oracle_proposals_run_case
          ON api_oracle_proposals(run_id, case_id);
        CREATE INDEX IF NOT EXISTS idx_api_oracle_proposals_project_status
          ON api_oracle_proposals(project_id, status, created_at);
        """
    )


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


def _drop_deprecated_api_test_case_columns(db: sqlite3.Connection) -> None:
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
          test_description TEXT NOT NULL DEFAULT '',
          priority TEXT NOT NULL DEFAULT 'P2',
          coverage TEXT NOT NULL DEFAULT 'positive',
          source TEXT NOT NULL CHECK(source IN ('ai_generated', 'manual', 'approved_test_case')) DEFAULT 'ai_generated',
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
          title, test_description, priority, coverage, source, preconditions_json,
          request_json, test_data_json, expected_json, assertions_json, variables_json,
          data_origin_json, data_file_path, notes, created_by, updated_by, created_at, updated_at
        )
        SELECT
          id, project_id, endpoint_id, source_test_case_id, generation_run_id,
          {generation_item_id}, {generation_attempt_id},
          title, test_description, priority, coverage, source, preconditions_json,
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


def _migrate_project_environment_scope(db: sqlite3.Connection) -> None:
    table = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'project_environments'"
    ).fetchone()
    if not table:
        return

    legacy_project = db.execute("SELECT 1 FROM projects WHERE id = '__global_environments__'").fetchone()
    if not legacy_project:
        return

    fallback_project = db.execute(
        "SELECT id FROM projects WHERE name = '百工平台' AND status != 'archived'"
    ).fetchone()
    legacy_environments = db.execute(
        "SELECT id, name FROM project_environments WHERE project_id = '__global_environments__'"
    ).fetchall()
    for environment in legacy_environments:
        referenced_projects = db.execute(
            "SELECT DISTINCT project_id FROM exploration_runs WHERE environment_id = ?",
            (environment["id"],),
        ).fetchall()
        if len(referenced_projects) > 1:
            raise RuntimeError(f"环境 {environment['name']} 被多个项目引用，无法迁移为单项目环境。")
        target_project_id = referenced_projects[0]["project_id"] if referenced_projects else None
        if not target_project_id:
            if not fallback_project:
                raise RuntimeError(f"环境 {environment['name']} 无历史任务，且未找到百工平台项目。")
            target_project_id = fallback_project["id"]
        db.execute(
            "UPDATE project_environments SET project_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (target_project_id, environment["id"]),
        )

    db.execute("DELETE FROM projects WHERE id = '__global_environments__'")

def _ensure_api_test_script_columns(db: sqlite3.Connection) -> None:
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_test_scripts)").fetchall()}
    additions = {
        "source_hash": "ALTER TABLE api_test_scripts ADD COLUMN source_hash TEXT NOT NULL DEFAULT ''",
        "case_count": "ALTER TABLE api_test_scripts ADD COLUMN case_count INTEGER NOT NULL DEFAULT 0",
        "manual_modified": "ALTER TABLE api_test_scripts ADD COLUMN manual_modified INTEGER NOT NULL DEFAULT 0",
        "last_run_status": "ALTER TABLE api_test_scripts ADD COLUMN last_run_status TEXT NOT NULL DEFAULT ''",
        "last_run_at": "ALTER TABLE api_test_scripts ADD COLUMN last_run_at TEXT",
    }
    for column, statement in additions.items():
        if column not in columns:
            db.execute(statement)

    duplicate_groups = db.execute(
        """
        SELECT project_id, endpoint_id
        FROM api_test_scripts
        WHERE endpoint_id IS NOT NULL
        GROUP BY project_id, endpoint_id
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    for group in duplicate_groups:
        rows = db.execute(
            """
            SELECT id FROM api_test_scripts
            WHERE project_id = ? AND endpoint_id = ?
            ORDER BY updated_at DESC, created_at DESC, id DESC
            """,
            (group["project_id"], group["endpoint_id"]),
        ).fetchall()
        for stale in rows[1:]:
            db.execute("DELETE FROM api_test_scripts WHERE id = ?", (stale["id"],))

    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_api_scripts_project_endpoint
        ON api_test_scripts(project_id, endpoint_id)
        WHERE endpoint_id IS NOT NULL
        """
    )
