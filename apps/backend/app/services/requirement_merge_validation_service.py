import re

from app.schemas.requirement_merge import (
    RequirementFragmentDecision,
    RequirementMergeAuditOutput,
    RequirementSourceFragment,
)


def validate_merge_audit_output(
    audit_output: RequirementMergeAuditOutput,
    source_fragments: list[RequirementSourceFragment],
) -> list[str]:
    issues: list[str] = []
    expected_ids = {fragment.fragment_id for fragment in source_fragments}
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    unknown_ids: set[str] = set()

    for decision in audit_output.fragment_decisions:
        if decision.fragment_id in seen_ids:
            duplicate_ids.add(decision.fragment_id)
        seen_ids.add(decision.fragment_id)
        if decision.fragment_id not in expected_ids:
            unknown_ids.add(decision.fragment_id)
        issues.extend(_decision_contract_issues(decision, audit_output))

    missing_ids = sorted(expected_ids - seen_ids)
    if missing_ids:
        issues.append(f"片段决策缺失：{', '.join(missing_ids)}。")
    if unknown_ids:
        issues.append(f"片段决策包含未知片段：{', '.join(sorted(unknown_ids))}。")
    if duplicate_ids:
        issues.append(f"片段决策重复：{', '.join(sorted(duplicate_ids))}。")

    summary_issues = audit_summary_count_mismatches(
        audit_output.merge_summary,
        _decision_counts(audit_output.fragment_decisions),
    )
    issues.extend(summary_issues)
    return issues


def validate_merge_draft_markdown(
    markdown: str,
    source_fragments: list[RequirementSourceFragment],
    audit_output: RequirementMergeAuditOutput,
) -> list[str]:
    issues: list[str] = []
    if not markdown.strip():
        issues.append("合并候选稿为空。")
        return issues
    top_level_headings = re.findall(r"(?m)^#\s+\S+", markdown)
    if len(top_level_headings) != 1:
        issues.append("合并候选稿必须且只能包含一个一级标题。")
    if _contains_source_structure(markdown, source_fragments):
        issues.append("合并候选稿包含源文件名、docmap 或来源文档结构。")
    if any(decision.coverage_status == "conflict" for decision in audit_output.fragment_decisions):
        issues.append("存在明显冲突片段时不能写入合并候选稿。")
    return issues


def audit_summary_count_mismatches(merge_summary: str, counts: dict[str, int]) -> list[str]:
    labels = {
        "merged": ("合入", "已合入"),
        "duplicate": ("重复", "去重"),
        "conflict": ("冲突",),
        "pending_clarification": ("待澄清",),
        "discarded": ("丢弃", "已丢弃"),
    }
    issues: list[str] = []
    for status, status_labels in labels.items():
        expected = counts.get(status, 0)
        for label in status_labels:
            match = re.search(rf"{label}\s*(\d+)\s*(?:个|条|处)?", merge_summary)
            if match and int(match.group(1)) != expected:
                issues.append(f"合并摘要称{label}{match.group(1)}处，但片段决策统计为{expected}处。")
                break
    return issues


def _decision_contract_issues(
    decision: RequirementFragmentDecision,
    audit_output: RequirementMergeAuditOutput,
) -> list[str]:
    issues: list[str] = []
    if not decision.reason.strip():
        issues.append(f"{decision.fragment_id} 缺少处理原因。")
    if decision.coverage_status == "merged" and (not decision.target_module.strip() or not decision.target_heading.strip()):
        issues.append(f"{decision.fragment_id} 标记为 merged 但缺少目标模块或目标标题。")
    if decision.coverage_status == "duplicate" and not decision.reason.strip():
        issues.append(f"{decision.fragment_id} 标记为 duplicate 但缺少覆盖说明。")
    if decision.coverage_status == "conflict":
        conflict_keys = {str(item.get("conflict_key") or item.get("id") or "") for item in audit_output.conflicts}
        if not decision.related_conflict_key.strip() or decision.related_conflict_key not in conflict_keys:
            issues.append(f"{decision.fragment_id} 标记为 conflict 但未关联有效冲突。")
    if decision.coverage_status == "pending_clarification":
        clarification_keys = {
            str(item.get("clarification_key") or item.get("id") or "") for item in audit_output.clarification_items
        }
        if not decision.related_clarification_key.strip() or decision.related_clarification_key not in clarification_keys:
            issues.append(f"{decision.fragment_id} 标记为 pending_clarification 但未关联有效澄清项。")
    return issues


def _decision_counts(decisions: list[RequirementFragmentDecision]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision in decisions:
        counts[decision.coverage_status] = counts.get(decision.coverage_status, 0) + 1
    return counts


def _contains_source_structure(markdown: str, source_fragments: list[RequirementSourceFragment]) -> bool:
    forbidden = ["docmap-", "mapping_id", "来源文档", "源文档", "原始文件", "标准文件"]
    if any(token in markdown for token in forbidden):
        return True
    source_names = {fragment.source_filename for fragment in source_fragments if fragment.source_filename}
    source_stems = {name.rsplit(".", 1)[0] for name in source_names}
    return any(name and name in markdown for name in source_names | source_stems)
