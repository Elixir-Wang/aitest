"""Understand node for requirement analysis workflow."""

from app.agents.requirement_analysis.core.state import RequirementAnalysisState
from app.agents.requirement_analysis.utils.timing import record_step_timing, start_step_timer


async def understand_node(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """需求理解节点：调用 understanding agent，写入 state。"""
    from app.agents.model_selection import build_agent_model, resolve_model_selection
    from app.agents.requirement_analysis.agents.understanding import run_understanding_agent

    run_id = state.get("run_id", "")
    started_at = start_step_timer()

    model_selection = resolve_model_selection("requirement_analysis")
    model = build_agent_model(model_selection)

    understanding, deep_understanding = await run_understanding_agent(
        model=model,
        primary_markdown_content=state["primary_content"],
        run_id=run_id,
        metadata=state["metadata"],
    )

    state["understanding"] = understanding
    state["metadata"]["deep_understanding"] = deep_understanding

    record_step_timing(
        state["metadata"],
        run_id=run_id,
        step="understand",
        started_at=started_at,
    )

    return state
