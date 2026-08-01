import sqlite3

from app.seed.seeds import (
    _ensure_exploration_loop_mode,
    _repair_legacy_exploration_run_foreign_keys,
)


def _connection() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def test_repairs_legacy_exploration_run_foreign_keys_without_losing_data() -> None:
    db = _connection()
    db.executescript(
        """
        PRAGMA foreign_keys = OFF;
        CREATE TABLE exploration_runs (id TEXT PRIMARY KEY);
        INSERT INTO exploration_runs VALUES ('run-1');
        CREATE TABLE exploration_pages (
          id TEXT PRIMARY KEY,
          exploration_run_id TEXT NOT NULL,
          title TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(exploration_run_id)
            REFERENCES "exploration_runs_legacy_loop_mode"(id) ON DELETE CASCADE
        );
        INSERT INTO exploration_pages VALUES ('page-1', 'run-1', 'Login');
        CREATE INDEX idx_exploration_pages_title ON exploration_pages(title);
        PRAGMA foreign_keys = ON;
        """
    )

    _repair_legacy_exploration_run_foreign_keys(db)

    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert db.execute("SELECT * FROM exploration_pages").fetchone()["title"] == "Login"
    assert db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'idx_exploration_pages_title'"
    ).fetchone()
    foreign_key = db.execute("PRAGMA foreign_key_list(exploration_pages)").fetchone()
    assert foreign_key["table"] == "exploration_runs"


def test_loop_mode_migration_keeps_child_foreign_keys_on_new_table() -> None:
    db = _connection()
    db.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY);
        CREATE TABLE project_environments (id TEXT PRIMARY KEY);
        INSERT INTO projects VALUES ('project-1');
        INSERT INTO project_environments VALUES ('environment-1');
        CREATE TABLE exploration_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          environment_id TEXT NOT NULL,
          requirement_doc_id TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          exploration_mode TEXT NOT NULL DEFAULT 'goal'
            CHECK(exploration_mode IN ('goal', 'autonomous')),
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
          FOREIGN KEY(project_id) REFERENCES projects(id),
          FOREIGN KEY(environment_id) REFERENCES project_environments(id)
        );
        INSERT INTO exploration_runs (
          id, project_id, environment_id, title, created_by
        ) VALUES ('run-1', 'project-1', 'environment-1', 'Run', 'user-1');
        CREATE TABLE exploration_pages (
          id TEXT PRIMARY KEY,
          exploration_run_id TEXT NOT NULL,
          FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE
        );
        INSERT INTO exploration_pages VALUES ('page-1', 'run-1');
        """
    )

    _ensure_exploration_loop_mode(db)

    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("SELECT id FROM exploration_pages").fetchone()["id"] == "page-1"
    foreign_key = db.execute("PRAGMA foreign_key_list(exploration_pages)").fetchone()
    assert foreign_key["table"] == "exploration_runs"
    table_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'exploration_runs'"
    ).fetchone()["sql"]
    assert "'loop'" in table_sql
