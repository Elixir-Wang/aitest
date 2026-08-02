import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.repositories import document_repo, project_repo
from app.schemas.project import ProjectCreateIn
from app.schemas.project_version import ProjectVersionCreateIn
from app.seed.init_db import init_db
from app.seed.seeds import seed_system_defaults
from app.services import project_service, project_version_service
from app.services.document import documents as document_service


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
    init_db()


def test_project_creation_bootstraps_version(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)

    project = project_service.create_project(ProjectCreateIn(name="版本项目"), ACTOR)

    assert project["current_version"]["version"] == "1.0.0"
    versions = project_version_service.list_versions(project["id"], ACTOR)
    assert [(item["version"], item["is_default"]) for item in versions] == [("1.0.0", True)]


def test_new_version_becomes_default_and_duplicate_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    project = project_service.create_project(ProjectCreateIn(name="版本切换项目"), ACTOR)

    created = project_version_service.create_version(
        project["id"],
        ProjectVersionCreateIn(version="1.10.0", name="能力升级"),
        ACTOR,
    )

    assert created["is_default"] is True
    versions = project_version_service.list_versions(project["id"], ACTOR)
    assert [item["version"] for item in versions] == ["1.10.0", "1.0.0"]
    with pytest.raises(HTTPException) as caught:
        project_version_service.create_version(
            project["id"],
            ProjectVersionCreateIn(version="1.10.0"),
            ACTOR,
        )
    assert caught.value.detail["code"] == "PROJECT_VERSION_EXISTS"


def test_requirement_uses_default_version_and_protects_delete(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    project = project_service.create_project(ProjectCreateIn(name="需求版本项目"), ACTOR)
    version = project_version_service.create_version(
        project["id"],
        ProjectVersionCreateIn(version="1.1.0"),
        ACTOR,
    )

    with core_db.connect() as db:
        resolved = project_version_service.resolve_requirement_version(db, project["id"])
        assert resolved["id"] == version["id"]
        document_repo.create_document(
            db,
            document_id="doc-versioned",
            project_id=project["id"],
            project_version_id=version["id"],
            name="版本需求",
            document_type="PRD",
            status="pending_merge",
            created_by=ACTOR["id"],
        )

    with pytest.raises(HTTPException) as caught:
        project_version_service.delete_version(project["id"], version["id"], ACTOR)
    assert caught.value.detail["code"] == "PROJECT_VERSION_IS_DEFAULT"


def test_legacy_migration_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        project_repo.create(db, project_id="project-legacy", name="存量项目", status="active", description="")
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
            VALUES ('doc-legacy', 'project-legacy', '存量需求', 'PRD', 'pending_merge', 'u-admin')
            """
        )
        seed_system_defaults(db)
        seed_system_defaults(db)
        versions = db.execute(
            "SELECT id FROM project_versions WHERE project_id = 'project-legacy' AND version = '1.0.0'"
        ).fetchall()
        project = db.execute("SELECT default_version_id FROM projects WHERE id = 'project-legacy'").fetchone()
        document = db.execute(
            "SELECT project_version_id FROM source_documents WHERE id = 'doc-legacy'"
        ).fetchone()

    assert len(versions) == 1
    assert project["default_version_id"] == versions[0]["id"]
    assert document["project_version_id"] == versions[0]["id"]


def test_invalid_version_format_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    project = project_service.create_project(ProjectCreateIn(name="格式项目"), ACTOR)

    with pytest.raises(HTTPException) as caught:
        project_version_service.create_version(
            project["id"],
            ProjectVersionCreateIn(version="v1.0.0"),
            ACTOR,
        )

    assert caught.value.detail["code"] == "PROJECT_VERSION_INVALID"


def test_requirement_can_be_reassigned_by_project_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    project = project_service.create_project(ProjectCreateIn(name="筛选项目"), ACTOR)
    initial = project_version_service.list_versions(project["id"], ACTOR)[0]
    next_version = project_version_service.create_version(
        project["id"],
        ProjectVersionCreateIn(version="1.1.0"),
        ACTOR,
    )
    with core_db.connect() as db:
        document_repo.create_document(
            db,
            document_id="doc-filter",
            project_id=project["id"],
            project_version_id=initial["id"],
            name="筛选需求",
            document_type="PRD",
            status="pending_merge",
            created_by=ACTOR["id"],
        )

    updated = document_service.update_document_project_version(
        project["id"],
        "doc-filter",
        next_version["id"],
        ACTOR,
    )

    assert updated["document"]["project_version"]["version"] == "1.1.0"
    documents = document_service.list_documents(project["id"], ACTOR)
    assert len(documents) == 1
    assert documents[0]["project_version"]["version"] == "1.1.0"
