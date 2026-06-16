"""Lightweight context builders for requirement analysis agents."""

from __future__ import annotations

from app.agents.requirement_analysis.core.schemas import (
    AuxiliaryDocument,
    EvidenceSnippet,
    QualityAssessmentBrief,
    QualityAssessmentOutput,
    QualityIssueBrief,
    QuestioningBrief,
    RequirementUnderstandingBrief,
    RequirementUnderstandingOutput,
)


def build_evidence_snippets(
    primary_markdown_content: str,
    auxiliary_documents: list[AuxiliaryDocument],
    *,
    max_primary_chars: int = 6000,
    max_auxiliary_chars: int = 1200,
) -> list[EvidenceSnippet]:
    """Build bounded evidence snippets from primary and auxiliary documents."""
    snippets: list[EvidenceSnippet] = []
    primary_text = primary_markdown_content.strip()
    if primary_text:
        snippets.append(
            EvidenceSnippet(
                source="primary",
                ref="REQ-PRIMARY",
                text=_trim_text(primary_text, max_primary_chars),
            )
        )

    for index, doc in enumerate(auxiliary_documents, 1):
        text = doc.markdown_content.strip()
        if not text:
            continue
        snippets.append(
            EvidenceSnippet(
                source="auxiliary",
                ref=doc.mapping_id or f"AUX-{index:03d}",
                filename=doc.filename,
                text=_trim_text(text, max_auxiliary_chars),
            )
        )
    return snippets


def build_understanding_brief(
    understanding: RequirementUnderstandingOutput,
) -> RequirementUnderstandingBrief:
    modules = [module.module_name for module in understanding.modules if module.module_name]
    p0_flows: list[str] = []
    state_objects: list[str] = []
    external_dependencies: list[str] = []

    for module in understanding.modules:
        p0_flows.extend(module.capabilities[:3])
        for state_flow in module.state_flows:
            if state_flow.object_name:
                state_objects.append(state_flow.object_name)
        external_dependencies.extend(module.dependencies)

    external_dependencies.extend(
        dependency.target_module
        for dependency in understanding.dependencies
        if dependency.target_module
    )

    return RequirementUnderstandingBrief(
        business_goal=understanding.understanding_summary,
        modules=_unique(modules),
        p0_flows=_unique(p0_flows),
        state_objects=_unique(state_objects),
        external_dependencies=_unique(external_dependencies),
        evidence_refs=["REQ-PRIMARY"],
    )


def build_quality_brief(quality: QualityAssessmentOutput) -> QualityAssessmentBrief:
    issues: list[QualityIssueBrief] = []
    issues.extend(
        QualityIssueBrief(
            issue_id=f"BLOCKER-{index:03d}",
            severity="blocker",
            dimension="decision",
            summary=issue,
            impact=issue,
            evidence_refs=["REQ-PRIMARY"],
        )
        for index, issue in enumerate(quality.decision.blocking_issues, 1)
    )
    issues.extend(
        QualityIssueBrief(
            issue_id=f"NFR-{index:03d}",
            severity=gap.severity,
            dimension="completeness",
            summary=gap.description,
            impact=gap.impact,
            evidence_refs=["REQ-PRIMARY"] if gap.evidence_text else [],
        )
        for index, gap in enumerate(quality.completeness.nfr_gaps, 1)
    )
    issues.extend(
        QualityIssueBrief(
            issue_id=f"FUZZY-{index:03d}",
            severity="major",
            dimension="clarity",
            summary=term.issue,
            impact=term.suggested_fix,
            evidence_refs=["REQ-PRIMARY"] if term.current_text else [],
        )
        for index, term in enumerate(quality.clarity.fuzzy_terms, 1)
    )
    issues.extend(
        QualityIssueBrief(
            issue_id=f"TEST-{index:03d}",
            severity="major",
            dimension="testability",
            summary=gap.description,
            impact=gap.impact,
            evidence_refs=["REQ-PRIMARY"],
        )
        for index, gap in enumerate(quality.testability.test_coverage_gaps, 1)
    )
    issues.extend(
        QualityIssueBrief(
            issue_id=f"CONFLICT-{index:03d}",
            severity=conflict.severity,
            dimension="consistency",
            summary=conflict.description,
            impact=conflict.impact,
            evidence_refs=["REQ-PRIMARY"],
        )
        for index, conflict in enumerate(quality.consistency.conflicts, 1)
    )

    return QualityAssessmentBrief(
        decision=quality.decision.result,
        blockers=list(quality.decision.blocking_issues),
        top_issues=issues[:20],
    )


