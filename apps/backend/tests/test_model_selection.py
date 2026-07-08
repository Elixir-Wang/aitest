import pytest
from fastapi import HTTPException

from app.agents.model_selection import ModelSelection, resolve_model_selection, thinking_disabled_extra_body
from app.core import db as core_db
from app.repositories import model_repo, project_repo
from app.schemas.model import ModelAssignmentIn
from app.seed.init_db import init_db
from app.services import model_service


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()


def _create_provider(provider_id: str = "mp-openai", *, status: str = "enabled", api_key: str = "sk-test") -> None:
    with core_db.connect() as db:
        model_repo.create_provider(
            db,
            provider_id=provider_id,
            provider="openai",
            model="gpt-5.5",
            base_url="https://api.openai.com/v1",
            api_key=api_key,
            description="test",
            status=status,
            created_by="u-admin",
        )


def test_model_assignment_update_and_selection_resolves_model_config(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _create_provider()

    result = model_service.update_model_assignment(
        "document_editor",
        payload=ModelAssignmentIn(model_provider_id="mp-openai"),
        actor={"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin"},
    )

    assert result["capability_id"] == "document_editor"
    assert "capability_kind" not in result

    selection = resolve_model_selection("document_editor")
    assert selection.model == "gpt-5.5"
    assert selection.api_key == "sk-test"


def test_legacy_site_exploration_assignment_migrates_to_page_exploration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _create_provider()
    with core_db.connect() as db:
        model_repo.upsert_model_assignment(
            db,
            capability_id="site_exploration",
            model_provider_id="mp-openai",
        )

    from app.seed.init_db import init_db

    init_db()

    assignments = model_service.list_model_assignments({"id": "u-admin"})
    assignment_ids = [item["capability_id"] for item in assignments]
    page_assignment = next(item for item in assignments if item["capability_id"] == "page_exploration")

    assert "site_exploration" not in assignment_ids
    assert page_assignment["model_provider_id"] == "mp-openai"


def test_model_assignment_rejects_unknown_capability(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _create_provider()

    with pytest.raises(HTTPException) as exc_info:
        model_service.update_model_assignment(
            "unknown_capability",
            payload=ModelAssignmentIn(model_provider_id="mp-openai"),
            actor={"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin"},
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "AI_CAPABILITY_NOT_FOUND"


def test_model_assignment_rejects_disabled_provider(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _create_provider(status="disabled")

    with pytest.raises(HTTPException) as exc_info:
        model_service.update_model_assignment(
            "document_editor",
            payload=ModelAssignmentIn(model_provider_id="mp-openai"),
            actor={"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin"},
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "MODEL_PROVIDER_DISABLED"


def test_resolve_model_selection_rejects_missing_assignment(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="未分配可用模型配置"):
        resolve_model_selection("document_editor")


def test_model_provider_health_check_disables_responses_api_for_compatible_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        model_repo.create_provider(
            db,
            provider_id="mp-minimax",
            provider="Minimax",
            model="MiniMax-M3",
            base_url="https://minimax.example/v1",
            api_key="sk-test",
            description="test",
            status="enabled",
            created_by="u-admin",
        )

    calls = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls.update(kwargs)

        def invoke(self, _message):
            class Response:
                content = "ok"

            return Response()

    monkeypatch.setattr(model_service, "ChatOpenAI", FakeChatOpenAI)

    result = model_service.test_model_provider(
        "mp-minimax",
        actor={"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin"},
    )

    assert result["success"] is True
    assert calls["use_responses_api"] is False


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("Minimax", "MiniMax-M3"),
        ("openai-compatible", "deepseek-chat"),
    ],
)
def test_thinking_disabled_extra_body_supports_thinking_models(provider: str, model: str) -> None:
    selection = ModelSelection(provider=provider, model=model, base_url=None, api_key="sk-test")

    assert thinking_disabled_extra_body(selection) == {"thinking": {"type": "disabled"}}


def test_thinking_disabled_extra_body_skips_models_without_thinking_toggle() -> None:
    selection = ModelSelection(provider="openai", model="gpt-5.5", base_url=None, api_key="sk-test")

    assert thinking_disabled_extra_body(selection) is None


def test_exploration_goal_optimization_disables_model_thinking(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from app.services import project_service

    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        project_repo.create(db, project_id="project-1", name="测试项目", status="active", description="")

    captured = {}

    class FakeModel:
        def invoke(self, _messages):
            class Response:
                content = "进入登录页并验证登录流程"

            return Response()

    def fake_build_agent_model(selection, *, extra_body=None):
        captured["selection"] = selection
        captured["extra_body"] = extra_body
        return FakeModel()

    monkeypatch.setattr(
        project_service,
        "resolve_model_selection",
        lambda _capability_id: ModelSelection(provider="Minimax", model="MiniMax-M3", base_url=None, api_key="sk-test"),
    )
    monkeypatch.setattr(project_service, "build_agent_model", fake_build_agent_model)

    result = project_service.optimize_exploration_goal("project-1", "登录", actor={"id": "u-admin"})

    assert result == {"optimized_goal": "进入登录页并验证登录流程"}
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
