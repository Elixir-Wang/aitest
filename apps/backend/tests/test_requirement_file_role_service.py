import asyncio
import pytest
from fastapi import UploadFile

from app.core import db as core_db
from app.core import storage as core_storage
from app.seed.init_db import init_db
from app.services.document import file_service


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
    init_db()


def _seed_project_and_document(project_id: str = "project-role", document_id: str = "doc-role") -> None:
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
            INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
            VALUES (?, ?, '角色需求', 'PRD', 'pending_merge', ?)
            """,
            (document_id, project_id, ACTOR["id"]),
        )


def _upload_file(filename: str, content: bytes = b"# requirement\n") -> UploadFile:
    return UploadFile(filename=filename, file=__import__("io").BytesIO(content))


def test_append_to_empty_requirement_marks_uploaded_file_as_primary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_document()

    result = asyncio.run(file_service.append_document_files("project-role", "doc-role", [_upload_file("new-main.md")], ACTOR))

    assert [item["file_role"] for item in result["files"]] == ["primary"]
    with core_db.connect() as db:
        row = db.execute("SELECT file_role FROM source_document_file_mappings WHERE document_id = ?", ("doc-role",)).fetchone()
    assert row["file_role"] == "primary"


def test_single_file_requirement_stays_parsing_until_standard_file_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_document()
    result = asyncio.run(file_service.append_document_files("project-role", "doc-role", [_upload_file("main.md")], ACTOR))
    mapping_id = result["files"][0]["id"]

    with core_db.connect() as db:
        row = db.execute("SELECT status FROM source_documents WHERE id = ?", ("doc-role",)).fetchone()
        assert row["status"] == "parsing"

        db.execute(
            """
            UPDATE source_document_file_mappings
            SET conversion_status = 'success',
                markdown_file_path = 'project-role/requirements/doc-role/standard/main.md'
            WHERE id = ?
            """,
            (mapping_id,),
        )
        file_service.sync_document_status(db, "doc-role")
        row = db.execute("SELECT status FROM source_documents WHERE id = ?", ("doc-role",)).fetchone()

    assert row["status"] == "pending_review"


def test_deleting_primary_promotes_remaining_single_file_to_primary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_document()
    result = asyncio.run(
        file_service.append_document_files(
            "project-role",
            "doc-role",
            [_upload_file("main.md"), _upload_file("supporting.md")],
            ACTOR,
        )
    )
    primary_file = next(item for item in result["files"] if item["file_role"] == "primary")

    file_service.delete_source_file(primary_file["id"], ACTOR)

    with core_db.connect() as db:
        rows = db.execute(
            "SELECT original_filename, file_role FROM source_document_file_mappings WHERE document_id = ?",
            ("doc-role",),
        ).fetchall()
    assert [(row["original_filename"], row["file_role"]) for row in rows] == [("supporting.md", "primary")]
