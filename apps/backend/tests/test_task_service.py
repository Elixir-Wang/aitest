import pytest

from app.core import db as core_db
from app.seed.init_db import init_db
from app.services import task_service


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
        db.execute(
            """
            INSERT INTO knowledge_builds (id, project_id, build_no, status, created_by)
            VALUES ('kb-1', 'project-1', 'KB-001', 'building', 'u-admin')
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
        db.execute(
            """
            INSERT INTO requirement_merge_runs
              (id, project_id, document_id, merge_mode, status, created_by)
            VALUES ('merge-1', 'project-1', 'doc-1', 'initial', 'running', 'u-admin')
            """
        )

    tasks = task_service.list_running_tasks(ACTOR)

    assert [task["id"] for task in tasks] == ["requirement_merge:merge-1", "requirement_file:file-1", "knowledge:kb-1"]
    assert {task["status_group"] for task in tasks} == {"running"}
    assert tasks[1]["module_label"] == "需求标准化"
    assert tasks[0]["detail_url"] == "/projects/project-1/requirements/doc-1"


def test_list_tasks_can_filter_by_status_group(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        _seed_requirement_document(db)
        db.execute(
            """
            INSERT INTO requirement_merge_runs
              (id, project_id, document_id, merge_mode, status, created_by)
            VALUES ('merge-failed', 'project-1', 'doc-1', 'initial', 'failed', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO knowledge_builds (id, project_id, build_no, status, created_by)
            VALUES ('kb-done', 'project-1', 'KB-002', 'published', 'u-admin')
            """
        )

    result = task_service.list_tasks(ACTOR, status_group="failed")

    assert result["total"] == 1
    assert result["items"][0]["id"] == "requirement_merge:merge-failed"
    assert result["items"][0]["status_label"] == "归并失败"


def test_requirement_file_task_uses_file_mapping_timestamp(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
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
    assert result["items"][0]["updated_at"] == "2026-06-04 16:58:01"


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
    assert task_service.is_active_task_status("exploration_run", "completed") is False
