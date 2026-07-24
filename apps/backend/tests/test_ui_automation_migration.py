from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.core import settings
from app.services.ui_automation.migration import (
    migrate_legacy_project_suite,
    remove_migrated_legacy_project_files,
)


def _database() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE ui_automation_generation_runs (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL, suite_path TEXT NOT NULL
        );
        CREATE TABLE ui_automation_assets (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL, suite_path TEXT NOT NULL
        );
        CREATE TABLE ui_automation_execution_runs (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL, run_dir TEXT NOT NULL,
          result_json TEXT NOT NULL, stdout_path TEXT NOT NULL, stderr_path TEXT NOT NULL,
          trace_path TEXT NOT NULL, video_path TEXT NOT NULL, screenshot_paths_json TEXT NOT NULL
        );
        """
    )
    return db


def test_migrates_shared_suite_into_owning_project(monkeypatch, tmp_path: Path):
    projects_root = tmp_path / "projects"
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", projects_root)
    legacy_root = tmp_path / "ui_automation/pytest_playwright"
    project_key = "project_1"
    test_file = legacy_root / f"testcases/generated/{project_key}/test_login.py"
    page_file = legacy_root / f"pages/generated/{project_key}/login_page.py"
    data_file = legacy_root / f"data/projects/{project_key}/cases/login.yaml"
    run_dir = legacy_root / "runs/uirun-1"
    for path, content in (
        (test_file, "def test_login(): pass\n"),
        (page_file, "class LoginPage: pass\n"),
        (data_file, "case: login\n"),
        (run_dir / "stdout.txt", "passed\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    db = _database()
    db.execute(
        "INSERT INTO ui_automation_generation_runs VALUES ('uigen-1', 'project-1', ?)",
        (str(legacy_root),),
    )
    db.execute(
        "INSERT INTO ui_automation_assets VALUES ('asset-1', 'project-1', ?)",
        (str(legacy_root),),
    )
    db.execute(
        "INSERT INTO ui_automation_execution_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "uirun-1",
            "project-1",
            str(run_dir),
            json.dumps({"stdout_path": str(run_dir / "stdout.txt")}),
            str(run_dir / "stdout.txt"),
            "",
            "",
            "",
            json.dumps([str(run_dir / "failure.png")]),
        ),
    )

    report = migrate_legacy_project_suite(db, "project-1")
    target_root = projects_root / "project-1/ui_automation/pytest_playwright"

    assert report["migrated"] is True
    assert (target_root / f"testcases/generated/{project_key}/test_login.py").is_file()
    assert (target_root / f"pages/generated/{project_key}/login_page.py").is_file()
    assert (target_root / f"data/projects/{project_key}/cases/login.yaml").is_file()
    assert (target_root / "runs/uirun-1/stdout.txt").read_text(encoding="utf-8") == "passed\n"
    assert db.execute("SELECT suite_path FROM ui_automation_assets").fetchone()[0] == (
        "project-1/ui_automation/pytest_playwright"
    )
    execution = db.execute("SELECT * FROM ui_automation_execution_runs").fetchone()
    assert execution["run_dir"] == "project-1/ui_automation/pytest_playwright/runs/uirun-1"
    assert json.loads(execution["result_json"])["stdout_path"].startswith(
        "project-1/ui_automation/pytest_playwright/runs/uirun-1"
    )

    migrated_test = target_root / f"testcases/generated/{project_key}/test_login.py"
    migrated_test.write_text("# new project content\n", encoding="utf-8")
    second_report = migrate_legacy_project_suite(db, "project-1")
    assert second_report["migrated"] is False
    assert migrated_test.read_text(encoding="utf-8") == "# new project content\n"


def test_resumes_file_copy_after_database_paths_were_already_migrated(monkeypatch, tmp_path: Path):
    projects_root = tmp_path / "projects"
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", projects_root)
    legacy_root = tmp_path / "ui_automation/pytest_playwright"
    source = legacy_root / "testcases/generated/project_1/test_login.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_login(): pass\n", encoding="utf-8")

    db = _database()
    target_root = projects_root / "project-1/ui_automation/pytest_playwright"
    stored_target = "project-1/ui_automation/pytest_playwright"
    db.execute("INSERT INTO ui_automation_generation_runs VALUES ('uigen-1', 'project-1', ?)", (stored_target,))
    db.execute("INSERT INTO ui_automation_assets VALUES ('asset-1', 'project-1', ?)", (stored_target,))

    report = migrate_legacy_project_suite(db, "project-1")

    assert report["migrated"] is True
    assert (target_root / "testcases/generated/project_1/test_login.py").read_text(encoding="utf-8") == (
        "def test_login(): pass\n"
    )


def test_cleanup_only_removes_migrated_project_namespace(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    legacy_root = tmp_path / "ui_automation/pytest_playwright"
    own_file = legacy_root / "testcases/generated/project_1/test_case.py"
    other_file = legacy_root / "testcases/generated/project_2/test_case.py"
    run_file = legacy_root / "runs/uirun-1/result.json"
    target_root = tmp_path / "projects/project-1/ui_automation/pytest_playwright"
    target_own_file = target_root / "testcases/generated/project_1/test_case.py"
    target_run_file = target_root / "runs/uirun-1/result.json"
    for path in (own_file, other_file, run_file, target_own_file, target_run_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content", encoding="utf-8")

    remove_migrated_legacy_project_files("project-1", ["uirun-1"])

    assert not own_file.exists()
    assert not run_file.exists()
    assert other_file.exists()


def test_cleanup_preserves_legacy_files_when_target_conflicts(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    legacy_file = tmp_path / "ui_automation/pytest_playwright/testcases/generated/project_1/test_case.py"
    target_file = (
        tmp_path / "projects/project-1/ui_automation/pytest_playwright/testcases/generated/project_1/test_case.py"
    )
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_text("legacy", encoding="utf-8")
    target_file.write_text("newer", encoding="utf-8")

    removed = remove_migrated_legacy_project_files("project-1", [])

    assert removed == []
    assert legacy_file.read_text(encoding="utf-8") == "legacy"
    assert target_file.read_text(encoding="utf-8") == "newer"
