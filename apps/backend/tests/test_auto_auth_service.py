import json
from pathlib import Path

import pytest

from app.core import db as core_db
from app.core import environment_auth_state
from app.core import environment_credentials
from app.seed.init_db import init_db
from app.services import auto_auth_service, captcha_solver_service, login_form_analyzer_service


def _login_page_observed_event(tmp_path: Path) -> str:
    elements_path = tmp_path / "login-elements.json"
    page_image_path = tmp_path / "login-page.png"
    page_image_path.write_bytes(b"png")
    elements_path.write_text(
        json.dumps(
            [
                {
                    "element_id": "login-el-1",
                    "selector": '[data-ai-testing-login-el="login-el-1"]',
                }
            ]
        ),
        encoding="utf-8",
    )
    return json.dumps(
        {
            "kind": "login_page_observed",
            "page_image_path": str(page_image_path),
            "elements_path": str(elements_path),
            "element_count": 1,
        }
    ) + "\n"


def _planned_login_form_plan() -> dict:
    return {
        "strategy": "planned",
        "username_selector": 'input[placeholder="请输入账号"]',
        "password_selector": 'input[placeholder="请输入密码"]',
        "captcha_image_selector": "img.verify-code",
        "captcha_input_selector": 'input[placeholder="请输入图形验证码"]',
        "agreement_selector": ".uui-checkbox-wrap",
        "login_button_selector": "button",
        "has_agreement_checkbox": True,
    }


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(environment_auth_state.settings, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    monkeypatch.setattr(environment_credentials.settings, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    with auto_auth_service._running_lock:
        auto_auth_service._running_environments.clear()
    init_db()


def _seed_environment() -> None:
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description) VALUES ('project-1', '测试项目', 'active', '')"
        )
        db.execute(
            """
            INSERT INTO project_environments
              (id, project_id, name, site_url, username, login_strategy, captcha_strategy, reuse_auth_state, created_by)
            VALUES ('env-1', 'project-1', '测试环境', 'https://example.test/login', 'tester', 'account_password', 'ai_letter', 1, 'u-admin')
            """
        )


def test_should_schedule_when_ai_letter_and_reuse_auth_state() -> None:
    assert auto_auth_service.should_schedule_ai_letter_auto_auth(
        {
            "login_strategy": "account_password",
            "captcha_strategy": "ai_letter",
            "reuse_auth_state": True,
            "has_saved_credentials": True,
        }
    )


def test_should_not_schedule_for_manual_or_none_captcha() -> None:
    assert not auto_auth_service.should_schedule_ai_letter_auto_auth(
        {
            "login_strategy": "account_password",
            "captcha_strategy": "manual",
            "reuse_auth_state": True,
            "has_saved_credentials": True,
        }
    )
    assert not auto_auth_service.should_schedule_ai_letter_auto_auth(
        {
            "login_strategy": "account_password",
            "captcha_strategy": "none",
            "reuse_auth_state": True,
            "has_saved_credentials": True,
        }
    )


def test_run_auto_auth_writes_storage_state_on_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_environment()
    environment_credentials.save_credentials("project-1", "env-1", username="tester", password="secret123")

    class FakeProcess:
        returncode = 0

        def __init__(self) -> None:
            self.stdin_lines: list[str] = []
            self._stdout = [
                _login_page_observed_event(tmp_path),
                json.dumps({"kind": "session_started", "url": "https://example.test/login"}) + "\n",
                json.dumps(
                    {
                        "kind": "captcha_challenge",
                        "attempt": 1,
                        "image_path": str(tmp_path / "captcha.png"),
                    }
                )
                + "\n",
                json.dumps({"kind": "login_succeeded", "attempt": 1, "reasons": ["logged_in_ui_signal"]}) + "\n",
            ]
            (tmp_path / "captcha.png").write_bytes(b"png")
            state_path = environment_auth_state.auth_state_path("project-1", "env-1")
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")

        @property
        def stdin(self):
            return self

        @property
        def stdout(self):
            return iter(self._stdout)

        def write(self, value: str) -> int:
            self.stdin_lines.append(value)
            return len(value)

        def flush(self) -> None:
            return None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr(auto_auth_service, "_launch_ai_letter_login_process", lambda **_kwargs: FakeProcess())
    monkeypatch.setattr(captcha_solver_service, "solve_letter_captcha", lambda _path, expected_length=None: "AB12")
    monkeypatch.setattr(
        login_form_analyzer_service,
        "analyze_login_form",
        lambda _page_image_path, _elements: _planned_login_form_plan(),
    )

    auto_auth_service._run_ai_letter_auto_auth("project-1", "env-1")

    status = auto_auth_service.get_auto_auth_status("project-1", "env-1")
    assert status["status"] == "failed"
    assert status["last_error_code"] == "AUTH_STATE_INVALID"
    assert environment_auth_state.auth_state_path("project-1", "env-1").exists()


