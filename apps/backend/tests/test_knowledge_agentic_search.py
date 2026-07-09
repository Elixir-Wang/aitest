import asyncio

from app.agents.knowledge.schemas import KnowledgeQueryInput, KnowledgeQueryOutput, KnowledgeSourceDocumentInput


def test_knowledge_agent_prompt_has_consolidated_source_rules():
    from app.agents.knowledge.agent import SYSTEM_PROMPT

    assert "7. 如果未读取 /requirements/ 或 /company-knowledge/" in SYSTEM_PROMPT
    assert "8. 如果读取了 /requirements/，必须在 used_requirement_versions 中返回实际使用过的需求版本 ID。" in SYSTEM_PROMPT
    assert "9. 如果读取了 /company-knowledge/，必须在 used_company_knowledge_files 中返回实际使用过的公司知识库文件 ID。" in SYSTEM_PROMPT
    assert "10. 参考来源写入 answer 正文末尾，不再单独返回结构化来源字段。" in SYSTEM_PROMPT
    assert "回答必须使用 Markdown 格式，并在回答末尾追加" in SYSTEM_PROMPT
    assert "- [需求] 项目名 / 需求标题" in SYSTEM_PROMPT
    assert "- [知识库] 知识库名 / 文件标题" in SYSTEM_PROMPT
    assert "问题宽泛时，优先回答最小可用流程和关键必填项" in SYSTEM_PROMPT
    assert "简洁步骤" in SYSTEM_PROMPT
    assert "完整说明" in SYSTEM_PROMPT
    assert "排障" in SYSTEM_PROMPT
    assert "最佳实践" in SYSTEM_PROMPT
    assert "不要为了覆盖所有命中文档而输出百科式答案" in SYSTEM_PROMPT
    assert "参考来源只列实际支撑核心答案的文档，优先列 3 个以内，最多 5 个" in SYSTEM_PROMPT
    assert "这不是知识库查询" in SYSTEM_PROMPT
    assert "不得回答“知识库内未查询到相关结果”" in SYSTEM_PROMPT
    assert "只有当用户询问项目事实/公司知识且已尝试查询仍没有依据时" in SYSTEM_PROMPT
    assert "不得基于文件名、路径或常识补全业务事实或参考来源" in SYSTEM_PROMPT
    assert "不得包含 <think>、思考过程、工具调用计划、检索过程描述" in SYSTEM_PROMPT
    assert "10. 如果没有读取知识库" not in SYSTEM_PROMPT
    assert "15. 不要把" not in SYSTEM_PROMPT


def test_knowledge_agent_uses_tool_strategy_for_structured_output(monkeypatch) -> None:
    from langchain.agents.structured_output import ToolStrategy

    from app.agents.knowledge.agent import knowledge_agent

    captured = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return "agent"

    monkeypatch.setattr("app.agents.knowledge.agent.create_deep_agent", fake_create_deep_agent)

    agent = knowledge_agent("model")

    assert agent == "agent"
    assert captured["model"] == "model"
    assert isinstance(captured["response_format"], ToolStrategy)
    assert captured["response_format"].schema is KnowledgeQueryOutput
    assert captured["response_format"].handle_errors is True


def test_knowledge_agent_service_runs_single_deepagent(monkeypatch):
    from app.agents.knowledge import service
    from app.agents.model_selection import ModelSelection

    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload, config=None):
            captured["payload"] = payload
            captured["config"] = config
            return {"structured_response": KnowledgeQueryOutput(answer="已查询。", knowledge_queried=True)}

    monkeypatch.setattr(
        service,
        "resolve_model_selection",
        lambda _capability_id: ModelSelection(
            provider="Minimax",
            model="MiniMax-M3",
            base_url="https://minimax.example/v1",
            api_key="sk-test",
        ),
    )
    monkeypatch.setattr(service, "build_agent_model", lambda _selection, **_kwargs: "model")
    monkeypatch.setattr(service, "knowledge_agent", lambda _model: FakeAgent())

    input_data = KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="登录规则是什么？")
    output = asyncio.run(service.run_knowledge_agent(input_data, thread_id="conversation-1"))

    assert captured["payload"]["messages"][0]["content"]
    assert captured["config"] == {"configurable": {"thread_id": "conversation-1"}}
    assert output.answer == "已查询。"


