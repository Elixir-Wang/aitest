from __future__ import annotations

import re
from typing import Any

from app.schemas.requirement_merge import OutlineAssignment, SourceOutlineDocument, SourceOutlineNode, TargetOutlineSection
from app.services.requirement_merge_outline_service import assignable_target_sections, flatten_target_outline
from app.services.requirement_source_outline_service import flatten_source_outline


ASSIGNMENT_BATCH_SIZE = 30
ALLOWED_ASSIGNMENT_TYPES = {"primary", "reference", "appendix", "pending_clarification"}


async def assign_source_outline_to_target(
    source_documents: list[SourceOutlineDocument],
    target_outline: list[TargetOutlineSection],
) -> tuple[list[OutlineAssignment], list[str], dict[str, Any]]:
    debug = {
        "input_summary": assignment_stage_input_summary(source_documents, target_outline),
        "raw_output": "assignments generated from target_outline.source_node_ids",
        "batches": [],
        "validation_issues": [],
    }
    try:
        assignments = assignments_from_target_outline(target_outline)
        issues = validate_assignments(source_documents, target_outline, assignments)
        debug["validation_issues"] = issues
        debug["assignments"] = [assignment.model_dump() for assignment in assignments]
        if issues:
            raise ValueError("；".join(issues))
        return assignments, [], debug
    except Exception as exc:
        return [], [f"旧大纲归属生成失败：{exc}"], debug


def assignments_from_target_outline(target_outline: list[TargetOutlineSection]) -> list[OutlineAssignment]:
    assignments: list[OutlineAssignment] = []
    for section in leaf_target_sections(target_outline):
        for source_node_id in section.source_node_ids:
            assignments.append(
                OutlineAssignment(
                    source_node_id=source_node_id,
                    target_section_id=section.section_id,
                    assignment_type="primary",
                    reason="outline_source_ref",
                )
            )
    return assignments


def validate_assignments(
    source_documents: list[SourceOutlineDocument],
    target_outline: list[TargetOutlineSection],
    assignments: list[OutlineAssignment],
) -> list[str]:
    issues: list[str] = []
    source_nodes = assignable_source_nodes(source_documents)
    expected_ids = {node.node_id for node in source_nodes}
    assignable_sections = assignable_target_sections(target_outline)
    assignable_ids = {section.section_id for section in assignable_sections}
    root_ids = {section.section_id for section in flatten_target_outline(target_outline) if section.level == 1}
    seen_ids = [assignment.source_node_id for assignment in assignments]

    missing = sorted(expected_ids - set(seen_ids))
    unknown = sorted(set(seen_ids) - expected_ids)
    if missing:
        issues.append(f"旧大纲节点缺少归属：{', '.join(missing)}。")
    if unknown:
        issues.append(f"归属包含未知旧节点：{', '.join(unknown)}。")

    sections_by_id = {section.section_id: section for section in assignable_sections}
    used_target_ids: set[str] = set()
    for assignment in assignments:
        target_id = assignment.target_section_id
        if target_id in root_ids:
            issues.append(f"{assignment.source_node_id} 不能归属到一级根节点：{target_id}。")
        if target_id and target_id not in assignable_ids and target_id not in root_ids:
            issues.append(f"{assignment.source_node_id} 指向未知新章节：{target_id}。")
        if assignment.assignment_type not in ALLOWED_ASSIGNMENT_TYPES:
            issues.append(f"{assignment.source_node_id} 归属类型不合法：{assignment.assignment_type}。")
        if not target_id:
            issues.append(f"{assignment.source_node_id} 缺少目标章节。")
        if target_id:
            used_target_ids.add(target_id)
        if not assignment.reason.strip():
            issues.append(f"{assignment.source_node_id} 缺少归属原因。")
    issues.extend(validate_outline_source_refs(source_documents, target_outline))
    issues.extend(_title_strong_match_issues(source_nodes, assignments, sections_by_id))
    return issues


