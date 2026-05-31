from __future__ import annotations

import json
import re
from typing import Any

from app.agents.requirement_merge.runner import run_requirement_merge_prompt
from app.schemas.requirement_merge import (
    OutlineAssignment,
    OutlineSectionBlock,
    OutlineSectionDecision,
    OutlineSectionMergeResult,
    SourceOutlineDocument,
    SourceOutlineNode,
    TargetOutlineSection,
)
from app.services.requirement_merge_outline_service import assignable_target_sections
from app.services.requirement_outline_assignment_service import assignable_source_nodes


REQUIREMENT_MERGE_AGENT_ID = "requirement_merge"


async def merge_sections_by_target_outline(
    source_documents: list[SourceOutlineDocument],
    target_outline: list[TargetOutlineSection],
    assignments: list[OutlineAssignment],
) -> tuple[list[OutlineSectionMergeResult], list[str]]:
    source_nodes = assignable_source_nodes(source_documents)
    nodes_by_id = {node.node_id: node for node in source_nodes}
    assignments_by_section = _assignments_by_section(assignments)
    results: list[OutlineSectionMergeResult] = []
    stage_errors: list[str] = []

    for section in assignable_target_sections(target_outline):
        section_nodes = [nodes_by_id[node_id] for node_id in assignments_by_section.get(section.section_id, []) if node_id in nodes_by_id]
        if not section_nodes:
            if section.children:
                continue
            stage_errors.append(f"章节 {section.section_id} 未找到旧块归属，不能生成空章节。")
            results.append(OutlineSectionMergeResult(section_id=section.section_id, blocks=[], decisions=[], conflicts=[]))
            continue
        if len(section_nodes) == 1:
            result = _direct_section_result(section, section_nodes[0])
        else:
            try:
                result = await _merge_single_section(section, section_nodes)
            except Exception as exc:
                result = OutlineSectionMergeResult(section_id=section.section_id, blocks=[], decisions=[], conflicts=[])
                stage_errors.append(f"章节 {section.section_id} 合并失败：{exc}")
        results.append(result)
    return results, stage_errors