def format_evidence_snippets(snippets: list[EvidenceSnippet]) -> str:
    if not snippets:
        return "（无证据片段）"
    blocks = []
    for snippet in snippets:
        title = snippet.ref
        if snippet.filename:
            title = f"{title} / {snippet.filename}"
        blocks.append(f"## {title}\n\n{snippet.text}")
    return "\n\n---\n\n".join(blocks)


def _trim_text(text: str, max_chars: int) -> str:
    normalized = text.strip()
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[:max_chars].rstrip()}\n\n...[已截断]"


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def build_questioning_brief(questioning_output) -> QuestioningBrief:
    """
    构建质疑分析摘要

    Token 优化：
    - 完整版 QuestioningOutput: ~12K tokens
    - 摘要版 QuestioningBrief: ~1.5K tokens
    - 节省: 87.5%

    Args:
        questioning_output: QuestioningOutput 对象

    Returns:
        QuestioningBrief 摘要对象
    """
    from app.agents.requirement_analysis.agents.questioning import QuestioningOutput

    if not isinstance(questioning_output, QuestioningOutput):
        # 兼容性处理：如果传入的不是 QuestioningOutput，返回空摘要
        return QuestioningBrief()

    # 统计风险等级
    high_risk_count = 0
    medium_risk_count = 0
    low_risk_count = 0

    # 统计反向场景风险
    for scenario in questioning_output.adversarial_scenarios:
        if scenario.risk_level == "🔴":
            high_risk_count += 1
        elif scenario.risk_level == "🟡":
            medium_risk_count += 1
        elif scenario.risk_level == "🟢":
            low_risk_count += 1

    # 统计需求漏洞风险
    critical_gap_count = 0
    for gap in questioning_output.requirement_gaps:
        if gap.severity == "🔴":
            high_risk_count += 1
            critical_gap_count += 1
        elif gap.severity == "🟡":
            medium_risk_count += 1
        elif gap.severity == "🟢":
            low_risk_count += 1

    # 统计可执行性/可实现性问题
    executability_red = len([c for c in questioning_output.executability_checks if c.status == "🔴不可测试"])
    executability_yellow = len([c for c in questioning_output.executability_checks if c.status == "🟡验证困难"])
    implementability_red = len([c for c in questioning_output.implementability_checks if c.status == "🔴不可实现"])
    implementability_yellow = len([c for c in questioning_output.implementability_checks if c.status == "🟡有风险"])

    high_risk_count += executability_red + implementability_red
    medium_risk_count += executability_yellow + implementability_yellow

    # 统计 9 宫格疑点
    nine_grid_summary = {}
    total_nine_grid_issues = 0
    critical_question_ids = []

    for matrix in questioning_output.nine_grid_matrices:
        for item in matrix.grid_items:
            dimension = item.dimension
            if item.status.startswith("Q-"):
                nine_grid_summary[dimension] = nine_grid_summary.get(dimension, 0) + 1
                total_nine_grid_issues += 1
                critical_question_ids.append(item.status)

    # 统计反向场景
    adversarial_high_risk = len([s for s in questioning_output.adversarial_scenarios if s.risk_level == "🔴"])

    return QuestioningBrief(
        high_risk_count=high_risk_count,
        medium_risk_count=medium_risk_count,
        low_risk_count=low_risk_count,
        total_risk_count=high_risk_count + medium_risk_count + low_risk_count,
        breaker_status=questioning_output.risk_breaker.breaker_status,
        breaker_message=questioning_output.risk_breaker.message,
        nine_grid_summary=nine_grid_summary,
        total_nine_grid_issues=total_nine_grid_issues,
        critical_question_ids=critical_question_ids[:10],  # 只保留前10个关键疑点ID
        adversarial_scenario_count=len(questioning_output.adversarial_scenarios),
        adversarial_high_risk_count=adversarial_high_risk,
        executability_red_count=executability_red,
        executability_yellow_count=executability_yellow,
        implementability_red_count=implementability_red,
        implementability_yellow_count=implementability_yellow,
        requirement_gap_count=len(questioning_output.requirement_gaps),
        critical_gap_count=critical_gap_count,
        recommended_action=questioning_output.risk_breaker.recommended_action,
        generated_at=questioning_output.generated_at,
    )


__all__ = [
    "build_evidence_snippets",
    "build_quality_brief",
    "build_questioning_brief",
    "build_understanding_brief",
    "format_evidence_snippets",
]
