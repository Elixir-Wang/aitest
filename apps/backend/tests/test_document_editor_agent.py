import pytest
from pydantic import SecretStr

from app.agents.document_editor import schemas
from app.agents.document_editor.agent import document_editor_agent
from app.agents.document_editor.schemas import DocumentEditInput, DocumentEditOutput
from app.agents.model_selection import ModelSelection


def test_document_editor_agent_schemas_expose_structured_output() -> None:
    assert schemas.DocumentEditOutput is DocumentEditOutput


def test_document_editor_agent_uses_langchain_create_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {}

    def fake_create_agent(**kwargs):
        calls.update(kwargs)
        return "agent"

    monkeypatch.setattr("app.agents.document_editor.agent.create_agent", fake_create_agent)

    agent = document_editor_agent("model")

    assert agent == "agent"
    assert calls["model"] == "model"
    assert calls["tools"] == []
    assert calls["response_format"] is DocumentEditOutput
    assert "文档修改智能体" in calls["system_prompt"]


def test_build_agent_model_uses_openai_compatible_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.model_selection import build_agent_model

    calls = {}

    def fake_chat_openai(**kwargs):
        calls.update(kwargs)
        return "chat-model"

    monkeypatch.setattr("app.agents.model_selection.ChatOpenAI", fake_chat_openai)

    model = build_agent_model(
        ModelSelection(
            provider="deepseek",
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key="sk-test",
        )
    )

    assert model == "chat-model"
    assert calls["model"] == "deepseek-chat"
    assert isinstance(calls["api_key"], SecretStr)
    assert calls["api_key"].get_secret_value() == "sk-test"
    assert calls["base_url"] == "https://api.deepseek.com"
    assert calls["temperature"] == 0


def test_document_editor_service_returns_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    original_content = "# Old title\n\n" + "Body line.\n" * 20
    edited_content = "# New title\n\n" + "Body line.\n" * 20
    from app.agents.document_editor.service import edit_document

    output = DocumentEditOutput(
        edited_content=edited_content,
        change_summary="Updated title.",
    )

    class FakeAgent:
        def invoke(self, payload):
            assert payload["messages"][0]["role"] == "user"
            assert "instruction:" in payload["messages"][0]["content"]
            assert "document_content:" in payload["messages"][0]["content"]
            return {"structured_response": output}

    monkeypatch.setattr("app.agents.document_editor.service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.agents.document_editor.service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.agents.document_editor.service.document_editor_agent", lambda model: FakeAgent())

    result = edit_document(
        DocumentEditInput(
            content=original_content,
            instruction="把标题改成 New title",
        )
    )

    assert result is output


def test_document_editor_service_allows_empty_content_for_unchanged_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_content = "# Old title\n\n" + "Body line.\n" * 20
    from app.agents.document_editor.service import edit_document

    output = DocumentEditOutput(
        edited_content="",
        change_summary="未修改：未找到需要调整的内容。",
    )

    class FakeAgent:
        def invoke(self, payload):
            return {"structured_response": output}

    monkeypatch.setattr("app.agents.document_editor.service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.agents.document_editor.service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.agents.document_editor.service.document_editor_agent", lambda model: FakeAgent())

    result = edit_document(
        DocumentEditInput(
            content=original_content,
            instruction="如果没有问题就不要修改",
        )
    )

    assert result is output
    assert result.edited_content == ""
    assert result.change_summary.startswith("未修改")


def test_document_editor_service_rejects_missing_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    original_content = "# Old title\n\n" + "Body line.\n" * 20
    from app.agents.document_editor.service import edit_document

    class FakeAgent:
        def invoke(self, payload):
            return {}

    monkeypatch.setattr("app.agents.document_editor.service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.agents.document_editor.service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.agents.document_editor.service.document_editor_agent", lambda model: FakeAgent())

    with pytest.raises(ValueError, match="未返回结构化结果"):
        edit_document(
            DocumentEditInput(
                content=original_content,
                instruction="把标题改成 New title",
            )
        )
