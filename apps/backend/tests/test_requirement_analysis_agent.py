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


def test_requirement_analysis_input_is_primary_only():
    from app.agents.requirement_analysis.service import _build_requirement_analysis_input
    from app.schemas.requirement_analysis import RequirementAnalysisInput, RequirementAuxiliaryDocument

    prompt = _build_requirement_analysis_input(
        RequirementAnalysisInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            primary_mapping_id="main-1",
            primary_filename="main.md",
            primary_markdown_content="# 主需求\n\n用户可以使用验证码登录。",
            markdown_content="# 主需求\n\n用户可以使用验证码登录。",
            auxiliary_documents=[
                RequirementAuxiliaryDocument(
                    mapping_id="supporting-1",
                    filename="supporting.md",
                    markdown_content="# 辅助需求\n\n验证码有效期为 5 分钟。",
                )
            ],
        )
    )

    assert "primary_markdown_content" in prompt
    assert "用户可以使用验证码登录" in prompt
    assert "supporting.md" not in prompt
    assert "search_auxiliary_documents" not in prompt
    assert "验证码有效期为 5 分钟" not in prompt
    assert '"auxiliary_documents"' not in prompt
    assert '"markdown_content"' not in prompt


@pytest.mark.anyio
async def test_requirement_analysis_service_uses_direct_structured_primary_model(monkeypatch):
    from app.agents.requirement_analysis import service
    from app.schemas.requirement_analysis import RequirementAnalysisInput, RequirementAnalysisOutput, RequirementQualityGate

    response = RequirementAnalysisOutput(
        status="completed",
        analysis_summary="需求分析完成。",
        preliminary_requirement_markdown="# 主需求\n\n用户可以使用验证码登录。",
        quality_gate=RequirementQualityGate(result="passed", testability_score=90),
    )
    fake_model = FakeModel(response)

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: {"model": "fake:model"})
    monkeypatch.setattr(service, "build_agent_model", lambda selection: fake_model)

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
    assert fake_model.schema is RequirementAnalysisOutput
    message_content = fake_model.structured_model.messages[1].content
    assert "primary_markdown_content" in message_content
    assert "search_auxiliary_documents" not in message_content


def test_auxiliary_enhancement_input_contains_questions_and_articles():
    from app.agents.requirement_analysis.service import _build_auxiliary_enhancement_input
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
    from app.agents.requirement_analysis import service
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
    fake_model = FakeModel(response)

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: {"model": "fake:model"})
    monkeypatch.setattr(service, "build_agent_model", lambda selection: fake_model)

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
    assert fake_model.schema is RequirementAuxiliaryEnhancementOutput
    message_content = fake_model.structured_model.messages[1].content
    assert "auxiliary_articles" in message_content
    assert "验证码有效期为 5 分钟" in message_content