def test_launch_ai_letter_login_process_passes_login_plan_path() -> None:
    command: list[str] = []
    env: dict[str, str] = {}

    def fake_popen(args, **kwargs):
        command.extend(args)
        env.update(kwargs["env"])

        class FakeProcess:
            pass

        return FakeProcess()

    original_popen = auto_auth_service.subprocess.Popen
    try:
        auto_auth_service.subprocess.Popen = fake_popen
        auto_auth_service._launch_ai_letter_login_process(
            site_url="https://example.test/login",
            storage_state_path=Path("D:/tmp/storage-state.json"),
            login_plan_path=Path("D:/tmp/login-plan.json"),
            browser_channel="chrome",
            credentials={"username": "tester", "password": "secret123"},
        )
    finally:
        auto_auth_service.subprocess.Popen = original_popen

    assert command[-1] == "D:\\tmp\\login-plan.json" or command[-1] == "D:/tmp/login-plan.json"
    assert env["AI_TESTING_LOGIN_PLAN_PATH"].replace("\\", "/").endswith("/login-plan.json")


def test_run_auto_auth_marks_failed_when_solver_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_environment()
    environment_credentials.save_credentials("project-1", "env-1", username="tester", password="secret123")

    class FakeProcess:
        returncode = 1

        def __init__(self) -> None:
            self.stdin_lines: list[str] = []
            self._stdout = [
                _login_page_observed_event(tmp_path),
                json.dumps(
                    {
                        "kind": "captcha_challenge",
                        "attempt": 1,
                        "image_path": str(tmp_path / "captcha.png"),
                    }
                )
                + "\n",
            ]
            (tmp_path / "captcha.png").write_bytes(b"png")

        @property
        def stdin(self):
            return self

        @property
        def stdout(self):
            return iter(self._stdout)

        def write(self, value: str) -> int:
            self.stdin_lines.append(value)
            return len(value)

        def flush(self) -> None:
            return None

        def poll(self):
            return None

        def wait(self, timeout=None):
            return self.returncode

        def terminate(self) -> None:
            self.returncode = 1

        def kill(self) -> None:
            self.returncode = 1

    monkeypatch.setattr(auto_auth_service, "_launch_ai_letter_login_process", lambda **_kwargs: FakeProcess())
    monkeypatch.setattr(
        login_form_analyzer_service,
        "analyze_login_form",
        lambda _page_image_path, _elements: _planned_login_form_plan(),
    )

    def raise_solver_error(_path, expected_length=None):
        raise captcha_solver_service.CaptchaSolverError("字母验证码识别模型未配置或未启用。")

    monkeypatch.setattr(captcha_solver_service, "solve_letter_captcha", raise_solver_error)

    auto_auth_service._run_ai_letter_auto_auth("project-1", "env-1")

    status = auto_auth_service.get_auto_auth_status("project-1", "env-1")
    assert status["status"] == "failed"
    assert "模型" in status["message"]


def test_run_auto_auth_records_operation_log_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_environment()
    environment_credentials.save_credentials("project-1", "env-1", username="tester", password="secret123")
    recorded: list[dict] = []

    class FakeProcess:
        returncode = 1

        def __init__(self) -> None:
            self.stdin_lines: list[str] = []
            self._stdout = [
                _login_page_observed_event(tmp_path),
                '{"kind": "captcha_challenge", "attempt": 1, "image_path": "' + str(tmp_path / "captcha.png").replace("\\", "/") + '"}\n',
            ]
            (tmp_path / "captcha.png").write_bytes(b"png")

        @property
        def stdin(self):
            return self

        @property
        def stdout(self):
            return iter(self._stdout)

        def write(self, value: str) -> int:
            self.stdin_lines.append(value)
            return len(value)

        def flush(self) -> None:
            return None

        def poll(self):
            return None

        def wait(self, timeout=None):
            return self.returncode

        def terminate(self) -> None:
            self.returncode = 1

        def kill(self) -> None:
            self.returncode = 1

    monkeypatch.setattr(auto_auth_service, "_launch_ai_letter_login_process", lambda **_kwargs: FakeProcess())
    monkeypatch.setattr(
        login_form_analyzer_service,
        "analyze_login_form",
        lambda _page_image_path, _elements: _planned_login_form_plan(),
    )

    def raise_solver_error(_path, expected_length=None):
        raise captcha_solver_service.CaptchaSolverError("字母验证码识别模型未配置或未启用。")

    monkeypatch.setattr(captcha_solver_service, "solve_letter_captcha", raise_solver_error)
    monkeypatch.setattr(
        auto_auth_service.operation_log_service,
        "record_task_event",
        lambda **kwargs: recorded.append(kwargs) or "log-1",
    )

    auto_auth_service._run_ai_letter_auto_auth("project-1", "env-1")

    assert recorded
    assert recorded[0]["module"] == "environment"
    assert recorded[0]["action"] == "auto_auth_login"
    assert recorded[0]["result"] == "failed"


def test_concurrent_schedule_skips_if_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    with auto_auth_service._running_lock:
        auto_auth_service._running_environments.add("env-busy")

    scheduled: list[tuple[str, str]] = []

    def fake_thread(target, args=(), daemon=True):
        scheduled.append(args)
        return None

    monkeypatch.setattr(auto_auth_service.threading, "Thread", fake_thread)
    auto_auth_service.schedule_ai_letter_auto_auth("project-1", "env-busy")
    assert scheduled == []

    with auto_auth_service._running_lock:
        auto_auth_service._running_environments.discard("env-busy")
