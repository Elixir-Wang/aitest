"""
需求理解节点

从主需求文档中提取结构化信息
"""

from app.agents.requirement_analysis.state import RequirementAnalysisState
from app.agents.requirement_analysis.agents.understanding import run_understanding_agent


async def understand_node(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """
    需求理解节点

    Args:
        state: 工作流状态

    Returns:
        更新后的状态（添加 understanding 结果）
    """
    # 获取 LLM 模型（从 config 或使用默认）
    from app.agents.model_selection import build_agent_model, resolve_model_selection

    model_selection = resolve_model_selection("requirement_analysis")
    model = build_agent_model(model_selection)

    # 执行需求理解
    understanding_result = await run_understanding_agent(
        model=model,
        primary_markdown_content=state["primary_content"]
    )

    # 更新状态
    state["understanding"] = understanding_result

    return state


__all__ = ["understand_node"]
