import asyncio

import pytest

from app.agents.knowledge_chat.agent import knowledge_chat_agent
from app.agents.knowledge_chat.schemas import KnowledgeQueryInput, KnowledgeQueryOutput


def test_knowledge_chat_contracts_are_owned_by_agent_schema_module() -> None:
    assert KnowledgeQueryInput.__module__ == "app.agents.knowledge_chat.schemas"
    assert KnowledgeQueryOutput.__module__ == "app.agents.knowledge_chat.schemas"


def test_knowledge_chat_agent_uses_langchain_create_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {}

    def fake_create_agent(**kwargs):
        calls.update(kwargs)
        return "agent"

    monkeypatch.setattr("app.agents.knowledge_chat.agent.create_agent", fake_create_agent)

    agent = knowledge_chat_agent("model", ["tool"])

    assert agent == "agent"
    assert calls["model"] == "model"
    assert calls["tools"] == ["tool"]
    assert calls["response_format"] is KnowledgeQueryOutput
    assert "项目知识库 AI" in calls["system_prompt"]
    assert "不要调用 search_project_knowledge" in calls["system_prompt"]
    assert "必须调用 search_project_knowledge" in calls["system_prompt"]


def test_knowledge_chat_agent_can_stream_plain_language_without_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {}

    def fake_create_agent(**kwargs):
        calls.update(kwargs)
        return "agent"

    monkeypatch.setattr("app.agents.knowledge_chat.agent.create_agent", fake_create_agent)

    agent = knowledge_chat_agent("model", ["tool"], structured_output=False)

    assert agent == "agent"
    assert "response_format" not in calls
    assert "不要输出 JSON" in calls["system_prompt"]


def test_knowledge_chat_service_returns_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.knowledge_chat import service

    output = KnowledgeQueryOutput(answer="你好，我是项目知识库 AI。", knowledge_queried=False)

    class FakeAgent:
        async def ainvoke(self, payload):
            assert "最近对话上下文" in payload["messages"][0]["content"]
            assert "用户问题" in payload["messages"][0]["content"]
            return {"structured_response": output}

    captured_tools = []

    def fake_knowledge_chat_agent(model, tools):
        assert model == "model"
        captured_tools.extend(tools)
        return FakeAgent()

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "knowledge_chat_agent", fake_knowledge_chat_agent)

    async def fake_search_project_knowledge(_question):
        raise AssertionError("普通对话不应调用知识库查询工具。")

    result = asyncio.run(
        service.run_knowledge_chat(
            KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="你好"),
            fake_search_project_knowledge,
        )
    )

    assert result is output
    assert len(captured_tools) == 1
    assert captured_tools[0].__name__ == "search_project_knowledge"


def test_knowledge_chat_service_returns_final_message_when_structured_output_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.knowledge_chat import service

    class FakeMessage:
        content = "你好，我是项目知识库 AI。"

    class FakeAgent:
        async def ainvoke(self, _payload):
            return {"messages": [FakeMessage()]}

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "knowledge_chat_agent", lambda model, tools, **_kwargs: FakeAgent())

    async def fake_search_project_knowledge(_question):
        raise AssertionError("普通对话不应调用知识库查询工具。")

    result = asyncio.run(
        service.run_knowledge_chat(
            KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="你好"),
            fake_search_project_knowledge,
        )
    )

    assert result == KnowledgeQueryOutput(answer="你好，我是项目知识库 AI。", knowledge_queried=False)


def test_knowledge_chat_service_streams_answer_then_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.knowledge_chat import service

    output = KnowledgeQueryOutput(answer="你好，我是项目知识库 AI。", knowledge_queried=False)

    class FakeAgent:
        async def ainvoke(self, payload):
            assert "用户问题" in payload["messages"][0]["content"]
            return {"structured_response": output}

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "knowledge_chat_agent", lambda model, tools, **_kwargs: FakeAgent())

    async def fake_search_project_knowledge(_question):
        raise AssertionError("普通对话不应调用知识库查询工具。")

    async def collect_events():
        events = []
        async for event in service.stream_knowledge_chat(
            KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="你好"),
            fake_search_project_knowledge,
        ):
            events.append(event)
        return events

    events = asyncio.run(collect_events())

    assert events == [
        {"type": "message_delta", "delta": "你好，我是项目知识库 AI。"},
        {"type": "metadata", "output": output},
        {"type": "done"},
    ]


