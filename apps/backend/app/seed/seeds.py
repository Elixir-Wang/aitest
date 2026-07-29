import re
import sqlite3

from app.core.security import hash_secret


def seed_system_defaults(db: sqlite3.Connection) -> None:
    _ensure_exploration_loop_mode(db)
    _repair_exploration_run_foreign_keys(db)
    _migrate_ui_automation_case_sources(db)
    _ensure_ui_automation_video_column(db)
    _drop_legacy_performance_run_tables(db)
    _ensure_performance_test_columns(db)
    _migrate_performance_scripts_to_single_record(db)
    _ensure_performance_analysis_columns(db)
    _ensure_api_test_script_columns(db)
    _ensure_api_automation_run_columns(db)
    _ensure_api_script_generation_runs(db)
    _ensure_api_scenario_columns(db)
    _ensure_api_scenario_ai_plan_table(db)
    _migrate_project_environment_scope(db)
    _migrate_api_environment_auth_types(db)
    _ensure_test_case_display_order(db)
    _ensure_api_test_case_structure_columns(db)
    _ensure_api_test_case_oracle_columns(db)
    _ensure_api_oracle_feedback_tables(db)
    _ensure_api_generation_batch_structure(db)
    _ensure_test_point_coverage_structure(db)
    _backfill_legacy_api_scenario_endpoints(db)
    _migrate_legacy_site_exploration_assignment(db)
    _seed_operation_log_retention_policy(db)
    _ensure_all_projects_conversation_scope(db)
    _assert_foreign_key_integrity(db)


def _ensure_exploration_loop_mode(db: sqlite3.Connection) -> None:
    """Migrate existing exploration_runs CHECK constraint to include loop mode."""
    table = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'exploration_runs'"
    ).fetchone()
    if not table:
        return
    try:
        table_sql = table["sql"]
    except (IndexError, KeyError, TypeError):
        table_sql = table[0]
    if "'loop'" in str(table_sql or ""):
        return

    foreign_keys = int(db.execute("PRAGMA foreign_keys").fetchone()[0])
    legacy_alter_table = int(db.execute("PRAGMA legacy_alter_table").fetchone()[0])
    db.commit()
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("PRAGMA legacy_alter_table = ON")
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("ALTER TABLE exploration_runs RENAME TO exploration_runs_legacy_loop_mode")
        db.execute(
            """
            CREATE TABLE exploration_runs (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              environment_id TEXT NOT NULL,
              requirement_doc_id TEXT NOT NULL DEFAULT '',
              title TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('pending', 'queued', 'running', 'stopping', 'cancelled', 'interrupted', 'completed', 'blocked', 'failed')) DEFAULT 'pending',
              exploration_mode TEXT NOT NULL DEFAULT 'goal' CHECK(exploration_mode IN ('goal', 'autonomous', 'loop')),
              scope TEXT NOT NULL DEFAULT '',
              forbidden_paths TEXT NOT NULL DEFAULT '',
              login_strategy TEXT NOT NULL DEFAULT 'skip_login',
              goal TEXT NOT NULL DEFAULT '',
              notes TEXT NOT NULL DEFAULT '',
              max_pages INTEGER NOT NULL DEFAULT 50,
              max_actions INTEGER NOT NULL DEFAULT 1000,
              timeout_minutes INTEGER NOT NULL DEFAULT 120,
              artifact_root TEXT NOT NULL DEFAULT '',
              result_summary TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              started_at TEXT,
              finished_at TEXT,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE RESTRICT
            )
            """
        )
        db.execute(
            """
            INSERT INTO exploration_runs (
              id, project_id, environment_id, requirement_doc_id, title, status,
              exploration_mode, scope, forbidden_paths, login_strategy, goal, notes,
              max_pages, max_actions, timeout_minutes, artifact_root, result_summary,
              created_by, created_at, updated_at, started_at, finished_at
            )
            SELECT id, project_id, environment_id, requirement_doc_id, title, status,
              exploration_mode, scope, forbidden_paths, login_strategy, goal, notes,
              max_pages, max_actions, timeout_minutes, artifact_root, result_summary,
              created_by, created_at, updated_at, started_at, finished_at
            FROM exploration_runs_legacy_loop_mode
            """
        )
        db.execute("DROP TABLE exploration_runs_legacy_loop_mode")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.execute(f"PRAGMA legacy_alter_table = {legacy_alter_table}")
        db.execute(f"PRAGMA foreign_keys = {foreign_keys}")


