import pytest

from app.presentation.serializers import resolve_environment_auth_state_display


def test_resolve_auth_display_logging_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.presentation.serializers.get_auto_auth_status",
        lambda _project_id, _environment_id: {
            "status": "running",
            "message": "正在识别验证码（第 1/3 次）",
            "updated_at": None,
            "last_error_code": "",
        },
    )
    monkeypatch.setattr(
        "app.presentation.serializers.auth_state_summary",
        lambda **_kwargs: {"status": "none", "expires_at": None},
    )

    result = resolve_environment_auth_state_display(
        project_id="project-1",
        environment_id="env-1",
        login_strategy="account_password",
        reuse_auth_state=True,
    )

    assert result["auth_state_status"] == "logging_in"
    assert "验证码" in result["auth_state_message"]


def test_resolve_auth_display_login_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.presentation.serializers.get_auto_auth_status",
        lambda _project_id, _environment_id: {
            "status": "failed",
            "message": "AI 能力未分配可用模型配置，无法运行：站点探索智能体",
            "updated_at": None,
            "last_error_code": "CAPTCHA_SOLVE_FAILED",
        },
    )
    monkeypatch.setattr(
        "app.presentation.serializers.auth_state_summary",
        lambda **_kwargs: {"status": "valid", "expires_at": "2100-01-01T00:00:00+00:00"},
    )

    result = resolve_environment_auth_state_display(
        project_id="project-1",
        environment_id="env-1",
        login_strategy="account_password",
        reuse_auth_state=True,
    )

    assert result["auth_state_status"] == "login_failed"
    assert "模型" in result["auth_state_message"]
