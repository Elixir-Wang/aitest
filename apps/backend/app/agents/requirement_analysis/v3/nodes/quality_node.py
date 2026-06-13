"""
质量评估节点

评估需求文档质量（完整性、清晰度、可测试性、一致性）
"""

from app.agents.requirement_analysis.v3.state import RequirementAnalysisState
from app.agents.requirement_analysis.v3.agents.analysis import run_quality_assessment_agent
from app.agents.model_selection import build_agent_model, resolve_model_selection


async def quality_node(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """
    质量评估节点

    Args:
        state: 工作流状态

    Returns:
        更新后的状态（添加 quality 结果）
    """
    selection = resolve_model_selection("requirement_analysis")
    model = build_agent_model(selection)

    # 执行质量评估
    quality_result = await run_quality_assessment_agent(
        model=model,
        primary_markdown_content=state["primary_content"],
        understanding_result=state["understanding"]
    )

    # 更新状态
    state["quality"] = quality_result

    return state


__all__ = ["quality_node"]
