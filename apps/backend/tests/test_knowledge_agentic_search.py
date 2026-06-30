import asyncio

from app.agents.knowledge.schemas import KnowledgeQueryInput, KnowledgeQueryOutput, KnowledgeSourceDocumentInput


def test_knowledge_agent_prompt_has_consolidated_source_rules():
    from app.agents.knowledge.prompts import SYSTEM_PROMPT

    assert "7. 如果未读取 /requirements/ 或 /company-knowledge/" in SYSTEM_PROMPT
    assert "8. 如果读取了 /requirements/，必须在 used_requirement_versions 中返回实际使用过的需求版本 ID。" in SYSTEM_PROMPT
    assert "9. 如果读取了 /company-knowledge/，必须在 used_company_knowledge_files 中返回实际使用过的公司知识库文件 ID。" in SYSTEM_PROMPT
    assert "10. source_refs 只能引用已读取文件顶部 source_metadata 中的字段，且必须填写 location 与 excerpt。" in SYSTEM_PROMPT
    assert "不得基于文件名、路径或常识补全业务事实或 source_refs" in SYSTEM_PROMPT
    assert "不得包含 <think>、思考过程、工具调用计划、检索过程描述" in SYSTEM_PROMPT
    assert "10. 如果没有读取知识库" not in SYSTEM_PROMPT
    assert "15. 不要把" not in SYSTEM_PROMPT


def test_knowledge_agent_service_runs_single_deepagent(monkeypatch):
    from app.agents.knowledge import service

    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            captured["payload"] = payload
            return {"structured_response": KnowledgeQueryOutput(answer="已查询。", knowledge_queried=True)}

    monkeypatch.setattr(service, "resolve_model_selection", lambda _capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda _selection, **_kwargs: "model")
    monkeypatch.setattr(service, "knowledge_agent", lambda _model: FakeAgent())

    input_data = KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="登录规则是什么？")
    output = asyncio.run(service.run_knowledge_agent(input_data))

    assert captured["payload"]["messages"][0]["content"]
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

    assert "files" in payload
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

    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            return {"structured_response": KnowledgeQueryOutput(answer="已查询。", knowledge_queried=True)}

    def fake_build_agent_model(selection, *, extra_body=None):
        captured["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr(service, "resolve_model_selection", lambda _capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", fake_build_agent_model)
    monkeypatch.setattr(service, "knowledge_agent", lambda _model: FakeAgent())

    input_data = KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="登录规则是什么？")
    asyncio.run(service.run_knowledge_agent(input_data))

    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}


def test_stream_knowledge_agent_filters_tool_messages_and_thinking_noise(monkeypatch):
    from app.agents.knowledge import service

    class FakeAgent:
        async def astream(self, payload, stream_mode):
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
            yield {
                "structured_response": KnowledgeQueryOutput(answer="结论来自知识库。", knowledge_queried=True),
            }

    monkeypatch.setattr(service, "resolve_model_selection", lambda _capability_id: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda _selection, **_kwargs: "model")
    monkeypatch.setattr(service, "knowledge_agent", lambda _model: FakeAgent())

    input_data = KnowledgeQueryInput(project_id="project-1", project_name="测试项目", question="登录规则是什么？")
    events = asyncio.run(_collect_events(service.stream_knowledge_agent(input_data, show_thinking=True)))

    assert {"type": "thinking_delta", "delta": "先判断来源。"} in events
    assert {"type": "message_delta", "delta": "结论来自知识库。"} in events
    assert all("source_metadata" not in str(event) for event in events)


def test_sanitize_visible_answer_removes_structured_xml_tail():
    from app.agents.knowledge import service

    answer = (
        "<KnowledgeQueryOutput><answer>关于项目最终需求\n"
        "当前项目为“全部项目 (all-projects)”，/requirements/ 下未发现明确需求文档。"
        "</answer> <source_refs> <item> <source_type>company_knowledge</source_type>"
        "<source_id>gkfile-8e685279cb75fe79</source_id><excerpt>支持将智能体发布至钉钉平台。</excerpt>"
        "</item> </source_refs> <used_requirement_versions>]<]minimax[>[</used_requirement_versions>"
        "<used_company_knowledge_files><item>gkfile-8e685279cb75fe79]<]minimax[>[</item></used_company_knowledge_files>"
        "<knowledge_queried>true]<]minimax[>[</knowledge_queried></KnowledgeQueryOutput>"
    )

    assert service.sanitize_visible_answer(answer) == "当前项目为“全部项目 (all-projects)”，/requirements/ 下未发现明确需求文档。"


def test_think_block_filter_stops_streaming_structured_xml_tail():
    from app.agents.knowledge import service

    visible_filter = service.ThinkBlockFilter()

    deltas = [
        visible_filter.feed("<KnowledgeQueryOutput><answer>"),
        visible_filter.feed("当前项目未发现明确需求文档。"),
        visible_filter.feed("</answer> <source_refs>"),
        visible_filter.feed("<item>不应显示</item></source_refs>"),
    ]

    assert deltas == ["", "当前项目未发现明确需求文档。", "", ""]


async def _collect_events(stream):
    return [event async for event in stream]
