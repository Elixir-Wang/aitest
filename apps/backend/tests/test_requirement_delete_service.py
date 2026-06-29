import sqlite3

import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.core import storage as core_storage
from app.seed.init_db import init_db
from app.services.document import service as document_service


ACTOR = {
    "id": "u-admin",
    "role": "admin",
    "nickname": "平台管理员",
    "username": "admin",
    "project_scope": "全部项目",
}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(core_storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    monkeypatch.setattr(document_service, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects", raising=False)
    init_db()


def _insert_requirement_document(project_id: str, document_id: str, version_id: str) -> None:
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, status, description)
            VALUES (?, ?, 'active', '')
            """,
            (project_id, project_id),
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES (?, ?, '待删需求', 'requirement', ?, 'versioned', ?)
            """,
            (document_id, project_id, version_id, ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO source_document_versions (
                id, document_id, version_no, markdown_content, file_path, source_action, created_by
            )
            VALUES (?, ?, 'v1', '# 待删需求', '', 'upload', ?)
            """,
            (version_id, document_id, ACTOR["id"]),
        )


def test_delete_document_reports_file_cleanup_failure_with_business_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    project_id = "project-delete-cleanup"
    document_id = "doc-delete-cleanup"
    version_id = "docver-delete-cleanup"
    _insert_requirement_document(project_id, document_id, version_id)
    document_dir = core_storage.project_requirement_dir(project_id, document_id)
    document_dir.mkdir(parents=True)
    (document_dir / "versions").mkdir()

    def fail_rmtree(_path):
        raise OSError("permission denied")

    monkeypatch.setattr(document_service.shutil, "rmtree", fail_rmtree)

    with pytest.raises(HTTPException) as exc_info:
        document_service.delete_document(project_id, document_id, ACTOR)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail["code"] == "DOCUMENT_FILE_DELETE_FAILED"
    assert "需求文档数据已删除" in exc_info.value.detail["message"]
    assert document_dir.exists()


def test_delete_document_rejects_requirement_linked_to_test_case_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    project_id = "project-delete-linked"
    document_id = "doc-delete-linked"
    version_id = "docver-delete-linked"
    _insert_requirement_document(project_id, document_id, version_id)
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO test_case_sets (
                id, project_id, name, requirement_doc_id, generation_scope_type, status, created_by
            )
            VALUES (?, ?, ?, ?, 'all', 'failed', ?)
            """,
            ("tcs-delete-linked", project_id, "关联测试用例集", document_id, ACTOR["id"]),
        )

    with pytest.raises(HTTPException) as exc_info:
        document_service.delete_document(project_id, document_id, ACTOR)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "DOCUMENT_HAS_TEST_CASE_SETS"
    assert "关联测试用例集" in exc_info.value.detail["message"]
    with core_db.connect() as db:
        assert db.execute("SELECT id FROM source_documents WHERE id = ?", (document_id,)).fetchone() is not None