def test_knowledge_chat_service_streams_model_message_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.knowledge_chat import service

    output = KnowledgeQueryOutput(answer="你好，我是项目知识库 AI。", knowledge_queried=False)

    class FakeChunk:
        content = "你好，"

    class FakeAgent:
        async def astream(self, payload, **kwargs):
            assert kwargs["stream_mode"] == ["messages", "values"]
            yield ("messages", (FakeChunk(), {}))
            yield ("messages", ({"content": "我是项目知识库 AI。"}, {}))
            yield ("values", {"structured_response": output})

        async def ainvoke(self, _payload):
            raise AssertionError("支持 astream 时不应回退到 ainvoke。")

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "knowledge_chat_agent", lambda model, tools, **_kwargs: FakeAgent())

    async def fake_search_project_knowledge(_question):
        raise AssertionError("普通对话不应调用知识库查询工具。")

    async def collect_events():
        events = []
        async for event in service.stream_knowledge_chat(
            KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="你好"),
            fake_search_project_knowledge,
        ):
            events.append(event)
        return events

    events = asyncio.run(collect_events())

    assert events == [
        {"type": "message_delta", "delta": "你好，"},
        {"type": "message_delta", "delta": "我是项目知识库 AI。"},
        {"type": "metadata", "output": output},
        {"type": "done"},
    ]


def test_knowledge_chat_service_streams_plain_text_without_second_invoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.knowledge_chat import service

    class FakeAgent:
        async def astream(self, _payload, **_kwargs):
            yield ("messages", ({"content": "你好，"}, {}))
            yield ("messages", ({"content": "我在。"}, {}))
            yield ("values", {"messages": [{"content": "你好，我在。"}]})

        async def ainvoke(self, _payload):
            raise AssertionError("流式自然语言可用时不应回退到 ainvoke。")

    captured_structured_modes = []

    def fake_knowledge_chat_agent(model, tools, *, structured_output=True):
        captured_structured_modes.append(structured_output)
        return FakeAgent()

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "knowledge_chat_agent", fake_knowledge_chat_agent)

    async def fake_search_project_knowledge(_question):
        raise AssertionError("普通对话不应调用知识库查询工具。")

    async def collect_events():
        events = []
        async for event in service.stream_knowledge_chat(
            KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="你好"),
            fake_search_project_knowledge,
        ):
            events.append(event)
        return events

    events = asyncio.run(collect_events())

    assert captured_structured_modes == [False]
    assert events == [
        {"type": "message_delta", "delta": "你好，"},
        {"type": "message_delta", "delta": "我在。"},
        {
            "type": "metadata",
            "output": KnowledgeQueryOutput(answer="你好，我在。", knowledge_queried=False),
        },
        {"type": "done"},
    ]


def test_knowledge_chat_service_metadata_uses_complete_streamed_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.knowledge_chat import service

    class FakeAgent:
        async def astream(self, _payload, **_kwargs):
            yield ("messages", ({"content": "你好，"}, {}))
            yield ("values", {"messages": [{"content": "你好，"}]})
            yield ("messages", ({"content": "我在。"}, {}))

        async def ainvoke(self, _payload):
            raise AssertionError("流式自然语言可用时不应回退到 ainvoke。")

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "knowledge_chat_agent", lambda model, tools, **_kwargs: FakeAgent())

    async def fake_search_project_knowledge(_question):
        raise AssertionError("普通对话不应调用知识库查询工具。")

    async def collect_events():
        events = []
        async for event in service.stream_knowledge_chat(
            KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="你好"),
            fake_search_project_knowledge,
        ):
            events.append(event)
        return events

    events = asyncio.run(collect_events())

    assert events[-2] == {
        "type": "metadata",
        "output": KnowledgeQueryOutput(answer="你好，我在。", knowledge_queried=False),
    }