def _repair_exploration_run_foreign_keys(db: sqlite3.Connection) -> None:
    legacy_table = "exploration_runs_legacy_loop_mode"
    affected_tables = []
    table_rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    for row in table_rows:
        table_name = str(row["name"] if isinstance(row, sqlite3.Row) else row[0])
        targets = {
            str(foreign_key["table"] if isinstance(foreign_key, sqlite3.Row) else foreign_key[2])
            for foreign_key in db.execute(f"PRAGMA foreign_key_list({_quote_identifier(table_name)})")
        }
        if legacy_table in targets:
            affected_tables.append(table_name)
    if not affected_tables:
        return

    foreign_keys = int(db.execute("PRAGMA foreign_keys").fetchone()[0])
    legacy_alter_table = int(db.execute("PRAGMA legacy_alter_table").fetchone()[0])
    db.commit()
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("PRAGMA legacy_alter_table = ON")
    try:
        db.execute("BEGIN IMMEDIATE")
        for table_name in affected_tables:
            _rebuild_table_with_repaired_parent(db, table_name, legacy_table, "exploration_runs")
        violations = _foreign_key_violations(db, affected_tables)
        if violations:
            raise RuntimeError(f"Exploration foreign key repair failed: {violations}")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.execute(f"PRAGMA legacy_alter_table = {legacy_alter_table}")
        db.execute(f"PRAGMA foreign_keys = {foreign_keys}")


def _rebuild_table_with_repaired_parent(
    db: sqlite3.Connection,
    table_name: str,
    legacy_parent: str,
    current_parent: str,
) -> None:
    table_row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)
    ).fetchone()
    create_sql = str(table_row["sql"] if isinstance(table_row, sqlite3.Row) else table_row[0])
    schema_objects = db.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE tbl_name = ? AND type IN ('index', 'trigger') AND sql IS NOT NULL ORDER BY type, name",
        (table_name,),
    ).fetchall()
    object_sql = [str(row["sql"] if isinstance(row, sqlite3.Row) else row[0]) for row in schema_objects]
    columns = []
    for row in db.execute(f"PRAGMA table_xinfo({_quote_identifier(table_name)})"):
        hidden = int(row["hidden"] if isinstance(row, sqlite3.Row) else row[6])
        if hidden == 0:
            columns.append(str(row["name"] if isinstance(row, sqlite3.Row) else row[1]))
    temporary_name = f"__repair_{table_name}"
    repaired_sql = re.sub(
        r"^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\"[^\"]+\"|`[^`]+`|\[[^\]]+\]|[^\s(]+)",
        f"CREATE TABLE {_quote_identifier(temporary_name)}",
        create_sql,
        count=1,
        flags=re.IGNORECASE,
    ).replace(legacy_parent, current_parent)
    quoted_columns = ", ".join(_quote_identifier(column) for column in columns)

    db.execute(f"DROP TABLE IF EXISTS {_quote_identifier(temporary_name)}")
    db.execute(repaired_sql)
    db.execute(
        f"INSERT INTO {_quote_identifier(temporary_name)} ({quoted_columns}) "
        f"SELECT {quoted_columns} FROM {_quote_identifier(table_name)}"
    )
    db.execute(f"DROP TABLE {_quote_identifier(table_name)}")
    db.execute(
        f"ALTER TABLE {_quote_identifier(temporary_name)} RENAME TO {_quote_identifier(table_name)}"
    )
    for statement in object_sql:
        db.execute(statement.replace(legacy_parent, current_parent))


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _foreign_key_violations(
    db: sqlite3.Connection,
    tables: list[str] | None = None,
) -> list[dict[str, object]]:
    rows = []
    if tables is None:
        rows.extend(db.execute("PRAGMA foreign_key_check"))
    else:
        for table_name in tables:
            rows.extend(db.execute(f"PRAGMA foreign_key_check({_quote_identifier(table_name)})"))
    return [
        {
            "table": row["table"] if isinstance(row, sqlite3.Row) else row[0],
            "rowid": row["rowid"] if isinstance(row, sqlite3.Row) else row[1],
            "parent": row["parent"] if isinstance(row, sqlite3.Row) else row[2],
            "fkid": row["fkid"] if isinstance(row, sqlite3.Row) else row[3],
        }
        for row in rows
    ]