def test_knowledge_agent_payload_uses_virtual_files():
    from app.agents.knowledge import service

    input_data = KnowledgeQueryInput(
        project_id="project-1",
        project_name="测试项目",
        question="登录规则是什么？",
        source_documents=[
            KnowledgeSourceDocumentInput(
                project_id="project-1",
                project_name="测试项目",
                document_id="doc-1",
                document_name="最终需求",
                version_id="version-1",
                version_no=1,
                markdown_content="# 登录\n用户可以使用账号密码登录。",
            )
        ],
    )

    payload = service._agent_payload(input_data)
    user_content = payload["messages"][0]["content"]

    assert "files" in payload
    assert "最近对话上下文" not in user_content
    assert "项目：" not in user_content
    assert "project-1" not in user_content
    assert "测试项目" not in user_content
    assert "/README.md" in payload["files"]
    assert any(path.startswith("/requirements/") for path in payload["files"])
    file_data = next(value for key, value in payload["files"].items() if key.startswith("/requirements/"))
    content = file_data["content"]
    assert "source_metadata" in content
    assert "version-1" in content
    assert "用户可以使用账号密码登录" in content


def test_knowledge_agent_payload_uses_company_knowledge_virtual_files():
    from app.agents.knowledge import service

    input_data = KnowledgeQueryInput(
        project_id="project-1",
        project_name="测试项目",
        question="登录测试怎么设计？",
        source_documents=[
            KnowledgeSourceDocumentInput(
                source_type="company_knowledge",
                source_id="gkfile-1",
                source_title="测试规范 / 登录测试.md",
                base_id="gkb-1",
                base_name="测试规范",
                folder_path="功能测试",
                file_id="gkfile-1",
                file_name="登录测试.md",
                markdown_content="# 登录测试\n覆盖成功、失败和锁定。",
            )
        ],
    )

    payload = service._agent_payload(input_data)

    assert any(path.startswith("/company-knowledge/") for path in payload["files"])
    file_data = next(value for key, value in payload["files"].items() if key.startswith("/company-knowledge/"))
    content = file_data["content"]
    assert '"source_type": "company_knowledge"' in content
    assert "覆盖成功、失败和锁定" in content


def test_knowledge_agent_disables_model_thinking_by_default(monkeypatch):
    from app.agents.knowledge import service
    from app.agents.model_selection import ModelSelection

    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload, config=None):
            return {"structured_response": KnowledgeQueryOutput(answer="已查询。", knowledge_queried=True)}

    def fake_build_agent_model(selection, *, extra_body=None):
        captured["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr(
        service,
        "resolve_model_selection",
        lambda _capability_id: ModelSelection(
            provider="Minimax",
            model="MiniMax-M3",
            base_url="https://minimax.example/v1",
            api_key="sk-test",
        ),
    )
    monkeypatch.setattr(service, "build_agent_model", fake_build_agent_model)
    monkeypatch.setattr(service, "knowledge_agent", lambda _model: FakeAgent())

    input_data = KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="登录规则是什么？")
    asyncio.run(service.run_knowledge_agent(input_data))

    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}


def test_knowledge_agent_disables_deepseek_thinking_by_default(monkeypatch):
    from app.agents.knowledge import service
    from app.agents.model_selection import ModelSelection

    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload, config=None):
            return {"structured_response": KnowledgeQueryOutput(answer="已查询。", knowledge_queried=True)}

    def fake_build_agent_model(selection, *, extra_body=None):
        captured["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr(
        service,
        "resolve_model_selection",
        lambda _capability_id: ModelSelection(
            provider="deepseek",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            api_key="sk-test",
        ),
    )
    monkeypatch.setattr(service, "build_agent_model", fake_build_agent_model)
    monkeypatch.setattr(service, "knowledge_agent", lambda _model: FakeAgent())

    input_data = KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="登录规则是什么？")
    asyncio.run(service.run_knowledge_agent(input_data))

    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}


def test_knowledge_agent_does_not_send_thinking_body_to_unknown_provider(monkeypatch):
    from app.agents.knowledge import service
    from app.agents.model_selection import ModelSelection

    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload, config=None):
            return {"structured_response": KnowledgeQueryOutput(answer="已查询。", knowledge_queried=True)}

    def fake_build_agent_model(selection, *, extra_body=None):
        captured["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr(
        service,
        "resolve_model_selection",
        lambda _capability_id: ModelSelection(
            provider="openai-compatible",
            model="other-model",
            base_url="https://example.test/v1",
            api_key="sk-test",
        ),
    )
    monkeypatch.setattr(service, "build_agent_model", fake_build_agent_model)
    monkeypatch.setattr(service, "knowledge_agent", lambda _model: FakeAgent())

    input_data = KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="登录规则是什么？")
    asyncio.run(service.run_knowledge_agent(input_data))

    assert captured["extra_body"] is None