def _assignments_by_section(assignments: list[OutlineAssignment]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for assignment in assignments:
        if assignment.target_section_id:
            grouped.setdefault(assignment.target_section_id, []).append(assignment.source_node_id)
    return grouped


def _direct_section_result(section: TargetOutlineSection, source_node: SourceOutlineNode) -> OutlineSectionMergeResult:
    return OutlineSectionMergeResult(
        section_id=section.section_id,
        blocks=[OutlineSectionBlock(type="source_node_ref", source_node_id=source_node.node_id)],
        decisions=[
            OutlineSectionDecision(
                section_id=section.section_id,
                source_node_id=source_node.node_id,
                status="preserved_original" if source_node.preserve_original else "merged",
                target_heading=section.title,
                reason="单块章节直接填充原始内容，不需要再次合并。",
            )
        ],
        conflicts=[],
    )


async def _merge_single_section(
    section: TargetOutlineSection,
    source_nodes: list[SourceOutlineNode],
) -> OutlineSectionMergeResult:
    prompt = _build_section_merge_prompt(section, source_nodes)
    output = await run_requirement_merge_prompt(prompt)
    parsed = _parse_json_object(output)
    section_result = _parse_section_result(section.section_id, parsed)
    issues = validate_section_result(section_result, source_nodes)
    if issues:
        raise ValueError("；".join(issues))
    return section_result


def validate_section_result(result: OutlineSectionMergeResult, source_nodes: list[SourceOutlineNode]) -> list[str]:
    issues: list[str] = []
    expected_ids = {node.node_id for node in source_nodes}
    decision_ids = {decision.source_node_id for decision in result.decisions}
    missing = sorted(expected_ids - decision_ids)
    unknown = sorted(decision_ids - expected_ids)
    if missing:
        issues.append(f"章节决策缺少旧节点：{', '.join(missing)}。")
    if unknown:
        issues.append(f"章节决策包含未知旧节点：{', '.join(unknown)}。")
    block_node_ids = {block.source_node_id for block in result.blocks if block.source_node_id}
    preserve_ids = {node.node_id for node in source_nodes if node.preserve_original}
    missing_preserve = sorted(preserve_ids - block_node_ids)
    if missing_preserve:
        issues.append(f"高保真旧节点未通过 source_node_ref 保留：{', '.join(missing_preserve)}。")
    return issues


def _build_section_merge_prompt(section: TargetOutlineSection, source_nodes: list[SourceOutlineNode]) -> str:
    payload = {
        "section": section.model_dump(),
        "source_nodes": [_node_payload(node) for node in source_nodes],
    }
    return (
        "你是需求归并智能体。当前阶段只合并一个目标大纲章节。\n"
        "请基于归属到本章节的旧大纲节点，做组合、去重、冲突和待澄清判断。\n"
        "只返回 JSON 对象，不要 Markdown 代码块，不要解释文字。\n"
        "高保真节点 preserve_original=true 必须用 source_node_ref 保留，不要改写为普通段落。\n"
        "blocks.type 只能是 paragraph, bullet_list, table, source_node_ref, pending_clarification_ref, conflict_ref。\n"
        "decisions.status 只能是 merged, duplicate, preserved_original, merged_and_preserved, conflict, pending_clarification, discarded。\n"
        "必须为每个 source_node_id 返回一条 decisions。\n"
        "JSON 字段：section_id, blocks, decisions, conflicts。\n\n"
        f"输入：\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _node_payload(node: SourceOutlineNode) -> dict:
    return {
        "source_node_id": node.node_id,
        "source_file": node.source_file,
        "title": node.title,
        "heading_path": node.heading_path,
        "content_types": node.content_types,
        "anchors": node.anchors,
        "preserve_original": node.preserve_original,
        "content_markdown": node.content_markdown,
    }


def _parse_section_result(section_id: str, parsed: dict) -> OutlineSectionMergeResult:
    return OutlineSectionMergeResult(
        section_id=str(parsed.get("section_id") or section_id),
        blocks=[_parse_block(item) for item in parsed.get("blocks", []) if isinstance(item, dict)],
        decisions=[_parse_decision(section_id, item) for item in parsed.get("decisions", []) if isinstance(item, dict)],
        conflicts=[_parse_conflict(item) for item in parsed.get("conflicts", []) if isinstance(item, dict)],
    )


def _parse_block(raw: dict) -> OutlineSectionBlock:
    block_type = _normalize_block_type(raw.get("type"))
    items = raw.get("items", [])
    if isinstance(items, str):
        items = [items] if items else []
    return OutlineSectionBlock(
        type=block_type,
        content=_string_or_joined(raw.get("content", "")),
        items=[str(item) for item in items if str(item).strip()],
        source_node_id=str(raw.get("source_node_id") or raw.get("node_id") or ""),
        conflict_id=str(raw.get("conflict_id") or ""),
    )


def _parse_decision(section_id: str, raw: dict) -> OutlineSectionDecision:
    return OutlineSectionDecision(
        section_id=str(raw.get("section_id") or section_id),
        source_node_id=str(raw.get("source_node_id") or raw.get("node_id") or ""),
        status=_normalize_decision_status(raw.get("status")),
        target_heading=str(raw.get("target_heading") or ""),
        covered_by_source_node_id=str(raw.get("covered_by_source_node_id") or raw.get("covered_by") or ""),
        conflict_id=str(raw.get("conflict_id") or ""),
        reason=str(raw.get("reason") or ""),
    )


def _parse_conflict(raw: dict) -> OutlineMergeConflict:
    source_node_ids = raw.get("source_node_ids", [])
    if isinstance(source_node_ids, str):
        source_node_ids = [source_node_ids] if source_node_ids else []
    return OutlineMergeConflict(
        conflict_id=str(raw.get("conflict_id") or raw.get("id") or ""),
        title=str(raw.get("title") or "未命名冲突"),
        conflict_type=str(raw.get("conflict_type") or "contradiction"),
        severity=str(raw.get("severity") or "medium"),
        source_node_ids=[str(item) for item in source_node_ids if str(item)],
        fragment_a=str(raw.get("fragment_a") or ""),
        fragment_b=str(raw.get("fragment_b") or ""),
        agent_suggestion=str(raw.get("agent_suggestion") or "需要人工确认。"),
    )


def _normalize_block_type(raw_value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(raw_value or "").strip().lower()).strip("_")
    aliases = {
        "text": "paragraph",
        "content": "paragraph",
        "paragraph": "paragraph",
        "bullet": "bullet_list",
        "bullets": "bullet_list",
        "list": "bullet_list",
        "bullet_list": "bullet_list",
        "table": "table",
        "source": "source_node_ref",
        "source_node": "source_node_ref",
        "source_node_ref": "source_node_ref",
        "pending": "pending_clarification_ref",
        "pending_clarification": "pending_clarification_ref",
        "pending_clarification_ref": "pending_clarification_ref",
        "conflict": "conflict_ref",
        "conflict_ref": "conflict_ref",
    }
    return aliases.get(normalized, "paragraph")


def _normalize_decision_status(raw_value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(raw_value or "").strip().lower()).strip("_")
    aliases = {
        "merge": "merged",
        "merged": "merged",
        "duplicate": "duplicate",
        "deduplicate": "duplicate",
        "preserved": "preserved_original",
        "preserved_original": "preserved_original",
        "preserve_original": "preserved_original",
        "merged_and_preserved": "merged_and_preserved",
        "merge_and_preserve": "merged_and_preserved",
        "conflict": "conflict",
        "pending": "pending_clarification",
        "pending_clarification": "pending_clarification",
        "discard": "discarded",
        "discarded": "discarded",
    }
    return aliases.get(normalized, "merged")


def _string_or_joined(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if str(item).strip())
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def _parse_json_object(output: Any) -> dict:
    if isinstance(output, dict):
        return output
    text = str(output).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("智能体未返回 JSON 对象。")
    return parsed
