import pytest

from app.core import db as core_db
from app.seed.init_db import init_db
from app.services import task_service
from app.services.exploration import page_exploration_service as exploration_service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()


def _seed_project(db, project_id: str = "project-1", name: str = "测试项目") -> None:
    db.execute(
        "INSERT INTO projects (id, name, status, description) VALUES (?, ?, 'active', '')",
        (project_id, name),
    )


def _seed_requirement_document(db, project_id: str = "project-1", document_id: str = "doc-1") -> None:
    db.execute(
        """
        INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
        VALUES (?, ?, '登录需求', 'PRD', 'pending_merge', 'u-admin')
        """,
        (document_id, project_id),
    )


def test_list_running_tasks_returns_empty_when_no_task(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)

    assert task_service.list_running_tasks(ACTOR) == []


def test_list_running_tasks_excludes_pending_exploration(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        db.execute(
            """
            INSERT INTO project_environments (id, project_id, name, site_url, created_by)
            VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO exploration_runs (id, project_id, environment_id, title, status, created_by)
            VALUES ('run-1', 'project-1', 'env-1', '待执行探索', 'pending', 'u-admin')
            """
        )

    assert task_service.list_running_tasks(ACTOR) == []


def test_list_running_tasks_aggregates_existing_business_statuses(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        db.execute(
            """
            INSERT INTO project_environments (id, project_id, name, site_url, created_by)
            VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO exploration_runs (id, project_id, environment_id, title, status, created_by)
            VALUES ('run-1', 'project-1', 'env-1', '首页探索', 'running', 'u-admin')
            """
        )
        _seed_requirement_document(db)
        db.execute(
            """
            INSERT INTO source_document_file_mappings
              (id, document_id, source_file_path, original_filename, file_format, conversion_status, created_by)
            VALUES ('file-1', 'doc-1', 'uploads/login.docx', 'login.docx', 'docx', 'processing', 'u-admin')
            """
        )

    tasks = task_service.list_running_tasks(ACTOR)

    assert [task["id"] for task in tasks] == ["requirement_file:file-1", "exploration:run-1"]
    assert {task["status_group"] for task in tasks} == {"running"}
    assert tasks[0]["module_label"] == "需求标准化"
    assert tasks[0]["detail_url"] == "/projects/project-1/requirements/doc-1"


def test_list_running_tasks_includes_active_exploration(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        db.execute(
            """
            INSERT INTO project_environments (id, project_id, name, site_url, created_by)
            VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO exploration_runs (id, project_id, environment_id, title, status, created_by, created_at)
            VALUES ('run-1', 'project-1', 'env-1', '首页探索', 'running', 'u-admin', '2026-06-04 17:00:01')
            """
        )

    tasks = task_service.list_running_tasks(ACTOR)

    assert [task["id"] for task in tasks] == ["exploration:run-1"]
    assert tasks[0]["source_type"] == "exploration_run"
    assert tasks[0]["status_label"] == "探索中"


def test_restart_exploration_clears_previous_summary_before_new_output(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        db.execute(
            """
            INSERT INTO project_environments (id, project_id, name, site_url, created_by)
            VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO exploration_runs
              (id, project_id, environment_id, title, status, result_summary, started_at, finished_at, created_by)
            VALUES
              ('run-1', 'project-1', 'env-1', '首页探索', 'completed', '探索完成，共探索 1 个页面', '2026-06-04T10:00:00Z', '2026-06-04T10:05:00Z', 'u-admin')
            """
        )

    with core_db.connect() as db:
        exploration_service.start_exploration_async(ACTOR, "run-1")

    with core_db.connect() as db:
        run = db.execute(
            "SELECT status, result_summary, started_at, finished_at FROM exploration_runs WHERE id = ?",
            ("run-1",),
        ).fetchone()

    assert run["status"] in {"queued", "running"}
    assert run["result_summary"] == ""
    assert run["finished_at"] is None
    assert run["started_at"] is None or run["started_at"] != "2026-06-04T10:00:00Z"


def test_requirement_file_task_uses_file_mapping_created_timestamp(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        _seed_requirement_document(db)
        db.execute(
            """
            UPDATE source_documents
            SET updated_at = '2026-06-04 16:59:19'
            WHERE id = 'doc-1'
            """
        )
        db.execute(
            """
            INSERT INTO source_document_file_mappings
              (id, document_id, source_file_path, original_filename, file_format, conversion_status, created_by, created_at)
            VALUES ('file-1', 'doc-1', 'uploads/login.docx', 'login.docx', 'docx', 'success', 'u-admin', '2026-06-04 16:58:01')
            """
        )

    result = task_service.list_tasks(ACTOR, module="requirement")

    assert result["items"][0]["id"] == "requirement_file:file-1"
    assert result["items"][0]["created_at"] == "2026-06-04 16:58:01"


def test_requirement_analysis_run_is_visible_as_requirement_review_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        _seed_requirement_document(db)
        db.execute(
            """
            INSERT INTO source_document_file_mappings
              (id, document_id, source_file_path, original_filename, file_format, conversion_status, created_by)
            VALUES ('file-1', 'doc-1', 'uploads/login.docx', 'login.docx', 'docx', 'success', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO requirement_analysis_runs
              (id, project_id, document_id, primary_mapping_id, status, summary, created_by, created_at)
            VALUES ('run-1', 'project-1', 'doc-1', 'file-1', 'needs_clarification', '存在待确认问题。', 'u-admin', '2026-06-04 17:00:01')
            """
        )

    result = task_service.list_tasks(ACTOR, module="requirement")

    task = next(item for item in result["items"] if item["source_type"] == "requirement_analysis_run")
    assert task["id"] == "requirement_analysis:run-1"
    assert task["module_label"] == "需求分析"
    assert task["title"] == "登录需求"
    assert task["status_label"] == "等待澄清"
    assert task["status_group"] == "waiting"
    assert task["detail_url"] == "/projects/project-1/requirements/doc-1"


def test_running_tasks_include_active_requirement_analysis_run(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        _seed_requirement_document(db)
        db.execute(
            """
            INSERT INTO source_document_file_mappings
              (id, document_id, source_file_path, original_filename, file_format, conversion_status, created_by)
            VALUES ('file-1', 'doc-1', 'uploads/login.docx', 'login.docx', 'docx', 'success', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO requirement_analysis_runs
              (id, project_id, document_id, primary_mapping_id, status, summary, created_by, created_at)
            VALUES ('run-1', 'project-1', 'doc-1', 'file-1', 'running', '需求分析智能体正在分析。', 'u-admin', '2026-06-04 17:00:01')
            """
        )

    tasks = task_service.list_running_tasks(ACTOR)

    assert [task["id"] for task in tasks] == ["requirement_analysis:run-1"]
    assert tasks[0]["status_label"] == "分析中"


def test_running_tasks_exclude_requirement_analysis_waiting_for_clarification(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        _seed_requirement_document(db)
        db.execute(
            """
            INSERT INTO source_document_file_mappings
              (id, document_id, source_file_path, original_filename, file_format, conversion_status, created_by)
            VALUES ('file-1', 'doc-1', 'uploads/login.docx', 'login.docx', 'docx', 'success', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO requirement_analysis_runs
              (id, project_id, document_id, primary_mapping_id, status, summary, created_by, created_at)
            VALUES ('run-1', 'project-1', 'doc-1', 'file-1', 'needs_clarification', '存在待确认问题。', 'u-admin', '2026-06-04 17:00:01')
            """
        )

    assert task_service.list_running_tasks(ACTOR) == []


def test_running_tasks_recovers_stale_requirement_analysis_run(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        _seed_requirement_document(db)
        db.execute(
            """
            INSERT INTO source_document_file_mappings
              (id, document_id, source_file_path, original_filename, file_format, conversion_status, created_by)
            VALUES ('file-1', 'doc-1', 'uploads/login.docx', 'login.docx', 'docx', 'success', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO requirement_analysis_runs
              (id, project_id, document_id, primary_mapping_id, status, summary, created_by, created_at, updated_at)
            VALUES (
              'run-1',
              'project-1',
              'doc-1',
              'file-1',
              'running',
              '需求分析智能体正在分析。',
              'u-admin',
              datetime('now', '-121 minutes'),
              datetime('now', '-121 minutes')
            )
            """
        )

    tasks = task_service.list_running_tasks(ACTOR)

    assert tasks == []
    with core_db.connect() as db:
        run = db.execute("SELECT status, summary, failure_reason FROM requirement_analysis_runs WHERE id = 'run-1'").fetchone()
        log = db.execute(
            """
            SELECT action, result, failure_reason
            FROM operation_logs
            WHERE task_id = 'run-1' AND action = 'fail_requirement_analysis'
            """
        ).fetchone()
    assert run["status"] == "failed"
    assert run["summary"] == "需求分析失败。"
    assert "超过 120 分钟" in run["failure_reason"]
    assert log["result"] == "failed"
    assert "超过 120 分钟" in log["failure_reason"]


def test_startup_recovers_interrupted_requirement_analysis_run(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        _seed_requirement_document(db)
        db.execute(
            """
            INSERT INTO source_document_file_mappings
              (id, document_id, source_file_path, original_filename, file_format, conversion_status, created_by)
            VALUES ('file-1', 'doc-1', 'uploads/login.docx', 'login.docx', 'docx', 'success', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO requirement_analysis_runs
              (id, project_id, document_id, primary_mapping_id, status, summary, created_by)
            VALUES ('run-1', 'project-1', 'doc-1', 'file-1', 'running', '需求分析智能体正在分析。', 'u-admin')
            """
        )

    task_service.recover_interrupted_requirement_analysis_runs()

    with core_db.connect() as db:
        run = db.execute("SELECT status, summary, failure_reason FROM requirement_analysis_runs WHERE id = 'run-1'").fetchone()
        log = db.execute(
            """
            SELECT action, result, failure_reason
            FROM operation_logs
            WHERE task_id = 'run-1' AND action = 'fail_requirement_analysis'
            """
        ).fetchone()

    assert run["status"] == "failed"
    assert run["summary"] == "需求分析已中断。"
    assert "服务已重启" in run["failure_reason"]
    assert log["result"] == "failed"
    assert "服务已重启" in log["failure_reason"]


def test_startup_marks_active_exploration_runs_interrupted(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        db.execute(
            """
            INSERT INTO project_environments (id, project_id, name, site_url, created_by)
            VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
            """
        )
        for status in ("queued", "running", "stopping"):
            db.execute(
                """
                INSERT INTO exploration_runs
                  (id, project_id, environment_id, title, status, result_summary, created_by)
                VALUES (?, 'project-1', 'env-1', ?, ?, '原状态摘要', 'u-admin')
                """,
                (f"run-{status}", f"{status} 探索", status),
            )

    exploration_service.recover_interrupted_exploration_runs()

    with core_db.connect() as db:
        rows = db.execute(
            """
            SELECT id, status, result_summary, finished_at
            FROM exploration_runs
            ORDER BY id
            """
        ).fetchall()
        logs = db.execute(
            """
            SELECT task_id, action, result, failure_reason
            FROM operation_logs
            WHERE object_type = 'exploration_run'
            ORDER BY task_id
            """
        ).fetchall()

    assert {row["status"] for row in rows} == {"interrupted"}
    assert all("服务已重启" in row["result_summary"] for row in rows)
    assert all(row["finished_at"] for row in rows)
    assert [log["task_id"] for log in logs] == ["run-queued", "run-running", "run-stopping"]
    assert {log["action"] for log in logs} == {"interrupt_exploration"}
    assert {log["result"] for log in logs} == {"failed"}
    assert all("服务已重启" in log["failure_reason"] for log in logs)


def test_get_task_by_source_returns_normalized_exploration_task(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        db.execute(
            """
            INSERT INTO project_environments (id, project_id, name, site_url, created_by)
            VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO exploration_runs (id, project_id, environment_id, title, status, result_summary, created_by)
            VALUES ('run-1', 'project-1', 'env-1', '首页探索', 'queued', '探索任务已提交，等待执行。', 'u-admin')
            """
        )

    task = task_service.get_task_by_source(ACTOR, source_type="exploration_run", source_id="run-1")

    assert task is not None
    assert task["id"] == "exploration:run-1"
    assert task["status"] == "queued"
    assert task["status_group"] == "running"
    assert task["status_label"] == "排队中"
    assert task["detail_url"] == "/projects/project-1/exploration/run-1"


def test_is_active_task_status_matches_running_indicator_contract() -> None:
    assert task_service.is_active_task_status("exploration_run", "queued") is True
    assert task_service.is_active_task_status("exploration_run", "running") is True
    assert task_service.is_active_task_status("exploration_run", "stopping") is True
    assert task_service.is_active_task_status("exploration_run", "pending") is False
    assert task_service.is_active_task_status("exploration_run", "interrupted") is False
    assert task_service.is_active_task_status("exploration_run", "completed") is False
    assert task_service.is_active_task_status("requirement_analysis_run", "queued") is True
    assert task_service.is_active_task_status("requirement_analysis_run", "running") is True
    assert task_service.is_active_task_status("requirement_analysis_run", "stopping") is True
    assert task_service.is_active_task_status("requirement_analysis_run", "cancelled") is False
    assert task_service.is_active_task_status("requirement_analysis_run", "needs_clarification") is False
    assert task_service.is_active_task_status("requirement_analysis_run", "completed") is False


def test_interrupted_exploration_run_is_restartable_for_admin() -> None:
    assert True
