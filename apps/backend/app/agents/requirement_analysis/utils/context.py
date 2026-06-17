"""Lightweight context builders for requirement analysis agents."""

from __future__ import annotations

from app.agents.requirement_analysis.schemas import (
    AuxiliaryDocument,
    EvidenceSnippet,
    QualityAssessmentBrief,
    QualityIssueBrief,
    RequirementUnderstandingBrief,
)
from app.agents.requirement_analysis.quality.schemas import QualityAssessmentOutput
from app.agents.requirement_analysis.understanding.schemas import RequirementUnderstandingOutput


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


def build_quality_brief(quality: QualityAssessmentOutput) -> QualityAssessmentBrief:
    """Build a compact quality summary for the clarification agent."""
    issues: list[QualityIssueBrief] = []
    issues.extend(
        QualityIssueBrief(
            issue_id=f"COMP-FG-{index:03d}",
            severity="major",
            dimension="completeness",
            summary=gap,
            impact="功能规则或处理路径不完整，影响测试设计和验收判定。",
            evidence_refs=["REQ-PRIMARY"],
        )
        for index, gap in enumerate(quality.completeness.functional_gaps, 1)
    )
    issues.extend(
        QualityIssueBrief(
            issue_id=f"COMP-NFR-{index:03d}",
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
            issue_id=f"COMP-MD-{index:03d}",
            severity="minor",
            dimension="completeness",
            summary=detail,
            impact="细节缺失可能导致实现和测试口径不一致。",
            evidence_refs=["REQ-PRIMARY"],
        )
        for index, detail in enumerate(quality.completeness.missing_details, 1)
    )
    issues.extend(
        QualityIssueBrief(
            issue_id=f"CLAR-FT-{index:03d}",
            severity="major",
            dimension="clarity",
            summary=f"模糊词：{term.term}（{term.location}）",
            impact=term.issue,
            evidence_refs=["REQ-PRIMARY"] if term.current_text else [],
        )
        for index, term in enumerate(quality.clarity.fuzzy_terms, 1)
    )
    issues.extend(
        QualityIssueBrief(
            issue_id=f"CLAR-AS-{index:03d}",
            severity="major",
            dimension="clarity",
            summary=statement.statement,
            impact="存在多种解读，需确认唯一业务口径。",
            evidence_refs=["REQ-PRIMARY"],
        )
        for index, statement in enumerate(quality.clarity.ambiguous_statements, 1)
    )
    issues.extend(
        QualityIssueBrief(
            issue_id=f"TEST-AC-{index:03d}",
            severity="major",
            dimension="testability",
            summary=f"{gap.module_key}: {gap.capability}",
            impact="缺少验收标准会导致测试无法断言。",
            evidence_refs=["REQ-PRIMARY"] if gap.current_text else [],
        )
        for index, gap in enumerate(quality.testability.acceptance_criteria_gaps, 1)
    )
    issues.extend(
        QualityIssueBrief(
            issue_id=f"TEST-COV-{index:03d}",
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
            issue_id=conflict.conflict_id or f"CONS-CON-{index:03d}",
            severity=conflict.severity,
            dimension="consistency",
            summary=conflict.description,
            impact=conflict.impact,
            evidence_refs=["REQ-PRIMARY"],
        )
        for index, conflict in enumerate(quality.consistency.conflicts, 1)
    )
    issues.extend(
        QualityIssueBrief(
            issue_id=f"CONS-TERM-{index:03d}",
            severity="minor",
            dimension="consistency",
            summary=f"术语不一致：{issue.concept}",
            impact="术语不一致可能导致实现、测试和业务沟通偏差。",
            evidence_refs=["REQ-PRIMARY"],
            needs_human_decision=False,
        )
        for index, issue in enumerate(quality.consistency.terminology_issues, 1)
    )

    severity_order = {"blocker": 0, "major": 1, "minor": 2}
    top_issues = sorted(
        issues,
        key=lambda item: (severity_order.get(item.severity, 3), not item.needs_human_decision),
    )[:20]

    return QualityAssessmentBrief(
        decision=quality.decision.result,
        blockers=quality.decision.blocking_issues,
        top_issues=top_issues,
        assessment_summary=quality.assessment_summary,
    )


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


__all__ = [
    "build_evidence_snippets",
    "build_quality_brief",
    "build_understanding_brief",
    "format_evidence_snippets",
]

