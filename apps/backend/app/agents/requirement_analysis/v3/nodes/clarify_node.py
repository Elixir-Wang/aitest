"""
澄清节点（集成 Agentic Search）

汇总质量问题，使用 Agentic Search 在辅助文档中查找答案
"""

from typing import List, Dict
from app.agents.requirement_analysis.v3.state import RequirementAnalysisState
from app.agents.requirement_analysis.v3.services.auxiliary_search_service import search_for_answer
from app.agents.requirement_analysis.schemas_v2 import (
    ClarificationOutput,
    ClarificationItem,
    ClarificationOption,
    EvidenceReference,
    ClarificationSummary,
)


async def clarify_node(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """
    澄清节点（带 Agentic Search）

    Args:
        state: 工作流状态

    Returns:
        更新后的状态（添加 clarification 结果）
    """
    # 获取 LLM 模型
    from app.core.llm import build_agent_model
    from app.repositories.model_selection_repo import resolve_model_selection

    model_selection = resolve_model_selection("requirement_analysis")
    model = build_agent_model(model_selection)

    # 1. 从质量评估中提取问题
    questions = _extract_questions_from_quality(state["quality"])

    # 2. 为每个问题执行 Agentic Search
    clarification_items = []

    for q in questions:
        # 🔥 使用 Agentic Search 查找答案
        search_result = await search_for_answer(
            model=model,
            question=q["question"],
            auxiliary_documents=state["auxiliary_docs"]
        )

        # 根据搜索结果生成 ClarificationItem
        item = _create_clarification_item(q, search_result)
        clarification_items.append(item)

    # 3. 生成汇总
    summary = _calculate_summary(clarification_items)

    # 4. 构建输出
    clarification_output = ClarificationOutput(
        items=clarification_items,
        summary=summary,
        clarification_summary_text=_generate_summary_text(summary)
    )

    # 更新状态
    state["clarification"] = clarification_output

    return state


def _extract_questions_from_quality(quality_result) -> List[Dict]:
    """从质量评估结果中提取问题"""
    questions = []

    # 从完整性检查提取
    for gap in quality_result.completeness.functional_gaps:
        questions.append({
            "id": f"FG-{len(questions)+1}",
            "question": f"缺少功能：{gap}，请补充相关需求",
            "impact": "影响功能设计",
            "severity": "major",
            "source": "completeness"
        })

    for nfr_gap in quality_result.completeness.nfr_gaps:
        questions.append({
            "id": f"NFR-{len(questions)+1}",
            "question": f"缺少{nfr_gap.category}需求，需要定义什么指标？",
            "impact": nfr_gap.impact,
            "severity": nfr_gap.severity,
            "source": "completeness"
        })

    # 从清晰度检查提取
    for fuzzy in quality_result.clarity.fuzzy_terms:
        questions.append({
            "id": f"FZ-{len(questions)+1}",
            "question": f"'{fuzzy.term}' 的具体定义是什么？",
            "impact": fuzzy.issue,
            "severity": "major",
            "source": "clarity",
            "current_text": fuzzy.current_text,
            "suggested_fix": fuzzy.suggested_fix
        })

    # 从一致性检查提取
    for conflict in quality_result.consistency.conflicts:
        questions.append({
            "id": f"CF-{len(questions)+1}",
            "question": f"发现冲突：{conflict.description}，以哪个为准？",
            "impact": conflict.impact,
            "severity": conflict.severity,
            "source": "consistency"
        })

    return questions


def _create_clarification_item(question: Dict, search_result: Dict) -> ClarificationItem:
    """根据搜索结果创建 ClarificationItem"""

    # 根据搜索结果决定状态
    if search_result["found"] and search_result["confidence"] == "high":
        # 高置信度答案 → auto_resolved
        return ClarificationItem(
            item_id=question["id"],
            source=question["source"],
            module_key="",
            module_name="",
            question=question["question"],
            impact=question["impact"],
            severity=question["severity"],
            current_text=question.get("current_text", ""),
            suggested_fix=search_result["answer"],
            evidence=[
                EvidenceReference(
                    mapping_id="",
                    filename=search_result["source"],
                    excerpt=search_result["answer"][:200],
                    confidence="high"
                )
            ] if search_result["source"] else [],
            resolution_status="auto_resolved",
            recommended_options=[]
        )

    elif search_result["found"]:
        # 中等置信度 → has_suggestions
        return ClarificationItem(
            item_id=question["id"],
            source=question["source"],
            module_key="",
            module_name="",
            question=question["question"],
            impact=question["impact"],
            severity=question["severity"],
            current_text=question.get("current_text", ""),
            suggested_fix=question.get("suggested_fix", ""),
            recommended_options=[
                ClarificationOption(
                    option_id="opt1",
                    label=f"基于 {search_result['source']}",
                    answer_markdown=search_result["answer"],
                    confidence=search_result["confidence"],
                    source=search_result["source"]
                )
            ] if search_result["source"] else [],
            evidence=[],
            resolution_status="has_suggestions"
        )

    else:
        # 未找到 → needs_manual
        return ClarificationItem(
            item_id=question["id"],
            source=question["source"],
            module_key="",
            module_name="",
            question=question["question"],
            impact=question["impact"],
            severity=question["severity"],
            current_text=question.get("current_text", ""),
            suggested_fix=question.get("suggested_fix", ""),
            recommended_options=[],
            evidence=[],
            resolution_status="needs_manual"
        )


def _calculate_summary(items: List[ClarificationItem]) -> ClarificationSummary:
    """计算汇总统计"""
    total = len(items)
    auto_resolved = len([i for i in items if i.resolution_status == "auto_resolved"])
    has_suggestions = len([i for i in items if i.resolution_status == "has_suggestions"])
    needs_manual = len([i for i in items if i.resolution_status == "needs_manual"])

    by_severity = {"blocker": 0, "major": 0, "minor": 0}
    for item in items:
        by_severity[item.severity] += 1

    by_source = {
        "understanding": 0,
        "completeness": 0,
        "clarity": 0,
        "testability": 0,
        "consistency": 0
    }
    for item in items:
        if item.source in by_source:
            by_source[item.source] += 1

    return ClarificationSummary(
        total=total,
        auto_resolved=auto_resolved,
        has_suggestions=has_suggestions,
        needs_manual=needs_manual,
        by_severity=by_severity,
        by_source=by_source
    )


def _generate_summary_text(summary: ClarificationSummary) -> str:
    """生成汇总文本"""
    return (
        f"共发现 {summary.total} 个待澄清项：\n"
        f"- 自动解决：{summary.auto_resolved} 个\n"
        f"- 有建议选项：{summary.has_suggestions} 个\n"
        f"- 需人工确认：{summary.needs_manual} 个\n\n"
        f"按严重程度：blocker {summary.by_severity['blocker']} 个，"
        f"major {summary.by_severity['major']} 个，"
        f"minor {summary.by_severity['minor']} 个"
    )


__all__ = ["clarify_node"]
