import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.core import environment_auth_state
from app.core import environment_credentials
from app.schemas.environment import ProjectEnvironmentCreateIn, ProjectEnvironmentUpdateIn
from app.seed.init_db import init_db
from app.services import environment_service, manual_auth_service, auto_auth_service


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
    with manual_auth_service._sessions_lock:
        manual_auth_service._sessions.clear()
    with auto_auth_service._running_lock:
        auto_auth_service._running_environments.clear()
    init_db()


def _seed_project(project_id: str = "project-1") -> None:
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description) VALUES (?, '测试项目', 'active', '')",
            (project_id,),
        )


class FakeManualAuthProcess:
    stdin = None

    def __init__(self, returncode: int | None = None) -> None:
        self.returncode = returncode
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9


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
    assert "password_mask" not in result
    assert result["captcha_strategy"] == "none"
    assert result["reuse_auth_state"] is False
    assert result["has_saved_credentials"] is False
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
    assert "password_mask" not in result
    assert result["captcha_strategy"] == "none"
    assert result["reuse_auth_state"] is True
    assert result["has_saved_credentials"] is True
    assert result["auth_state_status"] == "none"
    assert environment_credentials.load_credentials("project-1", result["id"]) == {
        "username": "admin",
        "password": "secret123",
    }
    with core_db.connect() as db:
        stored = db.execute(
            "SELECT password_encrypted, password_hash FROM project_environments WHERE id = ?",
            (result["id"],),
        ).fetchone()
    assert stored["password_encrypted"]
    assert stored["password_hash"]
    assert "secret123" not in stored["password_encrypted"]


def test_create_ai_letter_schedules_auto_auth(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    scheduled: list[tuple[str, str]] = []

    def fake_schedule(project_id: str, environment_id: str) -> None:
        scheduled.append((project_id, environment_id))
        auto_auth_service._write_auto_auth_status(
            project_id,
            environment_id,
            status="queued",
            message="等待自动登录",
        )

    monkeypatch.setattr(auto_auth_service, "schedule_ai_letter_auto_auth", fake_schedule)

    result = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="AI 验证码环境",
            site_url="https://example.test/login",
            username="admin",
            password="secret123",
            login_strategy="account_password",
            captcha_strategy="ai_letter",
            reuse_auth_state=True,
        ),
        ACTOR,
    )

    assert scheduled == [("project-1", result["id"])]
    assert result["auto_auth_status"] == "queued"
    assert result["auth_state_status"] == "logging_in"
    assert "自动登录" in result["auth_state_message"]


def test_update_ai_letter_with_valid_auth_state_does_not_reschedule_auto_auth(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    scheduled: list[tuple[str, str]] = []

    def fake_schedule(project_id: str, environment_id: str) -> None:
        scheduled.append((project_id, environment_id))

    monkeypatch.setattr(auto_auth_service, "schedule_ai_letter_auto_auth", fake_schedule)

    created = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="AI 验证码环境",
            site_url="https://example.test/login",
            username="admin",
            password="secret123",
            login_strategy="account_password",
            captcha_strategy="ai_letter",
            reuse_auth_state=True,
        ),
        ACTOR,
    )
    scheduled.clear()
    state_path = environment_auth_state.auth_state_path("project-1", created["id"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        f'{{"cookies":[{{"name":"sid","value":"secret","domain":"example.test","path":"/","expires":{FUTURE_EXPIRES}}}],"origins":[]}}',
        encoding="utf-8",
    )
    auto_auth_service._write_auto_auth_status(
        "project-1",
        created["id"],
        status="succeeded",
        message="登录态已自动保存。",
    )

    updated = environment_service.update_project_environment(
        "project-1",
        created["id"],
        ProjectEnvironmentUpdateIn(description="仅更新描述"),
        ACTOR,
    )

    assert scheduled == []
    assert updated["auth_state_status"] == "valid"


def test_start_environment_auto_auth_triggers_login(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    scheduled: list[tuple[str, str]] = []

    def fake_schedule(project_id: str, environment_id: str) -> None:
        scheduled.append((project_id, environment_id))
        auto_auth_service._write_auto_auth_status(
            project_id,
            environment_id,
            status="queued",
            message="等待自动登录",
        )

    monkeypatch.setattr(auto_auth_service, "schedule_ai_letter_auto_auth", fake_schedule)

    created = environment_service.create_project_environment(
        "project-1",
        ProjectEnvironmentCreateIn(
            name="AI 验证码环境",
            site_url="https://example.test/login",
            username="admin",
            password="secret123",
            login_strategy="account_password",
            captcha_strategy="ai_letter",
            reuse_auth_state=True,
        ),
        ACTOR,
    )
    scheduled.clear()

    result = environment_service.start_environment_auto_auth("project-1", created["id"], ACTOR)

    assert scheduled == [("project-1", created["id"])]
    assert result["auth_state_status"] == "logging_in"
    assert result["auto_auth_status"] == "queued"


def test_start_environment_auto_auth_requires_saved_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO project_environments (
                id, project_id, name, site_url, username, login_strategy, captcha_strategy,
                reuse_auth_state, description, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "env-no-password",
                "project-1",
                "无密码环境",
                "https://example.test/login",
                "admin",
                "account_password",
                "ai_letter",
                1,
                "",
                "u-admin",
            ),
        )

    with pytest.raises(HTTPException) as exc:
        environment_service.start_environment_auto_auth("project-1", "env-no-password", ACTOR)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "AUTO_AUTH_CREDENTIALS_REQUIRED"


def test_update_username_keeps_saved_password_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
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
        ),
        ACTOR,
    )

    environment_service.update_project_environment(
        "project-1",
        created["id"],
        ProjectEnvironmentUpdateIn(username="tester"),
        ACTOR,
    )

    assert environment_credentials.load_credentials("project-1", created["id"]) == {
        "username": "tester",
        "password": "secret123",
    }


