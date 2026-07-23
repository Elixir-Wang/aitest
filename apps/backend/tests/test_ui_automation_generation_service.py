from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException

from app.core import db as core_db
from app.seed.init_db import init_db
from app.services.ui_automation import artifact_storage, context, service


ACTOR = {"id": "u-admin", "role": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()
    with core_db.connect() as db:
        db.execute("INSERT INTO projects (id, name, status, description) VALUES ('project-1', '测试项目', 'active', '')")
        db.execute(
            """INSERT INTO project_environments (id, project_id, name, site_url, created_by)
               VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')"""
        )
        db.execute(
            """INSERT INTO manual_test_cases (id, project_id, title, preconditions, steps_json, notes, created_by)
               VALUES ('manual-case-1', 'project-1', '手工登录用例', '', '[]', '', 'u-admin')"""
        )


def test_find_source_case_supports_manual_test_cases(monkeypatch):
    manual_case = {"id": "manual-case-1", "project_id": "project-1", "title": "手工登录用例"}
    monkeypatch.setattr(service.test_case_repo, "find_case_by_id", lambda db, case_id: None)
    monkeypatch.setattr(service.test_case_repo, "find_manual_case_by_id", lambda db, case_id: manual_case)

    source_case, is_manual = service._find_source_case(object(), "manual-case-1")

    assert source_case == manual_case
    assert is_manual is True


def test_create_generation_run_persists_manual_case_source(monkeypatch, tmp_path: Path):
    _use_temp_db(monkeypatch, tmp_path)

    created = service.create_generation_run(
        "project-1",
        {"test_case_id": "manual-case-1", "environment_id": "env-1"},
        ACTOR,
    )

    assert created["test_case_id"] == "manual-case-1"
    assert created["manual_test_case_id"] == "manual-case-1"
    assert created["exploration_run_id"] == ""


def test_create_generation_run_uses_latest_compatible_exploration_evidence(monkeypatch, tmp_path: Path):
    _use_temp_db(monkeypatch, tmp_path)
    evidence_path = tmp_path / "page.yaml"
    evidence_path.write_text("page:\n  title: 登录页\n", encoding="utf-8")
    with core_db.connect() as db:
        db.execute(
            """INSERT INTO exploration_runs (id, project_id, environment_id, title, created_by)
               VALUES ('explore-1', 'project-1', 'env-1', '登录页探索', 'u-admin')"""
        )
        db.execute(
            """INSERT INTO exploration_artifacts (id, exploration_run_id, artifact_type, file_path)
               VALUES ('artifact-1', 'explore-1', 'page_yaml', ?)""",
            (str(evidence_path),),
        )

    created = service.create_generation_run(
        "project-1",
        {"test_case_id": "manual-case-1", "environment_id": "env-1"},
        ACTOR,
    )

    assert created["exploration_run_id"] == "explore-1"


def _insert_execution_run(tmp_path: Path, *, status: str) -> Path:
    suite_path = tmp_path / "suite"
    run_dir = suite_path / "runs" / "uirun-1"
    run_dir.mkdir(parents=True)
    (run_dir / "stdout.log").write_text("run output", encoding="utf-8")
    with core_db.connect() as db:
        db.execute(
            """INSERT INTO ui_automation_generation_runs (
                 id, project_id, manual_test_case_id, environment_id, status, suite_path, created_by
               ) VALUES ('uigen-1', 'project-1', 'manual-case-1', 'env-1', 'completed', ?, 'u-admin')""",
            (str(suite_path),),
        )
        db.execute(
            """INSERT INTO ui_automation_assets (
                 id, project_id, manual_test_case_id, generation_run_id, pytest_node_id, suite_path,
                 test_file_path, data_file_path, plan_file_path, source_hash, created_by
               ) VALUES (
                 'uiasset-1', 'project-1', 'manual-case-1', 'uigen-1', 'tests/test_case.py::test_case', ?,
                 'tests/test_case.py', 'data/case.yaml', 'data/case.plan.json', 'hash-1', 'u-admin'
               )""",
            (str(suite_path),),
        )
        db.execute(
            """INSERT INTO ui_automation_execution_runs (
                 id, project_id, asset_id, environment_id, status, run_dir, stdout_path, created_by
               ) VALUES ('uirun-1', 'project-1', 'uiasset-1', 'env-1', ?, ?, ?, 'u-admin')""",
            (status, str(run_dir), str(run_dir / "stdout.log")),
        )
    return run_dir


def test_delete_execution_run_removes_record_and_artifacts(monkeypatch, tmp_path: Path):
    _use_temp_db(monkeypatch, tmp_path)
    run_dir = _insert_execution_run(tmp_path, status="failed")

    service.delete_execution_run("project-1", "uirun-1", ACTOR)

    assert not run_dir.exists()
    with core_db.connect() as db:
        assert db.execute("SELECT id FROM ui_automation_execution_runs WHERE id = 'uirun-1'").fetchone() is None


def test_delete_execution_run_rejects_active_run(monkeypatch, tmp_path: Path):
    _use_temp_db(monkeypatch, tmp_path)
    run_dir = _insert_execution_run(tmp_path, status="running")

    with pytest.raises(HTTPException) as exc_info:
        service.delete_execution_run("project-1", "uirun-1", ACTOR)

    assert exc_info.value.status_code == 409
    assert run_dir.exists()
    with core_db.connect() as db:
        assert db.execute("SELECT id FROM ui_automation_execution_runs WHERE id = 'uirun-1'").fetchone()


def test_init_db_migrates_legacy_ui_automation_source_columns(monkeypatch, tmp_path: Path):
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        db.executescript(
            """
            DROP TABLE ui_automation_execution_runs;
            DROP TABLE ui_automation_assets;
            DROP TABLE ui_automation_generation_runs;
            CREATE TABLE ui_automation_generation_runs (
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL, test_case_id TEXT NOT NULL,
              environment_id TEXT NOT NULL, exploration_run_id TEXT NOT NULL DEFAULT '',
              task_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'queued',
              suite_path TEXT NOT NULL DEFAULT '', changed_files_json TEXT NOT NULL DEFAULT '[]',
              error_message TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL,
              started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE ui_automation_assets (
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL, test_case_id TEXT NOT NULL,
              source_version INTEGER NOT NULL DEFAULT 1, generation_run_id TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'ready', pytest_node_id TEXT NOT NULL,
              suite_path TEXT NOT NULL, test_file_path TEXT NOT NULL, data_file_path TEXT NOT NULL,
              plan_file_path TEXT NOT NULL, source_hash TEXT NOT NULL, created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE ui_automation_execution_runs (
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL, asset_id TEXT NOT NULL,
              environment_id TEXT NOT NULL, task_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'queued',
              run_dir TEXT NOT NULL DEFAULT '', result_json TEXT NOT NULL DEFAULT '{}',
              stdout_path TEXT NOT NULL DEFAULT '', stderr_path TEXT NOT NULL DEFAULT '',
              trace_path TEXT NOT NULL DEFAULT '', screenshot_paths_json TEXT NOT NULL DEFAULT '[]',
              error_message TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL,
              started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    init_db()

    with core_db.connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(ui_automation_generation_runs)")}
        assert "manual_test_case_id" in columns
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='uq_ui_assets_manual_case'"
        ).fetchone()


def test_build_case_data_creates_derived_snapshot_without_mutating_source():
    source = {
        "id": "case-1",
        "project_id": "project-1",
        "title": "登录成功",
        "preconditions": "用户已注册",
        "steps_json": '[{"id":"step-1","action":"输入用户名"}]',
        "expected_result": "进入工作台",
        "status": "approved",
        "updated_at": "2026-07-23 10:00:00",
    }

    derived = context.build_case_data(source, automation_case_id="uiauto-1")
    derived["variables"] = {"username": {"source": "environment", "key": "UI_TEST_USERNAME"}}

    assert source.get("variables") is None
    assert derived["source_test_case"]["id"] == "case-1"
    assert derived["steps"][0]["id"] == "step-1"
    assert derived["expected_results"][0]["text"] == "进入工作台"


def test_build_case_data_extracts_parameterization_definition_from_step():
    source = {
        "id": "case-parameterized",
        "project_id": "project-1",
        "title": "按模型执行",
        "steps_json": (
            '[{"action":"选择目标模型 ${target_model}","value_ref":"target_model",'
            '"parameter":{"name":"target_model","type":"model","values":["qwen-plus"]}}]'
        ),
        "notes": "",
    }

    derived = context.build_case_data(source, automation_case_id="uiauto-parameterized")

    assert derived["parameters"]["target_model"]["values"] == ["qwen-plus"]
    assert derived["steps"][0]["value_ref"] == "target_model"


def test_write_case_data_uses_backend_owned_path(tmp_path: Path):
    data_path = tmp_path / "data/projects/project_1/cases/login.yaml"
    payload = {"schema_version": "v1", "variables": {}}

    artifact_storage.write_yaml_atomic(data_path, payload, suite_path=tmp_path)

    assert yaml.safe_load(data_path.read_text(encoding="utf-8")) == payload


def test_write_case_data_rejects_path_outside_suite(tmp_path: Path):
    outside = tmp_path.parent / "outside.yaml"

    try:
        artifact_storage.write_yaml_atomic(outside, {}, suite_path=tmp_path)
    except ValueError as exc:
        assert "工程目录" in str(exc)
    else:
        raise AssertionError("expected directory escape rejection")


def test_build_evidence_context_reads_only_selected_exploration_files(tmp_path: Path):
    page = tmp_path / "page-login.yaml"
    page.write_text("page:\n  title: 登录页\n  elements:\n    - name: 登录按钮\n", encoding="utf-8")
    ignored = tmp_path / "ignored.log"
    ignored.write_text("secret runtime log", encoding="utf-8")

    evidence = context.build_evidence_context(
        exploration_run_id="explore-1",
        artifact_rows=[
            {"artifact_type": "page", "file_path": str(page), "title": "登录页"},
            {"artifact_type": "log", "file_path": str(ignored), "title": "运行日志"},
        ],
    )

    assert evidence["exploration_run_id"] == "explore-1"
    assert evidence["artifacts"][0]["content"]["page"]["title"] == "登录页"
    assert len(evidence["artifacts"]) == 1
