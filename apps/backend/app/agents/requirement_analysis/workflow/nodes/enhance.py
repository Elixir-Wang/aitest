"""Enhancement node for requirement analysis workflow."""

from app.agents.requirement_analysis.core.state import RequirementAnalysisState
from app.agents.requirement_analysis.utils.timing import record_step_timing, start_step_timer


async def enhance_node(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """
    增强节点

    Args:
        state: 工作流状态

    Returns:
        更新后的状态（添加 enhanced_requirement 和 analysis_report）
    """
    from app.agents.requirement_analysis.utils.report import generate_analysis_report
    from app.agents.requirement_analysis.utils.enhancer import (
        generate_enhanced_requirement,
        get_auto_resolved_items,
    )

    run_id = state.get("run_id", "")
    started_at = start_step_timer()

    # 生成分析报告
    analysis_report = generate_analysis_report(state["understanding"])

    # 生成增强版需求文档
    auto_resolved_items = get_auto_resolved_items(state["clarification"].items)
    enhanced_requirement = generate_enhanced_requirement(
        original_markdown=state["primary_content"],
        auto_resolved_items=auto_resolved_items
    )

    # 确定最终状态
    decision = state["quality"].decision.result
    needs_manual = (
        state["clarification"].summary.by_resolution.get("needs_input", 0) +
        state["clarification"].summary.by_resolution.get("needs_research", 0)
    )

    if decision == "rejected":
        status = "blocked"
    elif needs_manual > 0:
        status = "needs_clarification"
    else:
        status = "completed"

    state["analysis_report"] = analysis_report
    state["enhanced_requirement"] = enhanced_requirement
    state["status"] = status

    record_step_timing(
        state["metadata"],
        run_id=run_id,
        step="enhance",
        started_at=started_at,
    )

    return state
