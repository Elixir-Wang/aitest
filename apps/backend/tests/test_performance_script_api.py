from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core import db as db_core
from app.core import settings
from app.core.db import connect
from app.repositories import api_automation_repo
from app.schemas.performance_test import PerformanceTestCreateIn
from app.seed.init_db import init_db
from app.services.performance_testing import script_service, service


ADMIN = {"id": "u-admin", "role": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    monkeypatch.setattr(db_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_core, "DB_PATH", tmp_path / "test.db")
    init_db()


def _create_test(project_id: str = "project-1") -> dict:
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', 'u-admin')",
            (project_id, project_id),
        )
        api_automation_repo.upsert_endpoint(
            db,
            endpoint_id=f"endpoint-{project_id}",
            project_id=project_id,
            document_id=None,
            method="GET",
            path="/api/items",
            normalized_path="/api/items",
            summary="items",
            description="",
            tags=[],
            parameters=[],
            request_body={},
            responses={"200": {"description": "ok"}},
            auth={},
            source={},
            created_by="u-admin",
        )
        api_automation_repo.create_api_environment(
            db,
            environment_id=f"environment-{project_id}",
            project_id=project_id,
            linked_ui_environment_id=None,
            name="local",
            api_base_url="http://127.0.0.1:8000",
            username="",
            password_encrypted="",
            password_hash="",
            auth_type="none",
            auth_config={},
            variables={},
            default_headers={},
            timeout_seconds=10,
            verify_ssl=True,
            auth_state_ttl_seconds=3600,
            description="",
            created_by="u-admin",
        )
    return service.create_performance_test(
        project_id,
        PerformanceTestCreateIn(
            name="items performance",
            endpoint_id=f"endpoint-{project_id}",
            api_environment_id=f"environment-{project_id}",
        ),
        ADMIN,
    )


def test_script_generation_versions_and_confirmation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_test()

    first = script_service.generate_script("project-1", performance_test["id"], ADMIN)
    confirmed = script_service.confirm_script("project-1", performance_test["id"], first["id"], ADMIN)
    second = script_service.generate_script("project-1", performance_test["id"], ADMIN)

    assert first["version"] == 1
    assert first["validation_status"] == "pending_confirmation"
    assert confirmed["validation_status"] == "confirmed"
    assert confirmed["confirmed_by"] == "u-admin"
    assert second["version"] == 2
    assert [item["version"] for item in script_service.list_scripts("project-1", performance_test["id"], ADMIN)] == [2, 1]


def test_confirmed_script_is_immutable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_test()
    generated = script_service.generate_script("project-1", performance_test["id"], ADMIN)
    script_service.confirm_script("project-1", performance_test["id"], generated["id"], ADMIN)

    with pytest.raises(HTTPException) as exc_info:
        script_service.update_script_configuration(
            "project-1",
            performance_test["id"],
            generated["id"],
            {"request": {"headers": {"X-Test": "changed"}}},
            ADMIN,
        )

    assert exc_info.value.detail["code"] == "PERFORMANCE_SCRIPT_IMMUTABLE"


def test_pending_script_edit_rerenders_and_revalidates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_test()
    generated = script_service.generate_script("project-1", performance_test["id"], ADMIN)

    updated = script_service.update_script_configuration(
        "project-1",
        performance_test["id"],
        generated["id"],
        {"request": {"headers": {"X-Test": "changed"}, "body": {"name": "updated"}}},
        ADMIN,
    )

    assert updated["generation_source"] == "user_edited"
    assert updated["plan"]["request"]["headers"] == {"X-Test": "changed"}
    assert updated["validation_status"] == "pending_confirmation"
    assert updated["validation_result"]["valid"] is True
    assert "changed" in updated["code"]


def test_script_lookup_is_project_isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    performance_test = _create_test("project-1")
    _create_test("project-2")
    generated = script_service.generate_script("project-1", performance_test["id"], ADMIN)

    with pytest.raises(HTTPException) as exc_info:
        script_service.get_script("project-2", performance_test["id"], generated["id"], ADMIN)

    assert exc_info.value.status_code == 404
