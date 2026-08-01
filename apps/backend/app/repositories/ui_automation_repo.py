from __future__ import annotations

import json
from sqlite3 import Connection, Row


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ui_automation_generation_runs (
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
  CHECK ((test_case_id IS NOT NULL) != (manual_test_case_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_ui_generation_project_created
  ON ui_automation_generation_runs(project_id, created_at);

CREATE TABLE IF NOT EXISTS ui_automation_assets (
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
  CHECK ((test_case_id IS NOT NULL) != (manual_test_case_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_ui_assets_project_updated
  ON ui_automation_assets(project_id, updated_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ui_assets_generated_case
  ON ui_automation_assets(project_id, test_case_id) WHERE test_case_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_ui_assets_manual_case
  ON ui_automation_assets(project_id, manual_test_case_id) WHERE manual_test_case_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS ui_automation_execution_runs (
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
  screenshot_paths_json TEXT NOT NULL DEFAULT '[]',
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ui_execution_project_created
  ON ui_automation_execution_runs(project_id, created_at);
"""


def create_generation_run(
    db: Connection,
    *,
    run_id: str,
    project_id: str,
    test_case_id: str | None,
    manual_test_case_id: str | None,
    environment_id: str,
    exploration_run_id: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO ui_automation_generation_runs (
          id, project_id, test_case_id, manual_test_case_id, environment_id,
          exploration_run_id, task_id, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, project_id, test_case_id, manual_test_case_id, environment_id, exploration_run_id,
         f"ui_generation:{run_id}", created_by),
    )


def find_generation_run(db: Connection, run_id: str) -> Row | None:
    return db.execute("SELECT * FROM ui_automation_generation_runs WHERE id = ?", (run_id,)).fetchone()


def list_generation_runs(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM ui_automation_generation_runs
        WHERE project_id = ?
        ORDER BY updated_at DESC, created_at DESC
        """,
        (project_id,),
    ).fetchall()


def list_asset_generation_runs(db: Connection, asset: Row) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM ui_automation_generation_runs
        WHERE project_id = ?
          AND ((test_case_id = ? AND ? IS NOT NULL)
               OR (manual_test_case_id = ? AND ? IS NOT NULL))
        ORDER BY created_at DESC
        """,
        (
            asset["project_id"],
            asset["test_case_id"],
            asset["test_case_id"],
            asset["manual_test_case_id"],
            asset["manual_test_case_id"],
        ),
    ).fetchall()


def list_active_generation_runs(db: Connection) -> list[Row]:
    return db.execute(
        "SELECT * FROM ui_automation_generation_runs WHERE status IN ('queued', 'running')"
    ).fetchall()


def update_generation_run(db: Connection, run_id: str, **fields) -> None:
    allowed = {
        "status",
        "suite_path",
        "error_message",
        "started_at",
        "finished_at",
    }
    assignments = []
    values = []
    for key, value in fields.items():
        if key == "changed_files":
            assignments.append("changed_files_json = ?")
            values.append(json.dumps(value, ensure_ascii=False))
        elif key in allowed:
            assignments.append(f"{key} = ?")
            values.append(value)
    if not assignments:
        return
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(run_id)
    db.execute(f"UPDATE ui_automation_generation_runs SET {', '.join(assignments)} WHERE id = ?", values)


def upsert_asset(
    db: Connection,
    *,
    asset_id: str,
    project_id: str,
    test_case_id: str | None,
    manual_test_case_id: str | None,
    source_version: int,
    generation_run_id: str,
    status: str,
    pytest_node_id: str,
    suite_path: str,
    test_file_path: str,
    data_file_path: str,
    plan_file_path: str,
    source_hash: str,
    created_by: str,
) -> str:
    existing = db.execute(
        """
        SELECT id FROM ui_automation_assets
        WHERE project_id = ?
          AND ((test_case_id = ? AND ? IS NOT NULL)
               OR (manual_test_case_id = ? AND ? IS NOT NULL))
        """,
        (project_id, test_case_id, test_case_id, manual_test_case_id, manual_test_case_id),
    ).fetchone()
    resolved_id = existing["id"] if existing else asset_id
    db.execute(
        """
        INSERT INTO ui_automation_assets (
          id, project_id, test_case_id, manual_test_case_id, source_version, generation_run_id, status,
          pytest_node_id, suite_path, test_file_path, data_file_path, plan_file_path,
          source_hash, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          test_case_id = excluded.test_case_id,
          manual_test_case_id = excluded.manual_test_case_id,
          source_version = excluded.source_version,
          generation_run_id = excluded.generation_run_id,
          status = excluded.status,
          pytest_node_id = excluded.pytest_node_id,
          suite_path = excluded.suite_path,
          test_file_path = excluded.test_file_path,
          data_file_path = excluded.data_file_path,
          plan_file_path = excluded.plan_file_path,
          source_hash = excluded.source_hash,
          updated_at = CURRENT_TIMESTAMP
        """,
        (
            resolved_id,
            project_id,
            test_case_id,
            manual_test_case_id,
            source_version,
            generation_run_id,
            status,
            pytest_node_id,
            suite_path,
            test_file_path,
            data_file_path,
            plan_file_path,
            source_hash,
            created_by,
        ),
    )
    return resolved_id


def find_asset(db: Connection, asset_id: str) -> Row | None:
    return db.execute("SELECT * FROM ui_automation_assets WHERE id = ?", (asset_id,)).fetchone()


def list_assets(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM ui_automation_assets WHERE project_id = ? ORDER BY updated_at DESC",
        (project_id,),
    ).fetchall()


def create_execution_run(
    db: Connection,
    *,
    run_id: str,
    project_id: str,
    asset_id: str,
    environment_id: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO ui_automation_execution_runs (
          id, project_id, asset_id, environment_id, task_id, created_by
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, project_id, asset_id, environment_id, f"ui_execution:{run_id}", created_by),
    )


def find_execution_run(db: Connection, run_id: str) -> Row | None:
    return db.execute("SELECT * FROM ui_automation_execution_runs WHERE id = ?", (run_id,)).fetchone()


def list_execution_runs(db: Connection, project_id: str, asset_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM ui_automation_execution_runs
        WHERE project_id = ? AND asset_id = ?
        ORDER BY created_at DESC
        """,
        (project_id, asset_id),
    ).fetchall()


def list_active_execution_runs(db: Connection) -> list[Row]:
    return db.execute(
        "SELECT * FROM ui_automation_execution_runs WHERE status IN ('queued', 'running', 'stopping')"
    ).fetchall()


def delete_execution_run(db: Connection, run_id: str) -> None:
    db.execute("DELETE FROM ui_automation_execution_runs WHERE id = ?", (run_id,))


def update_execution_run(db: Connection, run_id: str, **fields) -> None:
    assignments, values = _execution_run_update(fields)
    if not assignments:
        return
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(run_id)
    db.execute(f"UPDATE ui_automation_execution_runs SET {', '.join(assignments)} WHERE id = ?", values)


def transition_execution_run(db: Connection, run_id: str, from_statuses: tuple[str, ...], **fields) -> bool:
    assignments, values = _execution_run_update(fields)
    if not assignments or not from_statuses:
        return False
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    placeholders = ", ".join("?" for _ in from_statuses)
    cursor = db.execute(
        f"UPDATE ui_automation_execution_runs SET {', '.join(assignments)} "
        f"WHERE id = ? AND status IN ({placeholders})",
        [*values, run_id, *from_statuses],
    )
    return cursor.rowcount == 1


def _execution_run_update(fields: dict) -> tuple[list[str], list]:
    allowed = {
        "status",
        "run_dir",
        "stdout_path",
        "stderr_path",
        "error_message",
        "started_at",
        "finished_at",
    }
    assignments = []
    values = []
    for key, value in fields.items():
        if key == "result":
            assignments.append("result_json = ?")
            values.append(json.dumps(value, ensure_ascii=False))
        elif key == "screenshot_paths":
            assignments.append("screenshot_paths_json = ?")
            values.append(json.dumps(value, ensure_ascii=False))
        elif key in allowed:
            assignments.append(f"{key} = ?")
            values.append(value)
    return assignments, values


__all__ = [name for name in globals() if not name.startswith("_")]
