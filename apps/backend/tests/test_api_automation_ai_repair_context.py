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


def test_failure_context_includes_generated_case_notes_and_oracle(tmp_path) -> None:
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "cases.yaml").write_text(
        """- case_id: case-1
  endpoint_id: endpoint-1
  test_point_key: body.required.start_date.missing
  oracle_status: needs_confirmation
  test_description: 缺失 start_date，验证接口拒绝非法请求
  request:
    body: {end_date: '2026-02-05'}
  assertions:
    - {type: status_code, expected: 400}
  notes: 文档未声明状态码，按常见约定推断为 400
""",
        encoding="utf-8",
    )
    context = build_failure_context(
        run={"id": "run-1"},
        logs={},
        report={"tests": [], "observations": [{"case_id": "case-1", "status_code": 200, "response_body": {}}]},
        suite_path=suite,
        history=[],
        user_context="",
    )
    case = context["generated_cases"][0]
    assert case["oracle_status"] == "needs_confirmation"
    assert case["test_description"].startswith("缺失 start_date")
    assert case["notes"].endswith("400")
    assert case["generation_notes"] == case["notes"]
    assert context["observations"][0]["status_code"] == 200