def test_stream_knowledge_agent_filters_tool_messages_and_thinking_noise(monkeypatch):
    from app.agents.knowledge import service
    captured = {}

    class FakeAgent:
        async def astream(self, payload, *, config=None, stream_mode):
            captured["config"] = config
            yield (
                "messages",
                (
                    {
                        "type": "tool",
                        "content": '<!-- source_metadata: {"source_id":"gkfile-1"} -->\n1 # 文档原文',
                    },
                ),
            )
            yield (
                "messages",
                (
                    {
                        "type": "ai",
                        "content": "",
                        "additional_kwargs": {
                            "reasoning_content": '<!-- source_metadata: {"source_id":"gkfile-1"} -->\n1 先判断来源。',
                        },
                    },
                ),
            )
            yield ("messages", ({"type": "ai", "content": "结论来自知识库。"},))
            yield (
                "values",
                {
                    "structured_response": KnowledgeQueryOutput(answer="结论来自知识库。", knowledge_queried=True),
                },
            )

    monkeypatch.setattr(service, "resolve_model_selection", lambda _capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda _selection, **_kwargs: "model")
    monkeypatch.setattr(service, "knowledge_agent", lambda _model: FakeAgent())

    input_data = KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="登录规则是什么？")
    events = asyncio.run(_collect_events(service.stream_knowledge_agent(input_data, show_thinking=True, thread_id="conversation-1")))

    assert captured["config"] == {"configurable": {"thread_id": "conversation-1"}}
    assert {"type": "thinking_delta", "delta": "先判断来源。"} in events
    assert {"type": "message_delta", "delta": "结论来自知识库。"} in events
    assert all("source_metadata" not in str(event) for event in events)


def test_stream_knowledge_agent_can_fallback_to_think_blocks(monkeypatch) -> None:
    from app.agents.knowledge import service

    class FakeAgent:
        async def astream(self, payload, *, config=None, stream_mode):
            yield (
                "messages",
                (
                    {
                        "type": "assistant",
                        "content": "<think>先判断来源。</think>最终答案。",
                    },
                ),
            )
            yield (
                "values",
                {
                    "structured_response": KnowledgeQueryOutput(answer="最终答案。", knowledge_queried=True),
                },
            )

    monkeypatch.setattr(service, "resolve_model_selection", lambda _capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda _selection, **_kwargs: "model")
    monkeypatch.setattr(service, "knowledge_agent", lambda _model: FakeAgent())

    input_data = KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="登录规则是什么？")
    events = asyncio.run(_collect_events(service.stream_knowledge_agent(input_data, show_thinking=True, thread_id="conversation-1")))

    assert {"type": "thinking_delta", "delta": "先判断来源。"} in events
    assert {"type": "message_delta", "delta": "最终答案。"} in events


def test_stream_knowledge_agent_keeps_answer_streaming_when_thinking_enabled(monkeypatch) -> None:
    from app.agents.knowledge import service

    class FakeAgent:
        async def astream(self, payload, *, config=None, stream_mode):
            yield (
                "messages",
                (
                    {
                        "type": "assistant",
                        "content": "<think>先判断来源。</think>答案前缀",
                    },
                ),
            )
            yield (
                "messages",
                (
                    {
                        "type": "assistant",
                        "content": "继续输出。",
                    },
                ),
            )
            yield (
                "values",
                {
                    "structured_response": KnowledgeQueryOutput(answer="答案前缀继续输出。", knowledge_queried=True),
                },
            )

    monkeypatch.setattr(service, "resolve_model_selection", lambda _capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda _selection, **_kwargs: "model")
    monkeypatch.setattr(service, "knowledge_agent", lambda _model: FakeAgent())

    input_data = KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="登录规则是什么？")
    events = asyncio.run(_collect_events(service.stream_knowledge_agent(input_data, show_thinking=True, thread_id="conversation-1")))

    assert {"type": "thinking_delta", "delta": "先判断来源。"} in events
    assert {"type": "message_delta", "delta": "答案前缀"} in events
    assert {"type": "message_delta", "delta": "继续输出。"} in events


async def _collect_events(stream):
    return [event async for event in stream]