def test_update_empty_password_keeps_existing_password_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
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
        ),
        ACTOR,
    )

    updated = environment_service.update_project_environment(
        "project-1",
        created["id"],
        ProjectEnvironmentUpdateIn(password=""),
        ACTOR,
    )

    assert "password_mask" not in updated
    assert updated["has_saved_credentials"] is True
    assert environment_credentials.load_credentials("project-1", created["id"]) == {
        "username": "admin",
        "password": "secret123",
    }


def test_environment_list_reports_saved_credentials_from_secure_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
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
        ),
        ACTOR,
    )

    listed = environment_service.list_project_environments("project-1", ACTOR)
    assert listed[0]["id"] == created["id"]
    assert "password_mask" not in listed[0]
    assert listed[0]["has_saved_credentials"] is True

    environment_credentials.delete_credentials("project-1", created["id"])

    listed = environment_service.list_project_environments("project-1", ACTOR)
    assert "password_mask" not in listed[0]
    assert listed[0]["has_saved_credentials"] is False


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


def test_legacy_manual_login_strategy_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    with pytest.raises(HTTPException) as exc_info:
        environment_service.create_project_environment(
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

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "INVALID_LOGIN_STRATEGY"


def test_init_db_migrates_legacy_login_strategies(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO project_environments
              (id, project_id, name, site_url, username, password_encrypted, password_hash,
               login_strategy, captcha_strategy, reuse_auth_state, created_by)
            VALUES
              ('env-reuse', 'project-1', '旧复用态', 'https://reuse.test', 'admin', 'enc', 'hash',
               'reuse_state', 'none', 1, 'u-admin'),
              ('env-manual', 'project-1', '旧人工登录', 'https://manual.test', 'admin', 'enc', 'hash',
               'manual', 'none', 1, 'u-admin'),
              ('env-empty', 'project-1', '空策略', 'https://empty.test', 'admin', 'enc', 'hash',
               '', 'manual', 1, 'u-admin')
            """
        )

    init_db()

    with core_db.connect() as db:
        rows = {
            row["id"]: row
            for row in db.execute(
                """
                SELECT id, username, password_encrypted, password_hash, login_strategy, captcha_strategy, reuse_auth_state
                FROM project_environments
                WHERE id IN ('env-reuse', 'env-manual', 'env-empty')
                """
            ).fetchall()
        }

    assert rows["env-reuse"]["login_strategy"] == "account_password"
    assert rows["env-reuse"]["captcha_strategy"] == "none"
    assert rows["env-reuse"]["reuse_auth_state"] == 1
    assert rows["env-manual"]["login_strategy"] == "account_password"
    assert rows["env-manual"]["captcha_strategy"] == "manual"
    assert rows["env-manual"]["reuse_auth_state"] == 1
    assert rows["env-empty"]["login_strategy"] == "skip_login"
    assert rows["env-empty"]["captcha_strategy"] == "none"
    assert rows["env-empty"]["reuse_auth_state"] == 0
    assert rows["env-empty"]["username"] == ""
    assert rows["env-empty"]["password_encrypted"] == ""
    assert rows["env-empty"]["password_hash"] == ""


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
    assert "password_mask" not in updated
    assert updated["captcha_strategy"] == "none"
    assert updated["reuse_auth_state"] is False
    assert updated["has_saved_credentials"] is False
    assert environment_credentials.load_credentials("project-1", created["id"]) is None


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

    monkeypatch.setattr(
        manual_auth_service,
        "_launch_manual_auth_process",
        lambda *args, **kwargs: FakeManualAuthProcess(),
    )

    result = manual_auth_service.start_manual_auth_session("project-1", created["id"], ACTOR)

    assert result["status"] == "waiting_human"
    assert result["session_id"]
    assert result["auth_state_status"] == "none"
    assert "storage-state" not in str(result)
    assert "secret123" not in str(result)


def test_manual_auth_start_without_saved_credentials_opens_without_autofill(
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
    environment_credentials.delete_credentials("project-1", created["id"])
    captured: dict = {}

    def fake_launch(*args, **kwargs):
        captured.update(kwargs)
        return FakeManualAuthProcess()

    monkeypatch.setattr(manual_auth_service, "_launch_manual_auth_process", fake_launch)

    result = manual_auth_service.start_manual_auth_session("project-1", created["id"], ACTOR)

    assert result["status"] == "waiting_human"
    assert result["has_saved_credentials"] is False
    assert captured["credentials"] is None
    assert "未保存可自动填充的密码" in result["message"]


def test_manual_auth_start_injects_saved_credentials_to_runner(
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
    captured: dict = {}

    def fake_launch(*args, **kwargs):
        captured.update(kwargs)
        return FakeManualAuthProcess()

    monkeypatch.setattr(manual_auth_service, "_launch_manual_auth_process", fake_launch)

    result = manual_auth_service.start_manual_auth_session("project-1", created["id"], ACTOR)

    assert result["status"] == "waiting_human"
    assert result["has_saved_credentials"] is True
    assert captured["credentials"] == {"username": "admin", "password": "secret123"}


def test_manual_auth_process_clears_inherited_credentials_without_saved_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    captured: dict = {}

    def fake_popen(*args, **kwargs):
        captured.update(kwargs)
        return FakeManualAuthProcess()

    monkeypatch.setenv("AI_TESTING_LOGIN_USERNAME", "old-user")
    monkeypatch.setenv("AI_TESTING_LOGIN_PASSWORD", "old-password")
    monkeypatch.setattr(manual_auth_service.subprocess, "Popen", fake_popen)

    manual_auth_service._launch_manual_auth_process(
        site_url="https://example.test",
        storage_state_path=tmp_path / "state.json",
        browser_channel="chromium",
        credentials=None,
    )

    assert "AI_TESTING_LOGIN_USERNAME" not in captured["env"]
    assert "AI_TESTING_LOGIN_PASSWORD" not in captured["env"]


def test_manual_auth_status_returns_ended_when_browser_process_exited(
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

    monkeypatch.setattr(
        manual_auth_service,
        "_launch_manual_auth_process",
        lambda *args, **kwargs: FakeManualAuthProcess(returncode=1),
    )

    session = manual_auth_service.start_manual_auth_session("project-1", created["id"], ACTOR)
    result = manual_auth_service.get_manual_auth_session_status("project-1", created["id"], session["session_id"], ACTOR)

    assert result["status"] == "ended"
    assert result["message"] == "登录窗口已关闭，请重新打开登录窗口。"


def test_manual_auth_status_returns_auto_saved_when_process_exited_with_valid_state(
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
    state_path = environment_auth_state.auth_state_path("project-1", created["id"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        f'{{"cookies":[{{"name":"sid","value":"secret","domain":"example.test","path":"/","expires":{FUTURE_EXPIRES}}}],"origins":[]}}',
        encoding="utf-8",
    )

    process = FakeManualAuthProcess(returncode=0)
    session_id = "manual-auth-auto-saved"
    with manual_auth_service._sessions_lock:
        manual_auth_service._sessions[session_id] = {
            "project_id": "project-1",
            "environment_id": created["id"],
            "process": process,
            "storage_state_path": state_path,
        }

    result = manual_auth_service.get_manual_auth_session_status("project-1", created["id"], session_id, ACTOR)

    assert result["status"] == "auto_saved"
    assert result["auth_state_status"] == "valid"
    assert result["message"] == "检测到登录成功，登录态已自动保存。"
    with manual_auth_service._sessions_lock:
        assert session_id not in manual_auth_service._sessions
