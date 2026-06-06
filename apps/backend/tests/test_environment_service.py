import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.core import environment_auth_state
from app.schemas.environment import ProjectEnvironmentCreateIn, ProjectEnvironmentUpdateIn
from app.seed.init_db import init_db
from app.services import environment_service, manual_auth_service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}
FUTURE_EXPIRES = 4102444800
PAST_EXPIRES = 946684800
FUTURE_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJleHAiOjQxMDI0NDQ4MDAsImlhdCI6OTQ2Njg0ODAwLCJ1c2VyX2lkIjoxfQ."
    "signature"
)


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(environment_auth_state.settings, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    init_db()


def _seed_project(project_id: str = "project-1") -> None:
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description) VALUES (?, '测试项目', 'active', '')",
            (project_id,),
        )


def test_create_skip_login_normalizes_captcha_and_auth_state(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    result = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="无需登录环境",
            site_url="https://example.test",
            username="admin",
            password="secret123",
            login_strategy="skip_login",
            captcha_strategy="ai_letter",
            reuse_auth_state=True,
        ),
        ACTOR,
    )

    assert result["login_strategy"] == "skip_login"
    assert result["username"] == ""
    assert result["password_mask"] == ""
    assert result["captcha_strategy"] == "none"
    assert result["reuse_auth_state"] is False
    assert result["auth_state_status"] == "none"


def test_create_account_password_defaults_reuse_auth_state(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    result = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="账号密码环境",
            site_url="https://example.test",
            username="admin",
            password="secret123",
            login_strategy="account_password",
        ),
        ACTOR,
    )

    assert result["login_strategy"] == "account_password"
    assert result["username"] == "admin"
    assert result["password_mask"] == "s*******3"
    assert result["captcha_strategy"] == "none"
    assert result["reuse_auth_state"] is True
    assert result["auth_state_status"] == "none"


def test_manual_captcha_requires_reuse_auth_state(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    with pytest.raises(HTTPException) as exc_info:
        environment_service.create_project_environment(
            "project-1",
            ProjectEnvironmentCreateIn(
                name="人工验证码环境",
                site_url="https://example.test",
                username="admin",
                password="secret123",
                login_strategy="account_password",
                captcha_strategy="manual",
                reuse_auth_state=False,
            ),
            ACTOR,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "INVALID_CAPTCHA_STRATEGY"
    assert exc_info.value.detail["message"] == "人工登录必须开启复用登录态。"


def test_legacy_manual_login_strategy_maps_to_account_password_manual(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    result = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="旧人工登录环境",
            site_url="https://example.test",
            username="admin",
            password="secret123",
            login_strategy="manual",
        ),
        ACTOR,
    )

    assert result["login_strategy"] == "account_password"
    assert result["captcha_strategy"] == "manual"
    assert result["reuse_auth_state"] is True


def test_update_skip_login_clears_login_fields(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    created = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="账号密码环境",
            site_url="https://example.test",
            username="admin",
            password="secret123",
            login_strategy="account_password",
            captcha_strategy="manual",
        ),
        ACTOR,
    )

    updated = environment_service.update_project_environment(
        "project-1",
        created["id"],
        ProjectEnvironmentUpdateIn(login_strategy="skip_login"),
        ACTOR,
    )

    assert updated["login_strategy"] == "skip_login"
    assert updated["username"] == ""
    assert updated["password_mask"] == ""
    assert updated["captcha_strategy"] == "none"
    assert updated["reuse_auth_state"] is False