def _assert_foreign_key_integrity(db: sqlite3.Connection) -> None:
    violations = _foreign_key_violations(db)
    if violations:
        raise RuntimeError(f"Foreign key violations remain after system migrations: {violations}")


def _migrate_ui_automation_case_sources(db: sqlite3.Connection) -> None:
    """Split UI automation sources so manual cases retain referential integrity."""
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(ui_automation_generation_runs)")}
    if "manual_test_case_id" in columns:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_ui_assets_generated_case ON ui_automation_assets(project_id, test_case_id) WHERE test_case_id IS NOT NULL")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_ui_assets_manual_case ON ui_automation_assets(project_id, manual_test_case_id) WHERE manual_test_case_id IS NOT NULL")
        return

    db.commit()
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("PRAGMA legacy_alter_table = ON")
    db.execute("ALTER TABLE ui_automation_execution_runs RENAME TO ui_automation_execution_runs_legacy")
    db.execute("ALTER TABLE ui_automation_assets RENAME TO ui_automation_assets_legacy")
    db.execute("ALTER TABLE ui_automation_generation_runs RENAME TO ui_automation_generation_runs_legacy")

    db.executescript(
        """
        CREATE TABLE ui_automation_generation_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          test_case_id TEXT,
          manual_test_case_id TEXT,
          environment_id TEXT NOT NULL,
          exploration_run_id TEXT NOT NULL DEFAULT '',
          task_id TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'queued',
          suite_path TEXT NOT NULL DEFAULT '',
          changed_files_json TEXT NOT NULL DEFAULT '[]',
          error_message TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          started_at TEXT,
          finished_at TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE,
          FOREIGN KEY(manual_test_case_id) REFERENCES manual_test_cases(id) ON DELETE CASCADE,
          FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE CASCADE,
          CHECK ((test_case_id IS NOT NULL) != (manual_test_case_id IS NOT NULL))
        );
        CREATE TABLE ui_automation_assets (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          test_case_id TEXT,
          manual_test_case_id TEXT,
          source_version INTEGER NOT NULL DEFAULT 1,
          generation_run_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'ready',
          pytest_node_id TEXT NOT NULL,
          suite_path TEXT NOT NULL,
          test_file_path TEXT NOT NULL,
          data_file_path TEXT NOT NULL,
          plan_file_path TEXT NOT NULL,
          source_hash TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE,
          FOREIGN KEY(manual_test_case_id) REFERENCES manual_test_cases(id) ON DELETE CASCADE,
          FOREIGN KEY(generation_run_id) REFERENCES ui_automation_generation_runs(id) ON DELETE CASCADE,
          CHECK ((test_case_id IS NOT NULL) != (manual_test_case_id IS NOT NULL))
        );
        CREATE TABLE ui_automation_execution_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          asset_id TEXT NOT NULL,
          environment_id TEXT NOT NULL,
          task_id TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'queued',
          run_dir TEXT NOT NULL DEFAULT '',
          result_json TEXT NOT NULL DEFAULT '{}',
          stdout_path TEXT NOT NULL DEFAULT '',
          stderr_path TEXT NOT NULL DEFAULT '',
          trace_path TEXT NOT NULL DEFAULT '',
          video_path TEXT NOT NULL DEFAULT '',
          screenshot_paths_json TEXT NOT NULL DEFAULT '[]',
          error_message TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          started_at TEXT,
          finished_at TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(asset_id) REFERENCES ui_automation_assets(id) ON DELETE CASCADE,
          FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE CASCADE
        );
        """
    )
    db.execute(
        """INSERT INTO ui_automation_generation_runs
           SELECT id, project_id, test_case_id, NULL, environment_id, exploration_run_id, task_id,
                  status, suite_path, changed_files_json, error_message, created_by, started_at,
                  finished_at, created_at, updated_at
           FROM ui_automation_generation_runs_legacy"""
    )
    db.execute(
        """INSERT INTO ui_automation_assets
           SELECT id, project_id, test_case_id, NULL, source_version, generation_run_id, status,
                  pytest_node_id, suite_path, test_file_path, data_file_path, plan_file_path,
                  source_hash, created_by, created_at, updated_at
           FROM ui_automation_assets_legacy"""
    )
    db.execute(
        """INSERT INTO ui_automation_execution_runs (
             id, project_id, asset_id, environment_id, task_id, status, run_dir,
             result_json, stdout_path, stderr_path, trace_path, screenshot_paths_json,
             error_message, created_by, started_at, finished_at, created_at, updated_at
           )
           SELECT id, project_id, asset_id, environment_id, task_id, status, run_dir,
                  result_json, stdout_path, stderr_path, trace_path, screenshot_paths_json,
                  error_message, created_by, started_at, finished_at, created_at, updated_at
           FROM ui_automation_execution_runs_legacy"""
    )
    db.execute("DROP TABLE ui_automation_execution_runs_legacy")
    db.execute("DROP TABLE ui_automation_assets_legacy")
    db.execute("DROP TABLE ui_automation_generation_runs_legacy")
    db.execute("CREATE INDEX idx_ui_generation_project_created ON ui_automation_generation_runs(project_id, created_at)")
    db.execute("CREATE INDEX idx_ui_assets_project_updated ON ui_automation_assets(project_id, updated_at)")
    db.execute("CREATE UNIQUE INDEX uq_ui_assets_generated_case ON ui_automation_assets(project_id, test_case_id) WHERE test_case_id IS NOT NULL")
    db.execute("CREATE UNIQUE INDEX uq_ui_assets_manual_case ON ui_automation_assets(project_id, manual_test_case_id) WHERE manual_test_case_id IS NOT NULL")
    db.execute("CREATE INDEX idx_ui_execution_project_created ON ui_automation_execution_runs(project_id, created_at)")
    db.commit()
    db.execute("PRAGMA legacy_alter_table = OFF")
    db.execute("PRAGMA foreign_keys = ON")
    violations = db.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"UI automation source migration has foreign key violations: {violations}")


