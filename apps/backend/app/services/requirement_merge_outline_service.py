from __future__ import annotations

import json
import re
from typing import Any

from app.agents.runtime import run_agent
from app.schemas.requirement_merge import SourceOutlineDocument, SourceOutlineNode, TargetOutlineSection
from app.services.requirement_source_outline_service import flatten_source_outline


REQUIREMENT_MERGE_AGENT_ID = "requirement_merge"


async def generate_target_outline(
    document_name: str,
    source_documents: list[SourceOutlineDocument],
) -> tuple[list[TargetOutlineSection], list[str], dict[str, Any]]:
    prompt = _build_outline_prompt(document_name, source_documents)
    debug = {
        "input_summary": outline_stage_input_summary(source_documents),
        "raw_output": "",
    }
    try:
        result = await run_agent(REQUIREMENT_MERGE_AGENT_ID, prompt)
        debug["raw_output"] = str(result.output)
        parsed = _parse_json_object(result.output)
        sections = _parse_outline_sections(parsed.get("sections", parsed.get("outline", [])))
        outline = build_target_outline(document_name, sections)
        issues = validate_target_outline(outline, document_name)
        if issues:
            raise ValueError("；".join(issues))
        return outline, [], debug
    except Exception as exc:
        return [], [f"目标大纲生成失败：{exc}"], debug


def validate_target_outline(outline: list[TargetOutlineSection], document_name: str) -> list[str]:
    issues: list[str] = []
    ids: set[str] = set()

    if not outline:
        return ["目标大纲为空。"]
    if len(outline) != 1:
        issues.append("目标大纲必须有且只有一个一级根节点。")

    root = outline[0]
    if root.level != 1:
        issues.append(f"目标大纲根节点 {root.section_id} 层级必须为 1。")
    if root.parent_id:
        issues.append(f"目标大纲根节点 {root.section_id} parent_id 必须为空。")
    if root.title.strip() != document_name.strip():
        issues.append("目标大纲一级标题必须等于需求名称。")
    if not root.children:
        issues.append("目标大纲必须包含至少一个二级业务章节。")

    def visit(section: TargetOutlineSection, parent: TargetOutlineSection | None = None) -> None:
        if not section.section_id.strip():
            issues.append("目标大纲存在空 section_id。")
        if section.section_id in ids:
            issues.append(f"目标大纲 section_id 重复：{section.section_id}。")
        ids.add(section.section_id)
        if not section.title.strip():
            issues.append(f"目标大纲章节 {section.section_id} 标题为空。")
        if section.level not in {1, 2, 3}:
            issues.append(f"目标大纲章节 {section.section_id} 层级不合法。")
        if parent:
            if section.parent_id != parent.section_id:
                issues.append(f"目标大纲章节 {section.section_id} parent_id 不匹配。")
            if section.level != parent.level + 1:
                issues.append(f"目标大纲章节 {section.section_id} 层级跳级。")
        forbidden = ["\n", "|", "```"]
        if any(token in section.title for token in forbidden):
            issues.append(f"目标大纲章节 {section.section_id} 标题疑似包含正文。")
        for child in section.children:
            visit(child, section)

    for item in outline:
        visit(item)
    return issues


def fallback_target_outline(source_documents: list[SourceOutlineDocument]) -> list[TargetOutlineSection]:
    nodes = flatten_source_outline(source_documents)
    buckets = [
        ("S-01", "背景与目标", ("background",)),
        ("S-02", "范围与职责边界", ("requirement",)),
        ("S-03", "核心业务规则", ("requirement", "acceptance")),
        ("S-04", "接口契约", ("interface", "table", "error_code")),
        ("S-05", "流程与状态流转", ("state_flow",)),
        ("S-06", "安全要求", ("security",)),
        ("S-07", "验收标准", ("acceptance",)),
    ]
    used_titles: set[str] = set()
    children: list[TargetOutlineSection] = []
    for section_id, title, content_types in buckets:
        if content_types and not any(set(node.content_types) & set(content_types) for node in nodes):
            continue
        if title in used_titles:
            continue
        used_titles.add(title)
        children.append(
            TargetOutlineSection(
                section_id=section_id,
                parent_id="root",
                level=2,
                title=title,
                reason="系统根据旧大纲标题和内容类型生成的保守合并章节。",
                source_node_ids=[node.node_id for node in nodes if set(node.content_types) & set(content_types)] if content_types else [],
            )
        )
    if not children:
        children = [
            TargetOutlineSection(
                section_id="S-01",
                parent_id="root",
                level=2,
                title="合并需求",
                reason="来源大纲不足，使用全文合并章节。",
            )
        ]
    return [
        TargetOutlineSection(
            section_id="root",
            level=1,
            title="合并需求",
            reason="系统固定的需求文档根节点。",
            children=children,
        )
    ]


def flatten_target_outline(outline: list[TargetOutlineSection]) -> list[TargetOutlineSection]:
    result: list[TargetOutlineSection] = []

    def visit(section: TargetOutlineSection) -> None:
        result.append(section)
        for child in section.children:
            visit(child)

    for section in outline:
        visit(section)
    return result


def assignable_target_sections(outline: list[TargetOutlineSection]) -> list[TargetOutlineSection]:
    return [section for section in flatten_target_outline(outline) if section.level in {2, 3}]


