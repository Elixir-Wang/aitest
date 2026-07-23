import json

from app.services.api_automation.self_healing_context import build_failure_context, redact_sensitive


def test_redact_sensitive_nested_values() -> None:
    value = {
        "headers": {
            "Authorization": "Bearer secret-token",
            "Cookie": "sid=abc",
            "x-api-key": "api-secret",
        },
        "password": "plain-password",
    }

    redacted = redact_sensitive(value)

    assert redacted["headers"]["Authorization"] == "Bearer [REDACTED]"
    assert redacted["headers"]["Cookie"] == "[REDACTED]"
    assert redacted["headers"]["x-api-key"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"


def test_failure_context_contains_history_without_secrets(tmp_path) -> None:
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "test_api.py").write_text("TOKEN = 'do-not-send'\n", encoding="utf-8")
    context = build_failure_context(
        run={"id": "run-1", "summary": {"failed": 1}},
        logs={"stdout": "Authorization: Bearer secret-token", "stderr": ""},
        report={"tests": [{"nodeid": "test_api.py::test_one", "outcome": "failed"}]},
        suite_path=suite,
        history=[{"attempt": 1, "user_context": "token=history-secret"}],
        user_context="password=current-secret",
    )

    encoded = json.dumps(context, ensure_ascii=False)
    assert "test_api.py::test_one" in encoded
    assert "secret-token" not in encoded
    assert "history-secret" not in encoded
    assert "current-secret" not in encoded
