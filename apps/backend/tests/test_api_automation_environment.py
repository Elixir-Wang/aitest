from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.core.environment_credentials import decrypt_api_environment_secret
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.schemas.api_automation import ApiEnvironmentIn
from app.services.api_automation import service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}
GUEST = {"id": "u-guest", "role": "guest", "nickname": "访客", "username": "guest", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    project_root = data_dir / "projects"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", project_root)
    monkeypatch.setattr(db_core, "DATA_DIR", data_dir)
    monkeypatch.setattr(db_core, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", project_root)
    init_db()


def _seed_project() -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
            ("project-1", "测试项目", ACTOR["id"]),
        )


def test_create_api_environment_encrypts_password_and_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    created = service.create_api_environment(
        "project-1",
        ApiEnvironmentIn(
            name="测试环境",
            api_base_url="https://api.example.test",
            username="tester",
            password="secret-password",
            auth_type="static_bearer",
            auth_config={"token": "plain-token"},
        ),
        ACTOR,
    )

    with connect() as db:
        row = api_automation_repo.find_api_environment(db, created["id"])

    assert created["username"] == "tester"
    assert "password" not in created
    assert row["password_encrypted"]
    assert row["password_encrypted"] != "secret-password"
    assert decrypt_api_environment_secret(row["password_encrypted"]) == "secret-password"
    auth_config = api_automation_repo.loads_json(row["auth_config_json"], {})
    assert "token" not in auth_config
    assert auth_config["token_encrypted"] != "plain-token"
    assert decrypt_api_environment_secret(auth_config["token_encrypted"]) == "plain-token"


def test_list_api_environments_masks_sensitive_auth_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    service.create_api_environment(
        "project-1",
        ApiEnvironmentIn(
            name="测试环境",
            api_base_url="https://api.example.test",
            auth_type="static_bearer",
            auth_config={"token": "plain-token"},
        ),
        ACTOR,
    )

    environments = service.list_api_environments("project-1", ACTOR)

    assert environments[0]["auth_config"] == {"token_saved": True}


def test_guest_cannot_create_api_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    with pytest.raises(HTTPException) as exc_info:
        service.create_api_environment(
            "project-1",
            ApiEnvironmentIn(name="测试环境", api_base_url="https://api.example.test"),
            GUEST,
        )

    assert exc_info.value.status_code == 403
