"""
需求分析 v2.0 集成测试

测试完整流程
"""

import pytest
from app.agents.requirement_analysis.schemas import (
    RequirementAnalysisInputV2,
    AuxiliaryDocument,
)


# 测试用的需求文档
TEST_REQUIREMENT = """
# 订单管理模块

## 功能描述

用户可以创建订单。订单创建后状态为"待支付"。
用户支付成功后，订单状态变为"已支付"。
订单金额大于1000元时，需要经理审批。

系统应当快速响应用户操作。
系统应当是安全的。

## 验收标准

- 用户可以成功创建订单
- 支付流程正常工作
"""

# 测试用的辅助文档
TEST_AUXILIARY_DOC = """
# 技术标准

## 性能要求

Web 应用响应时间要求：95% 请求 < 2秒
并发用户数：支持 1000 并发用户

## 审批流程

所有审批流程超时时间统一为 48 小时。
超时后自动转至上级审批。
"""


@pytest.mark.skip(reason="需要真实的 LLM 模型")
@pytest.mark.asyncio
async def test_full_workflow():
    """
    测试完整流程（需要真实 LLM）

    注意：此测试需要配置真实的 LLM 模型才能运行
    """
    from app.agents.requirement_analysis.service import (
        RequirementAnalysisService,
    )

    # TODO: 替换为真实的 LLM 模型
    # from app.core.llm import get_llm_model
    # model = get_llm_model()
    model = None

    service = RequirementAnalysisService(model=model)

    input_data = RequirementAnalysisInputV2(
        project_id="test-project",
        document_id="test-doc",
        document_name="订单管理需求.md",
        run_id="test-run-001",
        primary_mapping_id="primary-001",
        primary_filename="订单管理需求.md",
        primary_markdown_content=TEST_REQUIREMENT,
        auxiliary_documents=[
            AuxiliaryDocument(
                mapping_id="aux-001",
                filename="技术标准.md",
                document_type="standard",
                markdown_content=TEST_AUXILIARY_DOC,
            )
        ],
    )

    result = await service.analyze(input_data)

    # 验证输出结构
    assert result.status in ["completed", "needs_clarification", "blocked"]
    assert result.understanding is not None
    assert result.quality_assessment is not None
    assert result.clarification is not None
    assert result.analysis_report_markdown != ""

    # 验证需求理解
    assert len(result.understanding.modules) > 0

    # 验证质量评估
    assert 0 <= result.quality_assessment.scores.overall <= 100
    assert result.quality_assessment.decision.result in [
        "approved",
        "conditional",
        "rejected",
    ]

    # 验证待澄清内容
    assert result.clarification.summary.total >= 0


def test_input_validation():
    """测试输入验证"""
    from app.agents.requirement_analysis.schemas import (
        RequirementAnalysisInputV2,
    )

    input_data = RequirementAnalysisInputV2(
        project_id="",  # 空字符串由业务层拒绝，schema 只负责结构契约
        document_id="test",
        document_name="test",
        primary_mapping_id="test",
        primary_filename="test",
        primary_markdown_content="",
    )

    assert input_data.project_id == ""
    assert input_data.primary_markdown_content == ""


def test_output_structure():
    """测试输出结构完整性"""
    from app.agents.requirement_analysis.schemas import (
        RequirementAnalysisResultV2,
        RequirementUnderstandingOutput,
        QualityAssessmentOutput,
        QualityScores,
        QualityDecision,
        CompletenessAssessment,
        ClarityAssessment,
        TestabilityAssessment,
        ConsistencyAssessment,
        ClarificationOutput,
        ClarificationSummary,
    )

    # 构造完整的输出对象
    result = RequirementAnalysisResultV2(
        status="needs_clarification",
        understanding=RequirementUnderstandingOutput(
            modules=[],
            risks=[],
            assumptions=[],
            understanding_summary="测试",
        ),
        quality_assessment=QualityAssessmentOutput(
            scores=QualityScores(
                completeness=70,
                clarity=75,
                testability=60,
                consistency=95,
                overall=73,
            ),
            decision=QualityDecision(
                result="conditional",
                rationale="测试",
                blocking_issues=[],
                recommended_actions=[],
            ),
            completeness=CompletenessAssessment(score=70),
            clarity=ClarityAssessment(score=75),
            testability=TestabilityAssessment(score=60),
            consistency=ConsistencyAssessment(score=95),
            assessment_summary="测试",
        ),
        clarification=ClarificationOutput(
            items=[],
            summary=ClarificationSummary(
                total=5,
                auto_resolved=1,
                has_suggestions=2,
                needs_manual=2,
            ),
            clarification_summary_text="测试",
        ),
        analysis_report_markdown="# 测试报告",
        metadata={},
    )

    # 验证可以正确序列化
    json_data = result.model_dump_json()
    assert json_data is not None

    # 验证可以正确反序列化
    result2 = RequirementAnalysisResultV2.model_validate_json(json_data)
    assert result2.status == "needs_clarification"


def test_config_merge():
    """测试配置合并"""
    from app.agents.requirement_analysis.service import (
        RequirementAnalysisService,
        DEFAULT_CONFIG,
    )

    custom_config = {
        "quality_thresholds": {
            "approved": 85,  # 覆盖默认值 90
        }
    }

    service = RequirementAnalysisService(model=None, config=custom_config)
    config = service.get_config()

    # 验证自定义配置已应用
    assert config["quality_thresholds"]["approved"] == 85

    # 验证其他默认配置仍然存在
    assert config["quality_thresholds"]["conditional"] == 75
    assert config["dimension_weights"]["completeness"] == 0.30


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
