"""需求分析新架构测试"""

import pytest
from app.agents.model_selection import ModelSelection
from app.agents.requirement_analysis import (
    ClarificationItem,
    RequirementInput,
    RequirementAnalysisResult,
    analyze_requirement,
    run_requirement_analysis,
)


def _model_selection(provider: str = "openai", model: str = "gpt-4o-mini") -> ModelSelection:
    return ModelSelection(provider=provider, model=model, base_url=None, api_key="test-key")


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


def test_legacy_contract_is_not_exported():
    """旧 compatibility 契约不再从 requirement_analysis 包导出。"""
    import app.agents.requirement_analysis as requirement_analysis

    assert not hasattr(requirement_analysis, "RequirementAnalysisRunInput")
    assert not hasattr(requirement_analysis, "RequirementAnalysisAgentInput")
    assert not hasattr(requirement_analysis, "RequirementAnalysisAgentOutput")
    assert not hasattr(requirement_analysis, "analyze_requirement_legacy")


@pytest.mark.anyio
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
                option_a="统一拦截到登录页",
                option_b="返回 401 由前端决定",
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
        lambda cap: _model_selection()
    )
    monkeypatch.setattr(
        "app.agents.requirement_analysis.service.build_agent_model",
        lambda sel, *, extra_body=None: "mock_model"
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
    assert "未登录用户能否访问？" in clarification_md


@pytest.mark.anyio
async def test_run_requirement_analysis_uses_new_input_contract(monkeypatch):
    """测试运行入口直接接收新输入契约。"""
    from app.agents.requirement_analysis.schemas import (
        ClarificationItem,
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
        clarifications=[
            ClarificationItem(
                id="clar-001",
                priority="P0",
                module="登录",
                question="测试问题？",
                option_a="选项 A",
                option_b="选项 B",
                impact="影响说明。",
            )
        ],
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
        lambda cap: _model_selection()
    )
    monkeypatch.setattr(
        "app.agents.requirement_analysis.service.build_agent_model",
        lambda sel, *, extra_body=None: "mock_model"
    )

    result = await run_requirement_analysis(
        RequirementInput(
            requirement_name="测试",
            requirement_content="# 测试内容",
            auxiliary_docs=[],
        )
    )

    assert result.status == "needs_clarification"
    assert result.understanding.background == "背景"
    assert len(result.clarifications) == 1


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
                option_a="选项 A",
                option_b="选项 B",
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
    assert "| 优先级 | 模块/对象 | 澄清问题 | 选项 A | 选项 B | 影响 |" in clarification_md
    assert "| P0 | 登录 | 测试问题 | 选项 A | 选项 B | 测试影响 |" in clarification_md


def test_empty_clarifications_is_now_rejected():
    """澄清问题数量硬约束：空列表必须被 schema 拒绝（回归防御）

    历史问题：result.json 里出现 status=completed + clarifications=[] + "暂无待澄清问题"
    的产物。修复方案是把硬约束下沉到 pydantic schema：clarifications 至少有 1 条。
    真正的失败用例见 test_clarification_minimum.py::test_clarifications_empty_list_fails_validation。
    """
    from app.agents.requirement_analysis.schemas import (
        RequirementUnderstanding,
        RequirementAnalysisResult,
    )
    from pydantic import ValidationError

    understanding = RequirementUnderstanding(
        background="背景",
        goals="目标",
        users="用户",
        scope="范围",
        flow="流程",
        states="状态",
        rules="规则",
        ui="界面",
        data="数据",
    )

    with pytest.raises(ValidationError):
        RequirementAnalysisResult(understanding=understanding, clarifications=[])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
