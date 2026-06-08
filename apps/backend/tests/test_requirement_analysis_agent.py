import pytest


class FakeStructuredModel:
    def __init__(self, response):
        self.response = response
        self.messages = None

    async def ainvoke(self, messages):
        self.messages = messages
        return self.response


class FakeModel:
    def __init__(self, response):
        self.response = response
        self.schema = None
        self.structured_model = FakeStructuredModel(response)

    def with_structured_output(self, schema):
        self.schema = schema
        return self.structured_model


class FakeAgent:
    def __init__(self, response):
        self.response = response
        self.payload = None

    async def ainvoke(self, payload):
        self.payload = payload
        return {"structured_response": self.response}


def test_requirement_analysis_input_is_primary_only():
    from app.agents.requirement_analysis.primary_analysis.service import _build_requirement_analysis_input
    from app.schemas.requirement_analysis import RequirementAnalysisInput

    prompt = _build_requirement_analysis_input(
        RequirementAnalysisInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            primary_mapping_id="main-1",
            primary_filename="main.md",
            primary_markdown_content="# 主需求\n\n用户可以使用验证码登录。",
        )
    )

    assert "primary_markdown_content" in prompt
    assert "用户可以使用验证码登录" in prompt
    assert "requirement-review" in prompt
    assert "test-scenarios" in prompt
    assert "不要生成、优化、摘要或改写需求正文" in prompt
    assert "系统会直接使用 primary_markdown_content 原文作为初步需求" in prompt
    assert "search_auxiliary_documents" not in prompt
    assert '"auxiliary_documents"' not in prompt
    assert '"markdown_content"' not in prompt


def test_requirement_analysis_input_contract_only_contains_primary_fields():
    from app.schemas.requirement_analysis import RequirementAnalysisInput

    assert set(RequirementAnalysisInput.model_fields) == {
        "project_id",
        "document_id",
        "document_name",
        "primary_mapping_id",
        "primary_filename",
        "primary_markdown_content",
    }


@pytest.mark.anyio
async def test_requirement_analysis_service_uses_direct_structured_primary_model(monkeypatch):
    from app.agents.requirement_analysis.primary_analysis import service
    from app.schemas.requirement_analysis import RequirementAnalysisInput, RequirementAnalysisOutput, RequirementQualityGate

    response = RequirementAnalysisOutput(
        status="completed",
        analysis_summary="需求分析完成。",
        preliminary_requirement_markdown="# 主需求\n\n用户可以使用验证码登录。",
        quality_gate=RequirementQualityGate(result="passed", testability_score=90),
    )
    fake_agent = FakeAgent(response)

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: {"model": "fake:model"})
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "primary_analysis_agent", lambda model: fake_agent)

    output = await service.analyze_requirement(
        RequirementAnalysisInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            primary_mapping_id="main-1",
            primary_filename="main.md",
            primary_markdown_content="# 主需求\n\n用户可以使用验证码登录。",
        )
    )

    assert output.status == "completed"
    message_content = fake_agent.payload["messages"][0]["content"]
    assert "primary_markdown_content" in message_content
    assert "requirement-review" in message_content
    assert "test-scenarios" in message_content
    assert "search_auxiliary_documents" not in message_content


@pytest.mark.anyio
async def test_requirement_analysis_service_uses_primary_markdown_as_preliminary_requirement(monkeypatch):
    from app.agents.requirement_analysis.primary_analysis import service
    from app.schemas.requirement_analysis import RequirementAnalysisInput, RequirementAnalysisOutput, RequirementQualityGate

    response = RequirementAnalysisOutput(
        status="needs_clarification",
        analysis_summary="需求存在待澄清项。",
        preliminary_requirement_markdown="",
        quality_gate=RequirementQualityGate(result="warning", testability_score=72),
    )
    fake_agent = FakeAgent(response)

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: {"model": "fake:model"})
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "primary_analysis_agent", lambda model: fake_agent)

    primary_markdown = "# 主需求\n\n## 登录\n\n用户可以使用验证码登录。\n\n| 字段 | 说明 |\n| --- | --- |\n| 手机号 | 必填 |\n"
    output = await service.analyze_requirement(
        RequirementAnalysisInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            primary_mapping_id="main-1",
            primary_filename="main.md",
            primary_markdown_content=primary_markdown,
        )
    )

    assert output.preliminary_requirement_markdown == primary_markdown.strip()


def test_primary_analysis_agent_uses_tool_strategy(monkeypatch):
    from langchain.agents.structured_output import ToolStrategy

    from app.agents.requirement_analysis.primary_analysis.agent import primary_analysis_agent
    from app.schemas.requirement_analysis import RequirementAnalysisOutput

    calls = {}

    def fake_create_agent(model, tools, *, system_prompt, response_format):
        calls.update(
            {
                "model": model,
                "tools": tools,
                "system_prompt": system_prompt,
                "response_format": response_format,
            }
        )
        return "agent"

    monkeypatch.setattr(
        "app.agents.requirement_analysis.primary_analysis.agent.create_agent",
        fake_create_agent,
    )

    agent = primary_analysis_agent("model")

    assert agent == "agent"
    assert calls["model"] == "model"
    assert calls["tools"] == []
    assert isinstance(calls["response_format"], ToolStrategy)
    assert calls["response_format"].schema is RequirementAnalysisOutput
    assert calls["response_format"].handle_errors is True
    assert "主需求分析智能体" in calls["system_prompt"]


