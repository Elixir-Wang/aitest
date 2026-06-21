"""需求分析新架构测试"""

import pytest
from app.agents.requirement_analysis import (
    RequirementInput,
    RequirementAnalysisResult,
    analyze_requirement,
    # 旧接口
    RequirementAnalysisRunInput,
    RequirementAnalysisAgentInput,
    run_requirement_analysis,
    analyze_requirement_legacy,
)


def test_new_schemas_structure():
    """测试新的数据结构"""
    # 测试输入
    input_data = RequirementInput(
        requirement_name="测试需求",
        requirement_content="测试内容",
        auxiliary_docs=[]
    )
    assert input_data.requirement_name == "测试需求"
    assert input_data.requirement_content == "测试内容"
    assert input_data.auxiliary_docs == []


def test_old_schemas_still_work():
    """测试旧的数据结构仍然可用"""
    # 测试旧的 RunInput
    run_input = RequirementAnalysisRunInput(run_id="test-123")
    assert run_input.run_id == "test-123"

    # 测试旧的 AgentInput
    agent_input = RequirementAnalysisAgentInput(
        requirement_name="测试",
        primary_filename="test.md",
        primary_markdown_content="# 测试内容",
        auxiliary_documents=[]
    )
    assert agent_input.requirement_name == "测试"


@pytest.mark.asyncio
async def test_new_api_mock(monkeypatch):
    """测试新的 API（Mock）"""
    from app.agents.requirement_analysis.schemas import (
        RequirementUnderstanding,
        ClarificationItem,
        RequirementAnalysisResult,
    )

    # Mock 的返回结果
    mock_result = RequirementAnalysisResult(
        understanding=RequirementUnderstanding(
            background="这是需求背景",
            goals="这是目标与价值",
            users="这是用户角色",
            scope="这是功能范围",
            flow="这是业务流程",
            states="这是状态流转",
            rules="这是业务规则",
            ui="这是页面与交互",
            data="这是数据与系统交互",
        ),
        clarifications=[
            ClarificationItem(
                id="clar-001",
                priority="P0",
                module="登录",
                question="未登录用户能否访问？",
                impact="影响权限控制设计"
            )
        ]
    )

    # Mock agent
    class MockAgent:
        async def ainvoke(self, payload):
            return {"structured_response": mock_result}

    monkeypatch.setattr(
        "app.agents.requirement_analysis.service.requirement_analysis_agent",
        lambda model: MockAgent()
    )
    monkeypatch.setattr(
        "app.agents.requirement_analysis.service.resolve_model_selection",
        lambda cap: "mock_model"
    )
    monkeypatch.setattr(
        "app.agents.requirement_analysis.service.build_agent_model",
        lambda sel: "mock_model"
    )

    # 测试
    input_data = RequirementInput(
        requirement_name="登录功能",
        requirement_content="用户可以登录系统",
        auxiliary_docs=[]
    )

    result = await analyze_requirement(input_data)

    # 验证结果
    assert result.status == "needs_clarification"
    assert result.understanding.background == "这是需求背景"
    assert len(result.clarifications) == 1
    assert result.clarifications[0].id == "clar-001"

    # 验证 Markdown 转换
    understanding_md = result.to_understanding_markdown()
    assert "# 需求理解" in understanding_md
    assert "这是需求背景" in understanding_md

    clarification_md = result.to_clarification_markdown()
    assert "# 待澄清问题" in clarification_md
    assert "clar-001" in clarification_md


@pytest.mark.asyncio
async def test_legacy_api_compatibility(monkeypatch):
    """测试旧 API 兼容性"""
    from app.agents.requirement_analysis.schemas import (
        RequirementUnderstanding,
        RequirementAnalysisResult,
    )

    # Mock 结果
    mock_result = RequirementAnalysisResult(
        understanding=RequirementUnderstanding(
            background="背景",
            goals="目标",
            users="用户",
            scope="范围",
            flow="流程",
            states="状态",
            rules="规则",
            ui="界面",
            data="数据",
        ),
        clarifications=[]
    )

    class MockAgent:
        async def ainvoke(self, payload):
            return {"structured_response": mock_result}

    monkeypatch.setattr(
        "app.agents.requirement_analysis.service.requirement_analysis_agent",
        lambda model: MockAgent()
    )
    monkeypatch.setattr(
        "app.agents.requirement_analysis.service.resolve_model_selection",
        lambda cap: "mock_model"
    )
    monkeypatch.setattr(
        "app.agents.requirement_analysis.service.build_agent_model",
        lambda sel: "mock_model"
    )

    # 使用旧接口
    old_input = RequirementAnalysisAgentInput(
        requirement_name="测试",
        primary_filename="test.md",
        primary_markdown_content="# 测试内容",
        auxiliary_documents=[]
    )

    old_output = await analyze_requirement_legacy(old_input)

    # 验证旧格式输出
    assert old_output.status == "completed"
    assert "# 需求理解" in old_output.understanding_markdown
    assert "背景" in old_output.understanding_markdown
    assert len(old_output.clarification_items) == 0


def test_markdown_conversion():
    """测试 Markdown 转换功能"""
    from app.agents.requirement_analysis.schemas import (
        RequirementUnderstanding,
        ClarificationItem,
        RequirementAnalysisResult,
    )

    result = RequirementAnalysisResult(
        understanding=RequirementUnderstanding(
            background="需求背景内容",
            goals="目标与价值内容",
            users="用户角色内容",
            scope="功能范围内容",
            flow="业务流程内容",
            states="状态流转内容",
            rules="业务规则内容",
            ui="页面交互内容",
            data="数据交互内容",
        ),
        clarifications=[
            ClarificationItem(
                id="clar-001",
                priority="P0",
                module="登录",
                question="测试问题",
                impact="测试影响"
            )
        ]
    )

    # 测试需求理解 Markdown
    understanding_md = result.to_understanding_markdown()
    assert "# 需求理解" in understanding_md
    assert "## 1. 需求背景" in understanding_md
    assert "需求背景内容" in understanding_md
    assert "## 9. 数据与系统交互" in understanding_md

    # 测试澄清问题 Markdown
    clarification_md = result.to_clarification_markdown()
    assert "# 待澄清问题" in clarification_md
    assert "| 优先级 | 模块/对象 | 澄清问题 | 影响 |" in clarification_md
    assert "| P0 | 登录 | 测试问题 | 测试影响 |" in clarification_md


def test_empty_clarifications():
    """测试无澄清问题的情况"""
    from app.agents.requirement_analysis.schemas import (
        RequirementUnderstanding,
        RequirementAnalysisResult,
    )

    result = RequirementAnalysisResult(
        understanding=RequirementUnderstanding(
            background="背景",
            goals="目标",
            users="用户",
            scope="范围",
            flow="流程",
            states="状态",
            rules="规则",
            ui="界面",
            data="数据",
        ),
        clarifications=[]
    )

    # 状态应该是 completed
    assert result.status == "completed"

    # Markdown 应该显示"暂无待澄清问题"
    clarification_md = result.to_clarification_markdown()
    assert "暂无待澄清问题" in clarification_md


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