def _ensure_ui_automation_video_column(db: sqlite3.Connection) -> None:
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(ui_automation_execution_runs)")}
    if "video_path" not in columns:
        db.execute("ALTER TABLE ui_automation_execution_runs ADD COLUMN video_path TEXT NOT NULL DEFAULT ''")


def _ensure_test_point_coverage_structure(db: sqlite3.Connection) -> None:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'test_point_generation_runs'"
    ).fetchone()
    if not row:
        return
    columns = {
        str(column["name"])
        for column in db.execute("PRAGMA table_info(test_point_generation_runs)").fetchall()
    }
    missing_columns = {
        "coverage_status": "ALTER TABLE test_point_generation_runs ADD COLUMN coverage_status TEXT NOT NULL DEFAULT 'pending'",
        "obligation_count": "ALTER TABLE test_point_generation_runs ADD COLUMN obligation_count INTEGER NOT NULL DEFAULT 0",
        "covered_obligation_count": "ALTER TABLE test_point_generation_runs ADD COLUMN covered_obligation_count INTEGER NOT NULL DEFAULT 0",
        "missing_obligations_json": "ALTER TABLE test_point_generation_runs ADD COLUMN missing_obligations_json TEXT NOT NULL DEFAULT '[]'",
        "obligations_json": "ALTER TABLE test_point_generation_runs ADD COLUMN obligations_json TEXT NOT NULL DEFAULT '[]'",
        "unsupported_assumptions_json": "ALTER TABLE test_point_generation_runs ADD COLUMN unsupported_assumptions_json TEXT NOT NULL DEFAULT '[]'",
        "supplement_round": "ALTER TABLE test_point_generation_runs ADD COLUMN supplement_round INTEGER NOT NULL DEFAULT 0",
    }
    for column, statement in missing_columns.items():
        if column not in columns:
            db.execute(statement)


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