def validate_outline_source_refs(
    source_documents: list[SourceOutlineDocument],
    target_outline: list[TargetOutlineSection],
) -> list[str]:
    issues: list[str] = []
    expected_ids = {node.node_id for node in assignable_source_nodes(source_documents)}
    root_ids = {section.section_id for section in flatten_target_outline(target_outline) if section.level == 1}
    seen: list[str] = []
    for section in flatten_target_outline(target_outline):
        if section.section_id in root_ids and section.source_node_ids:
            issues.append(f"一级根节点 {section.section_id} 不能带 source_node_ids。")
        if section.level in {2, 3}:
            if section.children and section.source_node_ids:
                issues.append(f"非叶子目标大纲章节不能直接承接旧块：{section.section_id}。")
            if not section.children:
                seen.extend(section.source_node_ids)
            if not section.children and not section.source_node_ids:
                issues.append(f"目标大纲章节没有旧块归属：{section.section_id}。")
    duplicates = sorted({node_id for node_id in seen if seen.count(node_id) > 1})
    missing = sorted(expected_ids - set(seen))
    unknown = sorted(set(seen) - expected_ids)
    if duplicates:
        issues.append(f"旧大纲节点重复标记到目标大纲：{', '.join(duplicates)}。")
    if missing:
        issues.append(f"旧大纲节点缺少目标大纲来源标记：{', '.join(missing)}。")
    if unknown:
        issues.append(f"目标大纲来源标记包含未知旧节点：{', '.join(unknown)}。")
    return issues


def leaf_target_sections(outline: list[TargetOutlineSection]) -> list[TargetOutlineSection]:
    return [section for section in assignable_target_sections(outline) if not section.children]


def validate_assignment_batch(
    batch_nodes: list[SourceOutlineNode],
    target_outline: list[TargetOutlineSection],
    assignments: list[OutlineAssignment],
) -> list[str]:
    issues: list[str] = []
    expected_ids = {node.node_id for node in batch_nodes}
    assignable_ids = {section.section_id for section in assignable_target_sections(target_outline)}
    root_ids = {section.section_id for section in flatten_target_outline(target_outline) if section.level == 1}
    seen_ids = [assignment.source_node_id for assignment in assignments]
    duplicates = sorted({node_id for node_id in seen_ids if seen_ids.count(node_id) > 1})
    missing = sorted(expected_ids - set(seen_ids))
    unknown = sorted(set(seen_ids) - expected_ids)
    if duplicates:
        issues.append(f"批次内旧节点重复归属：{', '.join(duplicates)}。")
    if missing:
        issues.append(f"批次内旧节点缺少归属：{', '.join(missing)}。")
    if unknown:
        issues.append(f"批次内包含未知旧节点：{', '.join(unknown)}。")
    for assignment in assignments:
        target_id = assignment.target_section_id
        if assignment.assignment_type not in ALLOWED_ASSIGNMENT_TYPES:
            issues.append(f"{assignment.source_node_id} 归属类型不合法：{assignment.assignment_type}。")
        if not target_id:
            issues.append(f"{assignment.source_node_id} 缺少 target_section_id。")
        if target_id in root_ids:
            issues.append(f"{assignment.source_node_id} 不能归属到一级根节点：{target_id}。")
        if target_id and target_id not in assignable_ids and target_id not in root_ids:
            issues.append(f"{assignment.source_node_id} 指向未知新章节：{target_id}。")
        if not assignment.reason.strip():
            issues.append(f"{assignment.source_node_id} 缺少归属原因。")
    return issues


def _node_payload(node: SourceOutlineNode) -> dict:
    return {
        "source_node_id": node.node_id,
        "title": node.title,
        "heading_path": node.heading_path,
        "content_types": node.content_types,
        "anchors": node.anchors,
        "preserve_original": node.preserve_original,
    }


def assignment_stage_input_summary(
    source_documents: list[SourceOutlineDocument],
    target_outline: list[TargetOutlineSection],
) -> dict:
    source_nodes = assignable_source_nodes(source_documents)
    assignable_sections = assignable_target_sections(target_outline)
    root_sections = [section for section in flatten_target_outline(target_outline) if section.level == 1]
    return {
        "source_node_count": len(source_nodes),
        "target_section_count": len(flatten_target_outline(target_outline)),
        "assignable_target_section_count": len(assignable_sections),
        "root_section_ids": [section.section_id for section in root_sections],
        "assignable_level_counts": {
            str(level): sum(1 for section in assignable_sections if section.level == level)
            for level in sorted({section.level for section in assignable_sections})
        },
        "batch_size": ASSIGNMENT_BATCH_SIZE,
    }