def build_target_outline(document_name: str, sections: list[TargetOutlineSection]) -> list[TargetOutlineSection]:
    root = TargetOutlineSection(
        section_id="root",
        level=1,
        title=document_name,
        reason="系统固定的需求文档根节点。",
        children=_normalize_outline_children(sections, parent_id="root"),
    )
    return [root]


def outline_stage_input_summary(source_documents: list[SourceOutlineDocument]) -> dict:
    nodes = flatten_source_outline(source_documents)
    indexed_nodes = [node for node in nodes if node.level in {2, 3}]
    return {
        "document_count": len(source_documents),
        "source_node_count": len(nodes),
        "indexed_heading_count": len(indexed_nodes),
        "level_counts": {str(level): sum(1 for node in nodes if node.level == level) for level in sorted({node.level for node in nodes})},
        "indexed_level_counts": {
            str(level): sum(1 for node in indexed_nodes if node.level == level)
            for level in sorted({node.level for node in indexed_nodes})
        },
    }


def _build_outline_prompt(document_name: str, source_documents: list[SourceOutlineDocument]) -> str:
    payload = {
        "document_name": document_name,
        "source_heading_index": [_document_index(document) for document in source_documents],
    }
    return (
        "你是需求归并智能体。当前阶段只生成新的统一目标大纲的二级、三级业务目录。\n"
        "一级标题由系统固定为 document_name，你禁止输出一级标题。\n"
        "输入是多个旧需求文档的二级、三级标题索引、父子关系、内容类型和锚点，不是正文。\n"
        "请根据多个原文档二三级目录组合、去重、归并生成新的二级、三级目录，不要照搬源文档顺序。\n"
        "生成每个二级、三级目录时，必须同时输出该目录直接承接的 source_node_ids；source_node_ids 只能使用输入 source_heading_index 中存在的 node_id。\n"
        "只有没有 children 的叶子目录可以承接 source_node_ids；有 children 的父目录必须作为结构容器，source_node_ids 必须为空。\n"
        "每个旧 node_id 必须且只能出现在一个叶子目录的 source_node_ids 中；没有子目录的叶子目录 source_node_ids 不能为空。\n"
        "如果旧二级标题自身有内容且新目录需要拆成三级，请为该旧二级标题生成一个对应的三级叶子目录承接它，不要把它挂到父目录。\n"
        "reason 只作为说明，不作为后续归属依据。\n"
        "只返回 JSON 对象，不要 Markdown 代码块，不要解释文字。\n"
        "JSON 字段：sections。sections 每项字段：section_id, parent_id, level, title, reason, source_node_ids, children。\n"
        "约束：只允许 level=2 或 level=3；至少一个 level=2；level=3 必须挂在 level=2 下；"
        "section_id 唯一；只输出目录，不输出正文。\n\n"
        f"输入：\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _document_index(document: SourceOutlineDocument) -> dict:
    return {
        "document_code": document.document_code,
        "mapping_id": document.mapping_id,
        "source_file": document.source_file,
        "nodes": [_node_index(node) for node in flatten_nodes(document.nodes) if node.level in {2, 3}],
    }


def flatten_nodes(nodes: list[SourceOutlineNode]) -> list[SourceOutlineNode]:
    result: list[SourceOutlineNode] = []
    for node in nodes:
        result.append(node)
        result.extend(flatten_nodes(node.children))
    return result


def _node_index(node: SourceOutlineNode) -> dict:
    return {
        "node_id": node.node_id,
        "level": node.level,
        "title": node.title,
        "heading_path": node.heading_path,
        "sub_headings": node.sub_headings,
        "content_types": node.content_types,
        "anchors": node.anchors,
        "preserve_original": node.preserve_original,
    }


def _parse_outline_sections(raw_items: Any, *, parent_id: str = "") -> list[TargetOutlineSection]:
    if not isinstance(raw_items, list):
        return []
    sections: list[TargetOutlineSection] = []
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            continue
        section_id = str(raw.get("section_id") or raw.get("id") or f"S-{index:02d}")
        default_level = 3 if parent_id else 2
        children = _parse_outline_sections(raw.get("children", []), parent_id=section_id)
        sections.append(
            TargetOutlineSection(
                section_id=section_id,
                parent_id=str(raw.get("parent_id") or parent_id or ""),
                level=int(raw.get("level") or default_level),
                title=str(raw.get("title") or "").strip(),
                reason=str(raw.get("reason") or ""),
                source_node_ids=_parse_source_node_ids(raw.get("source_node_ids", [])),
                children=children,
            )
        )
    return sections


def _normalize_outline_children(sections: list[TargetOutlineSection], *, parent_id: str) -> list[TargetOutlineSection]:
    normalized: list[TargetOutlineSection] = []
    for index, section in enumerate(sections, start=1):
        level = section.level
        if level <= 1:
            level = 2
        section_id = section.section_id or f"sect-{index:03d}"
        children = _normalize_outline_children(section.children, parent_id=section_id)
        normalized.append(
            TargetOutlineSection(
                section_id=section_id,
                parent_id=parent_id if level == 2 else section.parent_id,
                level=level,
                title=section.title,
                reason=section.reason,
                source_node_ids=section.source_node_ids,
                children=children,
            )
        )
    return normalized


def _parse_source_node_ids(raw_value: Any) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    result: list[str] = []
    for item in raw_value:
        value = str(item or "").strip()
        if value:
            result.append(value)
    return result


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