@pytest.mark.anyio
async def test_requirement_analysis_service_rejects_missing_structured_response(monkeypatch):
    from app.agents.requirement_analysis.primary_analysis import service
    from app.schemas.requirement_analysis import RequirementAnalysisInput

    class MissingStructuredResponseAgent:
        async def ainvoke(self, payload):
            return {}

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: {"model": "fake:model"})
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "primary_analysis_agent", lambda model: MissingStructuredResponseAgent())

    with pytest.raises(ValueError, match="未返回结构化结果"):
        await service.analyze_requirement(
            RequirementAnalysisInput(
                project_id="project-1",
                document_id="doc-1",
                document_name="登录需求",
                primary_mapping_id="main-1",
                primary_filename="main.md",
                primary_markdown_content="# 主需求\n\n用户可以使用验证码登录。",
            )
        )


def test_auxiliary_enhancement_input_contains_questions_and_articles():
    from app.agents.requirement_analysis.auxiliary_enhancement.service import _build_auxiliary_enhancement_input
    from app.schemas.requirement_analysis import (
        RequirementAuxiliaryArticleForEnhancement,
        RequirementAuxiliaryEnhancementInput,
        RequirementEnhancementQuestion,
    )

    prompt = _build_auxiliary_enhancement_input(
        RequirementAuxiliaryEnhancementInput(
            project_id="project-1",
            document_id="doc-1",
            analysis_id="analysis-1",
            primary_mapping_id="main-1",
            primary_filename="main.md",
            questions=[
                RequirementEnhancementQuestion(
                    id="q-1",
                    question="验证码有效期是多少？",
                    primary_excerpt="用户可以使用验证码登录。",
                )
            ],
            auxiliary_articles=[
                RequirementAuxiliaryArticleForEnhancement(
                    mapping_id="supporting-1",
                    filename="supporting.md",
                    markdown_content="# 辅助需求\n\n验证码有效期为 5 分钟。",
                )
            ],
        )
    )

    assert "questions" in prompt
    assert "auxiliary_articles" in prompt
    assert "验证码有效期是多少" in prompt
    assert "supporting.md" in prompt
    assert "验证码有效期为 5 分钟" in prompt
    assert "search_auxiliary_documents" not in prompt


@pytest.mark.anyio
async def test_auxiliary_enhancement_service_uses_direct_structured_model(monkeypatch):
    from app.agents.requirement_analysis.auxiliary_enhancement import service
    from app.schemas.requirement_analysis import (
        RequirementAuxiliaryArticleForEnhancement,
        RequirementAuxiliaryEnhancementInput,
        RequirementAuxiliaryEnhancementOutput,
        RequirementEnhancementQuestion,
    )

    response = RequirementAuxiliaryEnhancementOutput(
        enhancement_summary="从辅助文档找到验证码有效期。",
        unchanged_question_ids=[],
    )
    fake_agent = FakeAgent(response)

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: {"model": "fake:model"})
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "auxiliary_enhancement_agent", lambda model: fake_agent)

    output = await service.enhance_requirement_with_auxiliary_articles(
        RequirementAuxiliaryEnhancementInput(
            project_id="project-1",
            document_id="doc-1",
            analysis_id="analysis-1",
            questions=[RequirementEnhancementQuestion(id="q-1", question="验证码有效期是多少？")],
            auxiliary_articles=[
                RequirementAuxiliaryArticleForEnhancement(
                    mapping_id="supporting-1",
                    filename="supporting.md",
                    markdown_content="# 辅助需求\n\n验证码有效期为 5 分钟。",
                )
            ],
        )
    )

    assert output.enhancement_summary == "从辅助文档找到验证码有效期。"
    message_content = fake_agent.payload["messages"][0]["content"]
    assert "auxiliary_articles" in message_content
    assert "验证码有效期为 5 分钟" in message_content


def test_auxiliary_enhancement_agent_uses_tool_strategy(monkeypatch):
    from langchain.agents.structured_output import ToolStrategy

    from app.agents.requirement_analysis.auxiliary_enhancement.agent import auxiliary_enhancement_agent
    from app.schemas.requirement_analysis import RequirementAuxiliaryEnhancementOutput

    calls = {}

    def fake_create_agent(model, tools, *, system_prompt, response_format):
        calls.update(
            {
                "model": model,
                "tools": tools,
                "system_prompt": system_prompt,
                "response_format": response_format,
            }
        )
        return "agent"

    monkeypatch.setattr(
        "app.agents.requirement_analysis.auxiliary_enhancement.agent.create_agent",
        fake_create_agent,
    )

    agent = auxiliary_enhancement_agent("model")

    assert agent == "agent"
    assert calls["model"] == "model"
    assert calls["tools"] == []
    assert isinstance(calls["response_format"], ToolStrategy)
    assert calls["response_format"].schema is RequirementAuxiliaryEnhancementOutput
    assert calls["response_format"].handle_errors is True
    assert "辅助文档增强智能体" in calls["system_prompt"]
