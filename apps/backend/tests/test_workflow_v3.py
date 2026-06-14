"""
需求分析 LangGraph 端到端集成测试
"""

import pytest
from app.agents.requirement_analysis.schemas import (
    RequirementAnalysisInputV2,
    AuxiliaryDocument,
)


@pytest.mark.anyio
async def test_requirement_analysis_end_to_end(monkeypatch):
    """端到端测试：LangGraph 完整流程"""

    # Mock LLM 和各个 Agent（避免实际调用 API）
    from app.agents.requirement_analysis.schemas import (
        RequirementUnderstandingOutput,
        QualityAssessmentOutput,
        QualityScores,
        QualityDecision,
        CompletenessAssessment,
        ClarityAssessment,
        TestabilityAssessment,
        ConsistencyAssessment,
        FuzzyTerm,
    )

    # Mock 需求理解
    async def mock_understand(model, primary_markdown_content):
        return RequirementUnderstandingOutput(
            modules=[],
            dependencies=[],
            risks=[],
            assumptions=[],
            understanding_summary="需求理解完成"
        )

    # Mock 质量评估
    async def mock_quality(model, primary_markdown_content, understanding_result):
        return QualityAssessmentOutput(
            scores=QualityScores(
                completeness=85,
                clarity=75,
                testability=80,
                consistency=90,
                overall=82
            ),
            decision=QualityDecision(
                result="conditional",
                rationale="需要澄清部分模糊词",
                blocking_issues=[],
                recommended_actions=["澄清模糊词"]
            ),
            completeness=CompletenessAssessment(score=85),
            clarity=ClarityAssessment(
                score=75,
                fuzzy_terms=[
                    FuzzyTerm(
                        term="快速",
                        location="登录模块",
                        current_text="系统需要快速响应",
                        issue="未定义具体时间",
                        suggested_fix="系统响应时间 < 2秒"
                    )
                ]
            ),
            testability=TestabilityAssessment(score=80),
            consistency=ConsistencyAssessment(score=90),
            assessment_summary="质量评估完成"
        )

    monkeypatch.setattr(
        "app.agents.requirement_analysis.nodes.understand_node.run_understanding_agent",
        mock_understand
    )
    monkeypatch.setattr(
        "app.agents.requirement_analysis.nodes.quality_node.run_quality_assessment_agent",
        mock_quality
    )
    monkeypatch.setattr(
        "app.agents.model_selection.resolve_model_selection",
        lambda capability_id: object()
    )
    monkeypatch.setattr(
        "app.agents.model_selection.build_agent_model",
        lambda model_selection: object()
    )

    # Mock 搜索服务
    async def mock_search(model, question, auxiliary_documents):
        if "快速" in question:
            return {
                "found": True,
                "answer": "【文档: 性能规范.md】\nAPI响应时间要求 < 2秒",
                "source": "性能规范.md",
                "confidence": "high",
                "search_steps": ["快速", "响应时间"]
            }
        return {
            "found": False,
            "answer": "",
            "source": "",
            "confidence": "none",
            "search_steps": []
        }

    monkeypatch.setattr(
        "app.agents.requirement_analysis.nodes.clarify_node.search_for_answer",
        mock_search
    )

    # 准备测试输入
    input_data = RequirementAnalysisInputV2(
        project_id="test-project",
        document_id="test-doc",
        document_name="登录需求",
        run_id="test-run-001",
        primary_mapping_id="primary",
        primary_filename="登录需求.md",
        primary_markdown_content="# 登录需求\n\n用户可以使用验证码快速登录。",
        auxiliary_documents=[
            AuxiliaryDocument(
                mapping_id="aux-1",
                filename="性能规范.md",
                document_type="standard",
                markdown_content="# 性能规范\n\nAPI响应时间要求 < 2秒"
            )
        ],
        config={}
    )

    # 执行 LangGraph 分析
    from app.agents.requirement_analysis.workflow import run_requirement_analysis

    result = await run_requirement_analysis(input_data)

    # 验证结果
    assert result.status in ["completed", "needs_clarification", "blocked"]
    assert result.understanding is not None
    assert result.quality_assessment is not None
    assert result.clarification is not None

    # 验证 Agentic Search 生效
    auto_resolved = [
        item for item in result.clarification.items
        if item.resolution_status == "auto_resolved"
    ]
    assert len(auto_resolved) > 0, "应该有自动解决的问题"

    # 验证搜索路径
    first_resolved = auto_resolved[0]
    assert first_resolved.evidence, "应该有证据"
    assert first_resolved.evidence[0].filename == "性能规范.md"

    # 验证元数据
    assert result.metadata["version"] == "3.0"
    assert result.metadata["engine"] == "langchain_langgraph"
    assert result.metadata["execution_time_ms"] > 0


def test_resolve_primary_source_excerpt_uses_real_primary_paragraph():
    """查看原文应返回主需求里的相关段落，而不是模型生成的缺口描述。"""
    from app.agents.requirement_analysis.nodes.clarify_node import (
        _resolve_primary_source_excerpt,
    )

    primary_content = """
# 登录需求

用户可以使用手机号和验证码登录系统。
验证码错误时，系统提示用户重新输入。

## 会话管理

登录成功后系统创建会话。
""".strip()
    question = {
        "title": "缺失非功能需求",
        "issue_type": "missing",
        "question": "缺少安全需求，需要定义什么指标？",
        "impact": "无法确认验证码安全策略",
        "source": "completeness",
        "current_text": "未定义验证码有效期、重试次数和锁定策略",
    }

    excerpt = _resolve_primary_source_excerpt(question, primary_content)

    assert "用户可以使用手机号和验证码登录系统。" in excerpt
    assert "未定义验证码有效期" not in excerpt


