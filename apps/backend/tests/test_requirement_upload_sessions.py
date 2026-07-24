from __future__ import annotations

import asyncio
import hashlib
import io

import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.api.v1.requirements import uploads as upload_routes
from app.core import db as core_db
from app.core import settings
from app.core import storage as core_storage
from app.schemas.requirement_upload import RequirementUploadSessionCreateIn
from app.seed.init_db import init_db
from app.services.document import file_service, upload_sessions


ACTOR = {
    "id": "u-admin",
    "role": "admin",
    "nickname": "平台管理员",
    "username": "admin",
    "project_scope": "全部项目",
}


def _use_temp_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(core_storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "REQUIREMENT_UPLOAD_CHUNK_SIZE_BYTES", 4)
    monkeypatch.setattr(settings, "REQUIREMENT_UPLOAD_MAX_FILE_SIZE_BYTES", 20)
    monkeypatch.setattr(settings, "REQUIREMENT_UPLOAD_MAX_BATCH_SIZE_BYTES", 200)
    monkeypatch.setattr(settings, "REQUIREMENT_UPLOAD_MAX_FILES", 10)
    monkeypatch.setattr(settings, "REQUIREMENT_UPLOAD_CONCURRENCY", 3)
    monkeypatch.setattr(settings, "REQUIREMENT_UPLOAD_MAX_ACTIVE_SESSIONS_PER_USER", 2)
    monkeypatch.setattr(settings, "REQUIREMENT_UPLOAD_SESSION_TTL_HOURS", 24)
    init_db()
    with core_db.connect() as db:
        db.execute("INSERT INTO projects (id, name, status, description) VALUES ('project-upload', '上传项目', 'active', '')")


def _payload(content: bytes, *, filename: str = "requirement.md") -> RequirementUploadSessionCreateIn:
    return RequirementUploadSessionCreateIn(
        mode="new",
        document_name="上传需求",
        files=[
            {
                "filename": filename,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ],
    )


async def _stream(content: bytes):
    yield content


def test_session_upload_can_resume_and_complete(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_storage(monkeypatch, tmp_path)
    content = b"# hello"
    session = upload_sessions.create_session("project-upload", _payload(content), ACTOR)
    session_file = session["files"][0]

    asyncio.run(
        upload_sessions.save_chunk(
            "project-upload",
            session["id"],
            session_file["id"],
            0,
            _stream(content[:4]),
            ACTOR,
            expected_sha256=hashlib.sha256(content[:4]).hexdigest(),
        )
    )
    resumed = upload_sessions.get_session("project-upload", session["id"], ACTOR)
    assert resumed["files"][0]["uploaded_parts"] == [0]

    asyncio.run(
        upload_sessions.save_chunk(
            "project-upload",
            session["id"],
            session_file["id"],
            1,
            _stream(content[4:]),
            ACTOR,
            expected_sha256=hashlib.sha256(content[4:]).hexdigest(),
        )
    )
    result = asyncio.run(upload_sessions.complete_session("project-upload", session["id"], ACTOR))

    assert result["_upload_mode"] == "new"
    assert result["files"][0]["original_filename"] == "requirement.md"
    with core_db.connect() as db:
        mapping = db.execute("SELECT source_file_path FROM source_document_file_mappings").fetchone()
    stored_path = core_storage.resolve_stored_path(mapping["source_file_path"])
    assert stored_path.read_bytes() == content
    with pytest.raises(HTTPException) as caught:
        upload_sessions.get_session("project-upload", session["id"], ACTOR)
    assert caught.value.status_code == 404


def test_session_rejects_file_over_limit_and_too_many_files(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "REQUIREMENT_UPLOAD_MAX_FILE_SIZE_BYTES", 5)
    with pytest.raises(HTTPException) as oversized:
        upload_sessions.create_session("project-upload", _payload(b"123456"), ACTOR)
    assert oversized.value.status_code == 413
    assert oversized.value.detail["code"] == "UPLOAD_FILE_TOO_LARGE"

    files = [{"filename": f"file-{index}.md", "size": 1} for index in range(11)]
    with pytest.raises(HTTPException) as too_many:
        upload_sessions.create_session(
            "project-upload",
            RequirementUploadSessionCreateIn(mode="new", document_name="批量需求", files=files),
            ACTOR,
        )
    assert too_many.value.status_code == 422
    assert too_many.value.detail["code"] == "UPLOAD_FILE_COUNT_EXCEEDED"


def test_chunk_hash_mismatch_is_not_recorded(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_storage(monkeypatch, tmp_path)
    content = b"hash"
    session = upload_sessions.create_session("project-upload", _payload(content), ACTOR)
    session_file = session["files"][0]

    with pytest.raises(HTTPException) as caught:
        asyncio.run(
            upload_sessions.save_chunk(
                "project-upload",
                session["id"],
                session_file["id"],
                0,
                _stream(content),
                ACTOR,
                expected_sha256="0" * 64,
            )
        )
    assert caught.value.status_code == 409
    assert upload_sessions.get_session("project-upload", session["id"], ACTOR)["files"][0]["uploaded_parts"] == []


def test_legacy_multipart_upload_enforces_streamed_size_limit(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "REQUIREMENT_UPLOAD_MAX_FILE_SIZE_BYTES", 5)
    upload = UploadFile(filename="too-large.md", file=io.BytesIO(b"123456"))

    with pytest.raises(HTTPException) as caught:
        asyncio.run(
            file_service.upload_documents(
                "project-upload",
                [upload],
                ACTOR,
                mode="new",
                document_name="不可绕过限制",
            )
        )
    assert caught.value.status_code == 413
    with core_db.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM source_documents WHERE name = '不可绕过限制'").fetchone()[0] == 0


def test_upload_routes_accept_raw_chunks_and_report_resume_state(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_storage(monkeypatch, tmp_path)
    app = FastAPI()
    app.include_router(upload_routes.router, prefix="/api/v1")
    app.dependency_overrides[upload_routes.current_user] = lambda: ACTOR
    content = b"route"

    with TestClient(app) as client:
        config_response = client.get("/api/v1/projects/project-upload/requirements/upload-config")
        assert config_response.status_code == 200
        assert config_response.json()["concurrency"] == 3

        create_response = client.post(
            "/api/v1/projects/project-upload/requirements/upload-sessions",
            json={
                "mode": "new",
                "document_name": "路由上传需求",
                "files": [{"filename": "route.md", "size": len(content)}],
            },
        )
        assert create_response.status_code == 200
        session = create_response.json()
        session_file = session["files"][0]
        part_response = client.put(
            f"/api/v1/projects/project-upload/requirements/upload-sessions/{session['id']}"
            f"/files/{session_file['id']}/parts/0",
            content=content[:4],
            headers={"X-Chunk-SHA256": hashlib.sha256(content[:4]).hexdigest()},
        )
        assert part_response.status_code == 200

        status_response = client.get(
            f"/api/v1/projects/project-upload/requirements/upload-sessions/{session['id']}"
        )
        assert status_response.json()["files"][0]["uploaded_parts"] == [0]

        cancel_response = client.delete(
            f"/api/v1/projects/project-upload/requirements/upload-sessions/{session['id']}"
        )
        assert cancel_response.status_code == 200
