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


def test_create_api_environment_encrypts_password_and_cybertron_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    created = service.create_api_environment(
        "project-1",
        ApiEnvironmentIn(
            name="测试环境",
            api_base_url="https://api.example.test",
            username="tester",
            password="secret-password",
            auth_type="cybertron_agent",
            auth_config={
                "cybertron_robot_key": "plain-key",
                "cybertron_robot_token": "plain-token",
                "username": "robot-user",
            },
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
    assert "cybertron_robot_key" not in auth_config
    assert "cybertron_robot_token" not in auth_config
    assert auth_config["cybertron_robot_key_encrypted"] != "plain-key"
    assert auth_config["cybertron_robot_token_encrypted"] != "plain-token"
    assert decrypt_api_environment_secret(auth_config["cybertron_robot_key_encrypted"]) == "plain-key"
    assert decrypt_api_environment_secret(auth_config["cybertron_robot_token_encrypted"]) == "plain-token"
    assert auth_config["username"] == "robot-user"
    default_headers = api_automation_repo.loads_json(row["default_headers_json"], {})
    assert default_headers == {}


def test_list_api_environments_masks_sensitive_auth_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    service.create_api_environment(
        "project-1",
        ApiEnvironmentIn(
            name="测试环境",
            api_base_url="https://api.example.test",
            auth_type="cybertron_agent",
            auth_config={
                "cybertron_robot_key": "plain-key",
                "cybertron_robot_token": "plain-token",
                "username": "robot-user",
            },
        ),
        ACTOR,
    )

    environments = service.list_api_environments("project-1", ACTOR)

    assert environments[0]["auth_config"] == {
        "cybertron_robot_key_saved": True,
        "cybertron_robot_token_saved": True,
        "username": "robot-user",
    }
    assert environments[0]["default_headers"] == {}


def test_cybertron_environment_builds_runtime_headers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    created = service.create_api_environment(
        "project-1",
        ApiEnvironmentIn(
            name="测试环境",
            api_base_url="https://api.example.test",
            auth_type="cybertron_agent",
            auth_config={
                "cybertron_robot_key": "plain-key",
                "cybertron_robot_token": "plain-token",
                "username": "robot-user",
            },
        ),
        ACTOR,
    )

    with connect() as db:
        environment = service._build_debug_environment(db, "project-1", created["id"])

    assert "Content-Type" not in environment["headers"]
    assert environment["headers"]["cybertron-robot-key"] == "plain-key"
    assert environment["headers"]["cybertron-robot-token"] == "plain-token"
    assert environment["headers"]["username"] == "robot-user"


def test_update_api_environment_preserves_omitted_hidden_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    created = service.create_api_environment(
        "project-1",
        ApiEnvironmentIn(
            name="测试环境",
            api_base_url="https://api.example.test",
            variables={"tenant": "demo"},
            verify_ssl=False,
        ),
        ACTOR,
    )

    updated = service.update_api_environment(
        "project-1",
        created["id"],
        ApiEnvironmentIn(
            name="测试环境-改名",
            api_base_url="https://api.example.test",
            timeout_seconds=45,
        ),
        ACTOR,
    )

    assert updated["name"] == "测试环境-改名"
    assert updated["timeout_seconds"] == 45
    assert updated["variables"] == {"tenant": "demo"}
    assert updated["verify_ssl"] is False


def test_update_api_environment_preserves_omitted_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    created = service.create_api_environment(
        "project-1",
        ApiEnvironmentIn(
            name="测试环境",
            api_base_url="https://api.example.test",
            timeout_seconds=45,
        ),
        ACTOR,
    )

    updated = service.update_api_environment(
        "project-1",
        created["id"],
        ApiEnvironmentIn(
            name="测试环境-改名",
            api_base_url="https://api.example.test",
        ),
        ACTOR,
    )

    assert updated["name"] == "测试环境-改名"
    assert updated["timeout_seconds"] == 45


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


def test_api_environment_rejects_linked_ui_environment_from_another_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) "
            "VALUES ('project-2', '其他项目', '', 'active', ?)",
            (ACTOR["id"],),
        )
        db.execute(
            "INSERT INTO project_environments "
            "(id, project_id, name, site_url, created_by) "
            "VALUES ('env-other', 'project-2', '其他项目环境', 'https://other.test', ?)",
            (ACTOR["id"],),
        )

    with pytest.raises(HTTPException) as exc_info:
        service.create_api_environment(
            "project-1",
            ApiEnvironmentIn(
                name="测试环境",
                api_base_url="https://api.example.test",
                linked_ui_environment_id="env-other",
            ),
            ACTOR,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "UI_ENVIRONMENT_PROJECT_MISMATCH"
