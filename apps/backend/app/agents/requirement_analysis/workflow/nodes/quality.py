"""Quality assessment node for requirement analysis workflow."""

from app.agents.requirement_analysis.core.state import RequirementAnalysisState
from app.agents.requirement_analysis.utils.timing import record_step_timing, start_step_timer


async def quality_node(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """
    质量评估节点

    Args:
        state: 工作流状态

    Returns:
        更新后的状态（添加 quality 结果）
    """
    from app.agents.model_selection import build_agent_model, resolve_model_selection
    from app.agents.requirement_analysis.agents.quality import run_quality_assessment_agent

    run_id = state.get("run_id", "")
    started_at = start_step_timer()

    model_selection = resolve_model_selection("requirement_analysis")
    model = build_agent_model(model_selection)

    quality_result = await run_quality_assessment_agent(
        model=model,
        primary_markdown_content=state["primary_content"],
        understanding_result=state["understanding"]
    )

    state["quality"] = quality_result

    record_step_timing(
        state["metadata"],
        run_id=run_id,
        step="assess_quality",
        started_at=started_at,
    )

    return state