def test_auth_state_status_is_valid_when_cookie_expires_in_future(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    created = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="人工验证码环境",
            site_url="https://example.test",
            username="admin",
            password="secret123",
            login_strategy="account_password",
            captcha_strategy="manual",
            reuse_auth_state=True,
        ),
        ACTOR,
    )
    state_path = environment_auth_state.auth_state_path("project-1", created["id"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        f'{{"cookies":[{{"name":"sid","value":"secret","domain":"example.test","path":"/","expires":{FUTURE_EXPIRES}}}],"origins":[]}}',
        encoding="utf-8",
    )

    result = environment_service.list_project_environments("project-1", ACTOR)[0]

    assert result["auth_state_status"] == "valid"
    assert result["auth_state_expires_at"] == "2100-01-01T00:00:00+00:00"


def test_auth_state_status_is_expired_when_cookie_expires_in_past(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    created = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="人工验证码环境",
            site_url="https://example.test",
            username="admin",
            password="secret123",
            login_strategy="account_password",
            captcha_strategy="manual",
            reuse_auth_state=True,
        ),
        ACTOR,
    )
    state_path = environment_auth_state.auth_state_path("project-1", created["id"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        f'{{"cookies":[{{"name":"sid","value":"secret","domain":"example.test","path":"/","expires":{PAST_EXPIRES}}}],"origins":[]}}',
        encoding="utf-8",
    )

    result = environment_service.list_project_environments("project-1", ACTOR)[0]

    assert result["auth_state_status"] == "expired"
    assert result["auth_state_expires_at"] == "2000-01-01T00:00:00+00:00"


def test_auth_state_status_reads_jwt_exp_from_local_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    created = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="人工验证码环境",
            site_url="https://example.test",
            username="admin",
            password="secret123",
            login_strategy="account_password",
            captcha_strategy="manual",
            reuse_auth_state=True,
        ),
        ACTOR,
    )
    state_path = environment_auth_state.auth_state_path("project-1", created["id"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        (
            '{"cookies":[],"origins":[{"origin":"https://example.test","localStorage":'
            f'[{{"name":"sbtToken","value":"{FUTURE_JWT}"}}]}}]'
            "}"
        ),
        encoding="utf-8",
    )

    result = environment_service.list_project_environments("project-1", ACTOR)[0]

    assert result["auth_state_status"] == "valid"
    assert result["auth_state_expires_at"] == "2100-01-01T00:00:00+00:00"


def test_auth_state_status_is_valid_with_unknown_expiry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    created = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="人工验证码环境",
            site_url="https://example.test",
            username="admin",
            password="secret123",
            login_strategy="account_password",
            captcha_strategy="manual",
            reuse_auth_state=True,
        ),
        ACTOR,
    )
    state_path = environment_auth_state.auth_state_path("project-1", created["id"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        '{"cookies":[{"name":"sid","value":"secret","domain":"example.test","path":"/"}],"origins":[]}',
        encoding="utf-8",
    )

    result = environment_service.list_project_environments("project-1", ACTOR)[0]

    assert result["auth_state_status"] == "valid"
    assert result["auth_state_expires_at"] is None


def test_manual_auth_start_requires_manual_captcha_strategy(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    created = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="无验证码环境",
            site_url="https://example.test",
            username="admin",
            password="secret123",
            login_strategy="account_password",
            captcha_strategy="none",
            reuse_auth_state=True,
        ),
        ACTOR,
    )

    with pytest.raises(HTTPException) as exc_info:
        manual_auth_service.start_manual_auth_session("project-1", created["id"], ACTOR)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "MANUAL_AUTH_NOT_ENABLED"


def test_manual_auth_start_returns_session_summary_without_state_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    created = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="人工验证码环境",
            site_url="https://example.test",
            username="admin",
            password="secret123",
            login_strategy="account_password",
            captcha_strategy="manual",
            reuse_auth_state=True,
        ),
        ACTOR,
    )

    class FakeProcess:
        stdin = None

        def poll(self):
            return None

    monkeypatch.setattr(manual_auth_service, "_launch_manual_auth_process", lambda *args, **kwargs: FakeProcess())

    result = manual_auth_service.start_manual_auth_session("project-1", created["id"], ACTOR)

    assert result["status"] == "waiting_human"
    assert result["session_id"]
    assert result["auth_state_status"] == "none"
    assert "storage-state" not in str(result)
    assert "secret123" not in str(result)
