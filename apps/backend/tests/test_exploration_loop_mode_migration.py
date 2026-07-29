import sqlite3

from app.seed import seeds


OLD_EXPLORATION_RUNS_SQL = """
CREATE TABLE exploration_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  environment_id TEXT NOT NULL,
  requirement_doc_id TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  exploration_mode TEXT NOT NULL DEFAULT 'goal' CHECK(exploration_mode IN ('goal', 'autonomous')),
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


def _connection() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY);
        CREATE TABLE project_environments (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        INSERT INTO projects (id) VALUES ('project-1');
        INSERT INTO project_environments (id, project_id) VALUES ('environment-1', 'project-1');
        """
    )
    return db


def _foreign_key_targets(db: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["table"]) for row in db.execute(f'PRAGMA foreign_key_list("{table}")')}


def test_loop_mode_upgrade_preserves_existing_child_foreign_keys() -> None:
    db = _connection()
    db.execute(OLD_EXPLORATION_RUNS_SQL)
    db.executescript(
        """
        CREATE TABLE exploration_pages (
          id TEXT PRIMARY KEY,
          exploration_run_id TEXT NOT NULL,
          title TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE
        );
        INSERT INTO exploration_runs (
          id, project_id, environment_id, title, created_by
        ) VALUES (
          'run-1', 'project-1', 'environment-1', 'Legacy run', 'user-1'
        );
        INSERT INTO exploration_pages (id, exploration_run_id, title)
        VALUES ('page-1', 'run-1', 'Existing page');
        """
    )

    seeds._ensure_exploration_loop_mode(db)

    run_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'exploration_runs'"
    ).fetchone()["sql"]
    page = db.execute("SELECT id, exploration_run_id, title FROM exploration_pages").fetchone()

    assert "'loop'" in run_sql
    assert _foreign_key_targets(db, "exploration_pages") == {"exploration_runs"}
    assert dict(page) == {
        "id": "page-1",
        "exploration_run_id": "run-1",
        "title": "Existing page",
    }
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()


def test_repair_wrong_exploration_foreign_keys_once_without_data_loss() -> None:
    db = _connection()
    db.execute(OLD_EXPLORATION_RUNS_SQL.replace("('goal', 'autonomous')", "('goal', 'autonomous', 'loop')"))
    db.execute(
        """
        INSERT INTO exploration_runs (id, project_id, environment_id, title, created_by)
        VALUES ('run-1', 'project-1', 'environment-1', 'Existing run', 'user-1')
        """
    )
    db.commit()
    db.execute("PRAGMA foreign_keys = OFF")
    db.executescript(
        """
        CREATE TABLE exploration_module_coverages (
          id TEXT PRIMARY KEY,
          exploration_run_id TEXT NOT NULL,
          module_key TEXT NOT NULL,
          FOREIGN KEY(exploration_run_id) REFERENCES "exploration_runs_legacy_loop_mode"(id) ON DELETE CASCADE,
          UNIQUE(exploration_run_id, module_key)
        );
        CREATE TABLE exploration_pages (
          id TEXT PRIMARY KEY,
          exploration_run_id TEXT NOT NULL,
          title TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(exploration_run_id) REFERENCES "exploration_runs_legacy_loop_mode"(id) ON DELETE CASCADE
        );
        CREATE INDEX idx_exploration_pages_title ON exploration_pages(title);
        CREATE TABLE exploration_blockers (
          id TEXT PRIMARY KEY,
          exploration_run_id TEXT NOT NULL,
          reason TEXT NOT NULL,
          FOREIGN KEY(exploration_run_id) REFERENCES "exploration_runs_legacy_loop_mode"(id) ON DELETE CASCADE
        );
        CREATE TABLE exploration_artifacts (
          id TEXT PRIMARY KEY,
          exploration_run_id TEXT NOT NULL,
          artifact_type TEXT NOT NULL,
          file_path TEXT NOT NULL,
          FOREIGN KEY(exploration_run_id) REFERENCES "exploration_runs_legacy_loop_mode"(id) ON DELETE CASCADE
        );
        CREATE TABLE exploration_document_versions (
          id TEXT PRIMARY KEY,
          exploration_run_id TEXT NOT NULL,
          version_no INTEGER NOT NULL,
          markdown_path TEXT NOT NULL,
          FOREIGN KEY(exploration_run_id) REFERENCES "exploration_runs_legacy_loop_mode"(id) ON DELETE CASCADE,
          UNIQUE(exploration_run_id, version_no)
        );
        CREATE TABLE exploration_elements (
          id TEXT PRIMARY KEY,
          exploration_run_id TEXT NOT NULL,
          page_id TEXT,
          element_name TEXT NOT NULL,
          FOREIGN KEY(exploration_run_id) REFERENCES "exploration_runs_legacy_loop_mode"(id) ON DELETE CASCADE,
          FOREIGN KEY(page_id) REFERENCES exploration_pages(id) ON DELETE SET NULL
        );
        INSERT INTO exploration_module_coverages VALUES ('coverage-1', 'run-1', 'module-1');
        INSERT INTO exploration_pages VALUES ('page-1', 'run-1', 'Existing page');
        INSERT INTO exploration_blockers VALUES ('blocker-1', 'run-1', 'Blocked');
        INSERT INTO exploration_artifacts VALUES ('artifact-1', 'run-1', 'report', 'report.md');
        INSERT INTO exploration_document_versions VALUES ('version-1', 'run-1', 1, 'report-v1.md');
        INSERT INTO exploration_elements VALUES ('element-1', 'run-1', 'page-1', 'Submit');
        """
    )
    db.execute("PRAGMA foreign_keys = ON")
    affected_tables = {
        "exploration_module_coverages",
        "exploration_pages",
        "exploration_blockers",
        "exploration_artifacts",
        "exploration_document_versions",
        "exploration_elements",
    }

    seeds._repair_exploration_run_foreign_keys(db)

    first_schema = {
        table: db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()["sql"]
        for table in affected_tables
    }
    first_rows = {
        table: [tuple(row) for row in db.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]
        for table in affected_tables
    }
    seeds._repair_exploration_run_foreign_keys(db)
    second_schema = {
        table: db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()["sql"]
        for table in affected_tables
    }
    second_rows = {
        table: [tuple(row) for row in db.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]
        for table in affected_tables
    }

    for table in affected_tables:
        assert "exploration_runs_legacy_loop_mode" not in first_schema[table]
        assert "exploration_runs" in _foreign_key_targets(db, table)
    assert db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'idx_exploration_pages_title'"
    ).fetchone()
    assert first_schema == second_schema
    assert first_rows == second_rows
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()
