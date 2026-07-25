import pytest
from langchain.agents.structured_output import ToolStrategy
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
    assert isinstance(calls["response_format"], ToolStrategy)
    assert calls["response_format"].schema is DocumentEditOutput
    assert "文档修改智能体" in calls["system_prompt"]


def test_build_agent_model_uses_deepseek_client_for_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.model_selection import build_agent_model

    deepseek_calls = {}
    openai_called = False

    def fake_chat_deepseek(**kwargs):
        deepseek_calls.update(kwargs)
        return "deepseek-model"

    def fake_chat_openai(**kwargs):
        nonlocal openai_called
        openai_called = True
        return "openai-model"

    monkeypatch.setattr("app.agents.model_selection.ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr("app.agents.model_selection.ChatDeepSeek", fake_chat_deepseek, raising=False)

    model = build_agent_model(
        ModelSelection(
            provider="DeepSeek",
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key="sk-test",
        )
    )

    assert model == "deepseek-model"
    assert openai_called is False
    assert deepseek_calls["model"] == "deepseek-chat"
    assert isinstance(deepseek_calls["api_key"], SecretStr)
    assert deepseek_calls["api_key"].get_secret_value() == "sk-test"
    assert deepseek_calls["base_url"] == "https://api.deepseek.com"
    assert deepseek_calls["temperature"] == 0
    assert "use_responses_api" not in deepseek_calls


def test_build_agent_model_passes_extra_body_to_deepseek_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.model_selection import build_agent_model

    calls = {}

    def fake_chat_deepseek(**kwargs):
        calls.update(kwargs)
        return "deepseek-model"

    monkeypatch.setattr("app.agents.model_selection.ChatDeepSeek", fake_chat_deepseek, raising=False)

    model = build_agent_model(
        ModelSelection(
            provider="deepseek",
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key="sk-test",
        ),
        extra_body={"thinking": {"type": "disabled"}},
    )

    assert model == "deepseek-model"
    assert calls["extra_body"] == {"thinking": {"type": "disabled"}}


def test_build_agent_model_accepts_minimax_openai_tools_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.model_selection import build_agent_model

    calls = {}

    def fake_chat_openai(**kwargs):
        calls.update(kwargs)
        return "chat-model"

    monkeypatch.setattr("app.agents.model_selection.ChatOpenAI", fake_chat_openai)

    model = build_agent_model(
        ModelSelection(
            provider="Minimax",
            model="MiniMax-M3",
            base_url="https://minimax.example/v1",
            api_key="sk-test",
        )
    )

    assert model == "chat-model"
    assert calls["model"] == "MiniMax-M3"
    assert calls["base_url"] == "https://minimax.example/v1"
    assert calls["use_responses_api"] is False


def test_build_agent_model_keeps_official_openai_responses_api_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.model_selection import build_agent_model

    calls = {}

    def fake_chat_openai(**kwargs):
        calls.update(kwargs)
        return "chat-model"

    monkeypatch.setattr("app.agents.model_selection.ChatOpenAI", fake_chat_openai)

    model = build_agent_model(
        ModelSelection(
            provider="OpenAI",
            model="gpt-5.5",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
        )
    )

    assert model == "chat-model"
    assert calls["use_responses_api"] is None


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
    monkeypatch.setattr("app.agents.document_editor.service.thinking_disabled_extra_body", lambda selection: None)
    monkeypatch.setattr(
        "app.agents.document_editor.service.build_agent_model",
        lambda selection, *, extra_body=None: "model",
    )
    monkeypatch.setattr("app.agents.document_editor.service.document_editor_agent", lambda model: FakeAgent())

    result = edit_document(
        DocumentEditInput(
            content=original_content,
            instruction="把标题改成 New title",
        )
    )

    assert result is output


def test_document_editor_service_disables_thinking_for_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.document_editor.service import edit_document

    selection = ModelSelection(
        provider="DeepSeek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key="sk-test",
    )
    output = DocumentEditOutput(
        edited_content="# New title",
        change_summary="Updated title.",
    )
    model_calls = {}

    class FakeAgent:
        def invoke(self, payload):
            return {"structured_response": output}

    def fake_build_agent_model(received_selection, *, extra_body=None):
        model_calls["selection"] = received_selection
        model_calls["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr("app.agents.document_editor.service.resolve_model_selection", lambda capability_id: selection)
    monkeypatch.setattr("app.agents.document_editor.service.build_agent_model", fake_build_agent_model)
    monkeypatch.setattr("app.agents.document_editor.service.document_editor_agent", lambda model: FakeAgent())

    result = edit_document(DocumentEditInput(content="# Old title", instruction="把标题改成 New title"))

    assert result is output
    assert model_calls == {
        "selection": selection,
        "extra_body": {"thinking": {"type": "disabled"}},
    }


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
    monkeypatch.setattr("app.agents.document_editor.service.thinking_disabled_extra_body", lambda selection: None)
    monkeypatch.setattr(
        "app.agents.document_editor.service.build_agent_model",
        lambda selection, *, extra_body=None: "model",
    )
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
    monkeypatch.setattr("app.agents.document_editor.service.thinking_disabled_extra_body", lambda selection: None)
    monkeypatch.setattr(
        "app.agents.document_editor.service.build_agent_model",
        lambda selection, *, extra_body=None: "model",
    )
    monkeypatch.setattr("app.agents.document_editor.service.document_editor_agent", lambda model: FakeAgent())

    with pytest.raises(ValueError, match="未返回结构化结果"):
        edit_document(
            DocumentEditInput(
                content=original_content,
                instruction="把标题改成 New title",
            )
        )