def test_resolve_primary_source_excerpt_expands_direct_match_to_paragraph():
    """质量评估给出短原文时，前端仍能看到完整相关段落。"""
    from app.agents.requirement_analysis.nodes.clarify_node import (
        _resolve_primary_source_excerpt,
    )

    primary_content = """
# 性能需求

系统需要快速响应，用户提交订单后应立即看到处理结果。
失败时需要展示可理解的错误提示。
""".strip()
    question = {
        "title": "模糊表述",
        "issue_type": "ambiguous",
        "question": "'快速' 的具体定义是什么？",
        "impact": "无法度量响应时间",
        "source": "clarity",
        "current_text": "系统需要快速响应",
    }

    excerpt = _resolve_primary_source_excerpt(question, primary_content)

    assert "系统需要快速响应，用户提交订单后应立即看到处理结果。" in excerpt
    assert "失败时需要展示可理解的错误提示。" in excerpt


def test_clarification_item_without_search_result_still_has_recommended_options():
    """无辅助文档命中时，也应给出可供前端展示和保存的两个候选答案。"""
    from app.agents.requirement_analysis.nodes.clarify_node import (
        _create_clarification_item,
    )

    item = _create_clarification_item(
        {
            "id": "FG-1",
            "title": "缺失功能",
            "issue_type": "missing",
            "question": "缺少performance需求，需要定义什么指标？",
            "impact": "无法评估系统是否能满足业务连续性要求",
            "severity": "major",
            "source": "completeness",
            "current_text": "performance需求未定义",
            "category": "performance",
        },
        {
            "found": False,
            "answer": "",
            "source": "",
            "confidence": "none",
            "search_steps": [],
        },
    )

    assert item.resolution_status == "has_suggestions"
    assert len(item.recommended_options) == 2
    assert item.recommended_options[0].option_id == "opt1"
    assert item.recommended_options[1].option_id == "opt2"
    assert "P95" in item.recommended_options[0].answer_markdown
    assert "QPS" in item.recommended_options[1].answer_markdown
    assert all("请业务确认" not in option.answer_markdown for option in item.recommended_options)
    assert all("暂不纳入" not in option.answer_markdown for option in item.recommended_options)


@pytest.mark.anyio
async def test_requirement_analysis_skip_clarification(monkeypatch):
    """测试高质量需求跳过澄清阶段"""

    from app.agents.requirement_analysis.schemas import (
        RequirementUnderstandingOutput,
        QualityAssessmentOutput,
        QualityScores,
        QualityDecision,
        CompletenessAssessment,
        ClarityAssessment,
        TestabilityAssessment,
        ConsistencyAssessment,
    )

    # Mock 需求理解
    async def mock_understand(model, primary_markdown_content):
        return RequirementUnderstandingOutput(
            modules=[],
            dependencies=[],
            risks=[],
            assumptions=[],
            understanding_summary="高质量需求"
        )

    # Mock 质量评估（高分 + approved）
    async def mock_quality_high(model, primary_markdown_content, understanding_result):
        return QualityAssessmentOutput(
            scores=QualityScores(
                completeness=98,
                clarity=97,
                testability=96,
                consistency=99,
                overall=97  # >= 95
            ),
            decision=QualityDecision(
                result="approved",  # approved
                rationale="需求质量优秀",
                blocking_issues=[],
                recommended_actions=[]
            ),
            completeness=CompletenessAssessment(score=98),
            clarity=ClarityAssessment(score=97, fuzzy_terms=[]),
            testability=TestabilityAssessment(score=96),
            consistency=ConsistencyAssessment(score=99),
            assessment_summary="质量优秀"
        )

    monkeypatch.setattr(
        "app.agents.requirement_analysis.nodes.understand_node.run_understanding_agent",
        mock_understand
    )
    monkeypatch.setattr(
        "app.agents.requirement_analysis.nodes.quality_node.run_quality_assessment_agent",
        mock_quality_high
    )
    monkeypatch.setattr(
        "app.agents.model_selection.resolve_model_selection",
        lambda capability_id: object()
    )
    monkeypatch.setattr(
        "app.agents.model_selection.build_agent_model",
        lambda model_selection: object()
    )

    async def fail_if_search_called(model, question, auxiliary_documents):
        raise AssertionError("高质量需求应跳过澄清搜索")

    monkeypatch.setattr(
        "app.agents.requirement_analysis.nodes.clarify_node.search_for_answer",
        fail_if_search_called
    )

    # 准备输入
    input_data = RequirementAnalysisInputV2(
        project_id="test-project",
        document_id="test-doc",
        document_name="完善的需求",
        primary_mapping_id="primary",
        primary_filename="需求.md",
        primary_markdown_content="# 完善的需求\n\n所有细节都很清晰。",
        auxiliary_documents=[],
        config={}
    )

    # 执行
    from app.agents.requirement_analysis.workflow import run_requirement_analysis
    result = await run_requirement_analysis(input_data)

    # 验证：应该跳过澄清阶段（clarification.items 为空或自动生成）
    assert result.status == "completed"
    assert result.quality_assessment.scores.overall >= 95
    assert result.quality_assessment.decision.result == "approved"
    assert result.clarification is not None
    assert result.clarification.items == []
    assert result.clarification.summary.total == 0
    assert result.clarification.summary.needs_manual == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