def _migrate_performance_scripts_to_single_record(db: sqlite3.Connection) -> None:
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(performance_test_scripts)")}
    table = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'performance_test_scripts'"
    ).fetchone()
    table_sql = str(table["sql"] or "") if table else ""
    if "version" not in columns and "confirmed_by" not in columns and "'valid'" in table_sql:
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_performance_test_scripts_project_updated "
            "ON performance_test_scripts(project_id, updated_at)"
        )
        return

    has_versions = "version" in columns
    db.commit()
    db.execute("PRAGMA foreign_keys = OFF")
    db.executescript(
        """
        CREATE TABLE performance_test_scripts_validated (
          id TEXT PRIMARY KEY,
          performance_test_id TEXT NOT NULL UNIQUE,
          project_id TEXT NOT NULL,
          generation_source TEXT NOT NULL CHECK(generation_source IN ('ai_plan', 'default_plan', 'user_edited')),
          model_id TEXT NOT NULL DEFAULT '',
          prompt_version TEXT NOT NULL DEFAULT '',
          plan_json TEXT NOT NULL DEFAULT '{}',
          code TEXT NOT NULL,
          assumptions_json TEXT NOT NULL DEFAULT '[]',
          required_runtime_variables_json TEXT NOT NULL DEFAULT '[]',
          validation_status TEXT NOT NULL CHECK(validation_status IN ('generating', 'validation_failed', 'valid')),
          validation_result_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(performance_test_id) REFERENCES performance_tests(id) ON DELETE CASCADE,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """
    )
    latest_filter = (
        "WHERE legacy.id = (SELECT current.id FROM performance_test_scripts AS current "
        "WHERE current.performance_test_id = legacy.performance_test_id "
        "ORDER BY current.version DESC LIMIT 1)"
        if has_versions
        else ""
    )
    updated_at_expression = "legacy.created_at" if "updated_at" not in columns else "legacy.updated_at"
    db.execute(
        f"""
        INSERT INTO performance_test_scripts_validated (
          id, performance_test_id, project_id, generation_source, model_id, prompt_version,
          plan_json, code, assumptions_json, required_runtime_variables_json,
          validation_status, validation_result_json, created_at, updated_at
        )
        SELECT
          legacy.id, legacy.performance_test_id, legacy.project_id, legacy.generation_source,
          legacy.model_id, legacy.prompt_version, legacy.plan_json, legacy.code,
          legacy.assumptions_json, legacy.required_runtime_variables_json,
          CASE
            WHEN legacy.validation_status IN ('confirmed', 'pending_confirmation', 'superseded') THEN 'valid'
            ELSE legacy.validation_status
          END,
          legacy.validation_result_json, legacy.created_at, {updated_at_expression}
        FROM performance_test_scripts AS legacy
        {latest_filter}
        """
    )
    if has_versions:
        db.execute(
            """
            UPDATE performance_test_runs
            SET script_id = (
              SELECT current.id FROM performance_test_scripts_validated AS current
              WHERE current.performance_test_id = performance_test_runs.performance_test_id
            )
            WHERE EXISTS (
              SELECT 1 FROM performance_test_scripts_validated AS current
              WHERE current.performance_test_id = performance_test_runs.performance_test_id
            )
            """
        )
    db.execute("DROP TABLE performance_test_scripts")
    db.execute("ALTER TABLE performance_test_scripts_validated RENAME TO performance_test_scripts")
    db.execute(
        "CREATE INDEX idx_performance_test_scripts_project_updated "
        "ON performance_test_scripts(project_id, updated_at)"
    )
    db.commit()
    db.execute("PRAGMA foreign_keys = ON")
    violations = db.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"Performance script migration has foreign key violations: {violations}")


