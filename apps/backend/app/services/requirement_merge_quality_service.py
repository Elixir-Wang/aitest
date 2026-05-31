from __future__ import annotations

import re
from pathlib import Path

from app.schemas.requirement_merge import (
    OutlineAssignment,
    OutlineMergeConflict,
    OutlineSectionMergeResult,
    SourceOutlineDocument,
    TargetOutlineSection,
)
from app.services.requirement_merge_outline_service import assignable_target_sections
from app.services.requirement_outline_assignment_service import assignable_source_nodes
from app.services.requirement_source_outline_service import flatten_source_outline


def evaluate_outline_merge_quality(
    *,
    source_documents: list[SourceOutlineDocument],
    target_outline: list[TargetOutlineSection],
    assignments: list[OutlineAssignment],
    section_results: list[OutlineSectionMergeResult],
    conflicts: list[OutlineMergeConflict],
    merged_markdown: str,
    stage_errors: list[str],
) -> tuple[str, list[str]]:
    issues: list[str] = []
    source_nodes = assignable_source_nodes(source_documents)
    source_ids = {node.node_id for node in source_nodes}
    target_ids = {section.section_id for section in assignable_target_sections(target_outline)}
    assignment_ids = {assignment.source_node_id for assignment in assignments}
    decision_ids = {
        decision.source_node_id
        for result in section_results
        for decision in result.decisions
        if decision.status != "discarded"
    }

    missing_assignments = sorted(source_ids - assignment_ids)
    if missing_assignments:
        issues.append(f"旧大纲节点缺少归属：{', '.join(missing_assignments)}。")

    unknown_assignment_targets = sorted(
        {
            assignment.target_section_id
            for assignment in assignments
            if assignment.target_section_id and assignment.target_section_id not in target_ids
        }
    )
    if unknown_assignment_targets:
        issues.append(f"归属指向未知新章节：{', '.join(unknown_assignment_targets)}。")

    missing_decisions = sorted(assignment_ids - decision_ids)
    if missing_decisions:
        issues.append(f"旧节点缺少章节处理决策：{', '.join(missing_decisions)}。")

    preserved_refs = {
        block.source_node_id
        for result in section_results
        for block in result.blocks
        if block.type == "source_node_ref" and block.source_node_id
    }
    missing_preserved = sorted(node.node_id for node in source_nodes if node.preserve_original and node.node_id not in preserved_refs)
    if missing_preserved:
        issues.append(f"高保真旧节点未原文保留：{', '.join(missing_preserved)}。")

    if _contains_source_structure(merged_markdown, source_documents):
        issues.append("合并稿包含源文件名、docmap 或 mapping_id 等来源结构污染。")

    retention_issue = _retention_issue(merged_markdown, source_documents)
    if retention_issue:
        issues.append(retention_issue)

    structure_issue = _structure_retention_issue(merged_markdown, source_documents)
    if structure_issue:
        issues.append(structure_issue)

    if conflicts:
        issues.append(f"存在 {len(conflicts)} 个明显冲突，需要人工确认。")
        return "blocked", issues
    if any("失败" in item for item in stage_errors):
        issues.extend(stage_errors)
        return "warning" if not _has_blocking_issue(issues) else "failed", issues
    if _has_blocking_issue(issues):
        return "failed", issues
    if issues:
        return "warning", issues
    return "passed", []


def _has_blocking_issue(issues: list[str]) -> bool:
    blocking_tokens = ("缺少", "未知", "未原文保留", "污染", "异常过短", "保留不足")
    return any(any(token in issue for token in blocking_tokens) for issue in issues)


def _contains_source_structure(markdown: str, source_documents: list[SourceOutlineDocument]) -> bool:
    forbidden = ["docmap-", "mapping_id", "来源文档：", "源文档：", "原始文件：", "标准文件："]
    if any(token in markdown for token in forbidden):
        return True
    source_names = [Path(document.source_file).name for document in source_documents]
    return any(name and name in markdown for name in source_names)


def _retention_issue(markdown: str, source_documents: list[SourceOutlineDocument]) -> str:
    source_text = "\n".join(node.content_markdown for node in flatten_source_outline(source_documents))
    source_units = _meaningful_text_units(source_text)
    if len(source_units) < 20:
        return ""
    draft_units = _meaningful_text_units(markdown)
    ratio = len(draft_units) / len(source_units) if source_units else 1
    if ratio < 0.35:
        return f"合并稿相对来源内容异常过短，疑似摘要化（来源有效内容 {len(source_units)} 条，合并稿 {len(draft_units)} 条）。"
    return ""


def _structure_retention_issue(markdown: str, source_documents: list[SourceOutlineDocument]) -> str:
    source_text = "\n".join(node.content_markdown for node in flatten_source_outline(source_documents))
    source_metrics = _markdown_structure_metrics(source_text)
    draft_metrics = _markdown_structure_metrics(markdown)
    issues: list[str] = []
    for key, label, threshold, minimum in [
        ("fenced_blocks", "代码围栏", 0.5, 3),
        ("mermaid_blocks", "Mermaid 流程图", 0.5, 1),
        ("table_rows", "Markdown 表格行", 0.35, 8),
    ]:
        source_count = source_metrics[key]
        if source_count < minimum:
            continue
        draft_count = draft_metrics[key]
        ratio = draft_count / source_count if source_count else 1
        if ratio < threshold:
            issues.append(f"{label}保留不足（来源 {source_count}，合并稿 {draft_count}）")
    return "合并稿疑似丢失结构化 Markdown：" + "；".join(issues) + "。" if issues else ""


def _markdown_structure_metrics(markdown: str) -> dict[str, int]:
    fenced_languages = _fenced_block_languages(markdown)
    return {
        "fenced_blocks": len(fenced_languages),
        "mermaid_blocks": sum(1 for language in fenced_languages if language.lower() == "mermaid"),
        "table_rows": len(re.findall(r"(?m)^\|.*\|$", markdown)),
    }


def _fenced_block_languages(markdown: str) -> list[str]:
    languages: list[str] = []
    in_fence = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line.startswith("```"):
            continue
        if in_fence:
            in_fence = False
            continue
        languages.append(line[3:].strip().split(maxsplit=1)[0] if line[3:].strip() else "")
        in_fence = True
    return languages


def _meaningful_text_units(markdown: str) -> list[str]:
    units: list[str] = []
    in_fence = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line or line.startswith("#") or re.fullmatch(r"[-*_]{3,}", line):
            continue
        units.append(line)
    return units
