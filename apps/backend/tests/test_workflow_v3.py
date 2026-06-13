"""
需求分析 v3.0 端到端集成测试
"""

import pytest
from app.agents.requirement_analysis.schemas_v2 import (
    RequirementAnalysisInputV2,
    AuxiliaryDocument,
)


@pytest.mark.anyio
async def test_requirement_analysis_v3_end_to_end(monkeypatch):
    """端到端测试：v3.0 完整流程"""

    # Mock LLM 和各个 Agent（避免实际调用 API）
    from app.agents.requirement_analysis.schemas_v2 import (
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
        "app.agents.requirement_analysis.v3.nodes.understand_node.run_understanding_agent",
        mock_understand
    )
    monkeypatch.setattr(
        "app.agents.requirement_analysis.v3.nodes.quality_node.run_quality_assessment_agent",
        mock_quality
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
        "app.agents.requirement_analysis.v3.nodes.clarify_node.search_for_answer",
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

    # 执行 v3.0 分析
    from app.agents.requirement_analysis.v3.workflow import run_requirement_analysis_v3

    result = await run_requirement_analysis_v3(input_data)

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


@pytest.mark.anyio
async def test_requirement_analysis_v3_skip_clarification(monkeypatch):
    """测试高质量需求跳过澄清阶段"""

    from app.agents.requirement_analysis.schemas_v2 import (
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
        "app.agents.requirement_analysis.v3.nodes.understand_node.run_understanding_agent",
        mock_understand
    )
    monkeypatch.setattr(
        "app.agents.requirement_analysis.v3.nodes.quality_node.run_quality_assessment_agent",
        mock_quality_high
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
    from app.agents.requirement_analysis.v3.workflow import run_requirement_analysis_v3
    result = await run_requirement_analysis_v3(input_data)

    # 验证：应该跳过澄清阶段（clarification.items 为空或自动生成）
    assert result.status == "completed"
    assert result.quality_assessment.scores.overall >= 95
    assert result.quality_assessment.decision.result == "approved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
