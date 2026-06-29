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


def test_list_tasks_orders_by_updated_time_desc(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description) VALUES ('project-1', '测试项目', 'active', '')"
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
            VALUES ('doc-1', 'project-1', '登录需求', 'PRD', 'pending_merge', 'u-admin')
            """
        )
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
            VALUES
              ('run-old-created-new-updated', 'project-1', 'doc-1', 'file-1', 'needs_clarification',
               '等待澄清。', 'u-admin', '2026-06-04 10:00:00', '2026-06-04 15:00:00'),
              ('run-new-created-old-updated', 'project-1', 'doc-1', 'file-1', 'completed',
               '已完成。', 'u-admin', '2026-06-04 14:00:00', '2026-06-04 14:30:00')
            """
        )

    result = task_service.list_tasks(ACTOR, module="requirement")

    analysis_task_ids = [
        item["source_id"]
        for item in result["items"]
        if item["source_type"] == "requirement_analysis_run"
    ]
    assert analysis_task_ids == ["run-old-created-new-updated", "run-new-created-old-updated"]