def test_knowledge_chat_service_falls_back_to_streamed_text_when_structured_output_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.knowledge_chat import service

    class FakeChunk:
        content = "你好，我是项目知识库 AI。"

    class FakeAgent:
        async def astream(self, _payload, **_kwargs):
            yield ("messages", (FakeChunk(), {}))
            raise ValueError("structured output parse failed")

        async def ainvoke(self, _payload):
            raise AssertionError("已有流式文本时不应回退到 ainvoke。")

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "knowledge_chat_agent", lambda model, tools, **_kwargs: FakeAgent())

    async def fake_search_project_knowledge(_question):
        raise AssertionError("普通对话不应调用知识库查询工具。")

    async def collect_events():
        events = []
        async for event in service.stream_knowledge_chat(
            KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="你好"),
            fake_search_project_knowledge,
        ):
            events.append(event)
        return events

    events = asyncio.run(collect_events())

    assert events[0] == {"type": "message_delta", "delta": "你好，我是项目知识库 AI。"}
    assert events[1]["type"] == "metadata"
    assert events[1]["output"] == KnowledgeQueryOutput(answer="你好，我是项目知识库 AI。", knowledge_queried=False)
    assert events[2] == {"type": "done"}


def test_knowledge_chat_service_uses_final_message_when_structured_output_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.knowledge_chat import service

    class FakeMessage:
        content = "你好，我是项目知识库 AI。"

    class FakeAgent:
        async def astream(self, _payload, **_kwargs):
            yield ("values", {"messages": [FakeMessage()]})

        async def ainvoke(self, _payload):
            raise AssertionError("最终消息可用时不应回退到 ainvoke。")

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "knowledge_chat_agent", lambda model, tools, **_kwargs: FakeAgent())

    async def fake_search_project_knowledge(_question):
        raise AssertionError("普通对话不应调用知识库查询工具。")

    async def collect_events():
        events = []
        async for event in service.stream_knowledge_chat(
            KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="你好"),
            fake_search_project_knowledge,
        ):
            events.append(event)
        return events

    events = asyncio.run(collect_events())

    assert events == [
        {"type": "message_delta", "delta": "你好，我是项目知识库 AI。"},
        {
            "type": "metadata",
            "output": KnowledgeQueryOutput(answer="你好，我是项目知识库 AI。", knowledge_queried=False),
        },
        {"type": "done"},
    ]


def test_knowledge_chat_service_does_not_stream_structured_json_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.knowledge_chat import service

    output = KnowledgeQueryOutput(answer="你好！我在，可以帮你查询项目需求。", knowledge_queried=False)

    class FakeAgent:
        async def astream(self, _payload, **_kwargs):
            yield ("messages", ({"content": '{"answer":"你好！我在，可以帮你查询项目需求。",' }, {}))
            yield ("messages", ({"content": '"knowledge_queried":false,"source_refs":[]}'}, {}))
            yield ("values", {"structured_response": output})

        async def ainvoke(self, _payload):
            raise AssertionError("支持 astream 时不应回退到 ainvoke。")

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "knowledge_chat_agent", lambda model, tools, **_kwargs: FakeAgent())

    async def fake_search_project_knowledge(_question):
        raise AssertionError("普通对话不应调用知识库查询工具。")

    async def collect_events():
        events = []
        async for event in service.stream_knowledge_chat(
            KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="你好"),
            fake_search_project_knowledge,
        ):
            events.append(event)
        return events

    events = asyncio.run(collect_events())

    assert events == [
        {"type": "message_delta", "delta": "你好！我在，可以帮你查询项目需求。"},
        {"type": "metadata", "output": output},
        {"type": "done"},
    ]
