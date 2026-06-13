"""
增强节点

生成增强版需求文档和分析报告
"""

from app.agents.requirement_analysis.v3.state import RequirementAnalysisState
from app.agents.requirement_analysis.schemas import ClarificationOutput, ClarificationSummary
from app.agents.requirement_analysis.utils.report_generator import generate_analysis_report
from app.agents.requirement_analysis.utils.requirement_enhancer import (
    generate_enhanced_requirement,
    get_auto_resolved_items,
)


async def enhance_node(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """
    增强节点

    Args:
        state: 工作流状态

    Returns:
        更新后的状态（添加 enhanced_requirement 和 analysis_report）
    """
    clarification = state["clarification"] or _empty_clarification()

    # 1. 生成分析报告
    analysis_report = generate_analysis_report(
        state["understanding"],
        state["quality"],
        clarification
    )

    # 2. 生成增强版需求文档
    auto_resolved_items = get_auto_resolved_items(clarification.items)
    enhanced_requirement = generate_enhanced_requirement(
        original_markdown=state["primary_content"],
        auto_resolved_items=auto_resolved_items
    )

    # 3. 确定最终状态
    decision = state["quality"].decision.result
    needs_manual = clarification.summary.needs_manual

    if decision == "rejected":
        status = "blocked"
    elif needs_manual > 0:
        status = "needs_clarification"
    else:
        status = "completed"

    # 更新状态
    state["clarification"] = clarification
    state["analysis_report"] = analysis_report
    state["enhanced_requirement"] = enhanced_requirement
    state["status"] = status

    return state


def _empty_clarification() -> ClarificationOutput:
    return ClarificationOutput(
        items=[],
        summary=ClarificationSummary(
            total=0,
            auto_resolved=0,
            has_suggestions=0,
            needs_manual=0,
        ),
        clarification_summary_text="无待澄清问题。",
    )


__all__ = ["enhance_node"]