def _ensure_performance_analysis_columns(db: sqlite3.Connection) -> None:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'performance_analysis_sessions'"
    ).fetchone()
    if not row:
        return
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(performance_analysis_sessions)")}
    additions = {
        "analysis_status": "ALTER TABLE performance_analysis_sessions ADD COLUMN analysis_status TEXT NOT NULL DEFAULT 'collecting'",
        "analysis_stage": "ALTER TABLE performance_analysis_sessions ADD COLUMN analysis_stage TEXT NOT NULL DEFAULT 'evidence_collection'",
        "repair_status": "ALTER TABLE performance_analysis_sessions ADD COLUMN repair_status TEXT NOT NULL DEFAULT 'not_applicable'",
        "application_status": "ALTER TABLE performance_analysis_sessions ADD COLUMN application_status TEXT NOT NULL DEFAULT 'not_requested'",
        "selected_change_ids_json": "ALTER TABLE performance_analysis_sessions ADD COLUMN selected_change_ids_json TEXT NOT NULL DEFAULT '[]'",
        "preflight_json": "ALTER TABLE performance_analysis_sessions ADD COLUMN preflight_json TEXT NOT NULL DEFAULT '{}'",
        "applied_script_id": "ALTER TABLE performance_analysis_sessions ADD COLUMN applied_script_id TEXT NOT NULL DEFAULT ''",
        "applied_run_id": "ALTER TABLE performance_analysis_sessions ADD COLUMN applied_run_id TEXT NOT NULL DEFAULT ''",
        "applied_by": "ALTER TABLE performance_analysis_sessions ADD COLUMN applied_by TEXT NOT NULL DEFAULT ''",
        "applied_at": "ALTER TABLE performance_analysis_sessions ADD COLUMN applied_at TEXT",
        "metric_snapshot_json": "ALTER TABLE performance_analysis_sessions ADD COLUMN metric_snapshot_json TEXT NOT NULL DEFAULT '{}'",
        "report_snapshot_json": "ALTER TABLE performance_analysis_sessions ADD COLUMN report_snapshot_json TEXT NOT NULL DEFAULT '{}'",
        "calculator_version": "ALTER TABLE performance_analysis_sessions ADD COLUMN calculator_version TEXT NOT NULL DEFAULT ''",
        "prompt_version": "ALTER TABLE performance_analysis_sessions ADD COLUMN prompt_version TEXT NOT NULL DEFAULT ''",
        "source_fingerprint": "ALTER TABLE performance_analysis_sessions ADD COLUMN source_fingerprint TEXT NOT NULL DEFAULT ''",
        "audience": "ALTER TABLE performance_analysis_sessions ADD COLUMN audience TEXT NOT NULL DEFAULT 'engineer'",
    }
    added = set()
    for column, statement in additions.items():
        if column not in columns:
            db.execute(statement)
            added.add(column)
    if "analysis_status" in added:
        db.execute(
            """
            UPDATE performance_analysis_sessions
            SET analysis_status = CASE status
              WHEN 'collecting' THEN 'collecting'
              WHEN 'analyzing' THEN 'analyzing'
              WHEN 'failed' THEN 'failed'
              ELSE 'completed'
            END
            """
        )
    if "repair_status" in added:
        db.execute(
            """
            UPDATE performance_analysis_sessions
            SET repair_status = CASE status
              WHEN 'waiting_approval' THEN 'available'
              WHEN 'rejected' THEN 'rejected'
              ELSE 'not_applicable'
            END
            """
        )


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
    if "parent_run_id" not in columns:
        db.execute("ALTER TABLE api_automation_runs ADD COLUMN parent_run_id TEXT")
    if "source_repair_attempt_id" not in columns:
        db.execute("ALTER TABLE api_automation_runs ADD COLUMN source_repair_attempt_id TEXT")
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
          parent_run_id TEXT,
          source_repair_attempt_id TEXT,
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
          observation_result_path, parent_run_id, source_repair_attempt_id,
          summary_json, error_message, created_by,
          created_at, updated_at, finished_at
        )
        SELECT
          id, project_id, api_environment_id, task_id, status, script_ids_json,
          target_type, target_ids_json, execution_snapshot_json, command_summary,
          stdout_path, stderr_path, json_report_path, scenario_result_path,
          observation_result_path, parent_run_id, source_repair_attempt_id,
          summary_json, error_message, created_by,
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


def _ensure_api_scenario_ai_plan_table(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS api_scenario_ai_plans (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          scenario_id TEXT,
          expected_revision INTEGER,
          goal TEXT NOT NULL,
          request_json TEXT NOT NULL DEFAULT '{}',
          plan_json TEXT NOT NULL DEFAULT '{}',
          validation_json TEXT NOT NULL DEFAULT '{}',
          status TEXT NOT NULL CHECK(status IN ('preview', 'applied', 'discarded', 'expired')) DEFAULT 'preview',
          lifecycle_status TEXT NOT NULL DEFAULT 'completed',
          error_message TEXT NOT NULL DEFAULT '',
          model_provider TEXT NOT NULL DEFAULT '',
          model_name TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          applied_by TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          expires_at TEXT NOT NULL,
          applied_at TEXT,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(scenario_id) REFERENCES api_scenarios(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_api_scenario_ai_plans_project_created
          ON api_scenario_ai_plans(project_id, created_at DESC);
        """
    )
    columns = {str(column["name"]) for column in db.execute("PRAGMA table_info(api_scenario_ai_plans)").fetchall()}
    for column, definition in {
        "lifecycle_status": "TEXT NOT NULL DEFAULT 'completed'",
        "error_message": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
    }.items():
        if column not in columns:
            db.execute(f"ALTER TABLE api_scenario_ai_plans ADD COLUMN {column} {definition}")
    db.execute("UPDATE api_scenario_ai_plans SET updated_at = created_at WHERE updated_at = ''")


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
        db.execute(
            """
            UPDATE operation_log_retention_policy
            SET retention_days = 10,
                updated_by = 'system',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 'default' AND retention_days > 10
            """
        )
        return
    db.execute(
        """
        INSERT INTO operation_log_retention_policy (id, retention_days, max_rows, protect_high_risk)
        VALUES ('default', 10, 100000, 1)
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