def assignment_batch_input_summary(
    batch_nodes: list[SourceOutlineNode],
    target_outline: list[TargetOutlineSection],
    *,
    batch_index: int,
    batch_count: int,
) -> dict:
    return {
        "batch_index": batch_index,
        "batch_count": batch_count,
        "source_node_count": len(batch_nodes),
        "source_node_ids": [node.node_id for node in batch_nodes],
        "assignable_target_section_count": len(assignable_target_sections(target_outline)),
    }


def _parse_assignments(raw_items: Any) -> list[OutlineAssignment]:
    if not isinstance(raw_items, list):
        return []
    assignments: list[OutlineAssignment] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        target_id = raw.get("target_section_id", "")
        assignments.append(
            OutlineAssignment(
                source_node_id=str(raw.get("source_node_id") or raw.get("node_id") or ""),
                target_section_id=str(target_id or ""),
                assignment_type=str(raw.get("assignment_type") or "primary"),
                reason=str(raw.get("reason") or ""),
            )
        )
    return assignments


def _title_strong_match_issues(
    source_nodes: list[SourceOutlineNode],
    assignments: list[OutlineAssignment],
    sections_by_id: dict[str, TargetOutlineSection],
) -> list[str]:
    issues: list[str] = []
    assignment_by_node = {assignment.source_node_id: assignment for assignment in assignments}
    leaf_sections = [section for section in sections_by_id.values() if not section.children]
    sections_by_normalized_title: dict[str, list[TargetOutlineSection]] = {}
    for section in leaf_sections:
        normalized = _normalize_heading_title(section.title)
        if normalized:
            sections_by_normalized_title.setdefault(normalized, []).append(section)
    for node in source_nodes:
        normalized = _normalize_heading_title(node.title)
        if not normalized:
            continue
        matched_sections = sections_by_normalized_title.get(normalized, [])
        if len(matched_sections) != 1:
            continue
        expected_section = matched_sections[0]
        actual_section_id = assignment_by_node.get(node.node_id).target_section_id if node.node_id in assignment_by_node else ""
        if actual_section_id and actual_section_id != expected_section.section_id:
            actual_section = sections_by_id.get(actual_section_id)
            actual_title = actual_section.title if actual_section else actual_section_id
            issues.append(
                f"旧标题 {node.node_id}「{node.title}」更匹配目标章节 "
                f"{expected_section.section_id}「{expected_section.title}」，但被标记到 {actual_section_id}「{actual_title}」。"
            )
    return issues


def _normalize_heading_title(title: str) -> str:
    value = str(title or "").strip()
    value = re.sub(r"^\s*(?:第?[一二三四五六七八九十百]+[、.．章节]?|[0-9]+(?:[.．][0-9]+)*[、.．]?)\s*", "", value)
    value = re.sub(r"[\s　:：,，。；;、/\\-_\(\)（）【】\\[\\]]+", "", value)
    return value.lower()


def _assignment_batches(source_nodes: list[SourceOutlineNode]) -> list[list[SourceOutlineNode]]:
    batches: list[list[SourceOutlineNode]] = []
    current: list[SourceOutlineNode] = []
    current_key = ""
    for node in source_nodes:
        key = f"{node.document_code}:{node.heading_path[0] if node.heading_path else ''}"
        if current and (len(current) >= ASSIGNMENT_BATCH_SIZE or key != current_key):
            batches.append(current)
            current = []
        current.append(node)
        current_key = key
    if current:
        batches.append(current)
    return batches


def assignable_source_nodes(source_documents: list[SourceOutlineDocument]) -> list[SourceOutlineNode]:
    return [node for node in flatten_source_outline(source_documents) if node.level in {2, 3}]
