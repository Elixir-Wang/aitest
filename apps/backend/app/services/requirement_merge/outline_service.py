from typing import Any

from app.agents.requirement_merge.schemas import (
    RequirementMergeOutlineInput,
    RequirementMergeSourceBlockIndex,
    RequirementMergeSourceDocumentIndex,
)
from app.agents.requirement_merge.service import generate_outline_and_placements
from app.schemas.requirement_merge import SourceOutlineDocument, SourceOutlineNode, TargetOutlineSection
from app.services.requirement_merge.source_outline_service import flatten_source_outline


REQUIREMENT_MERGE_AGENT_ID = "requirement_merge"


async def generate_target_outline(
    document_name: str,
    source_documents: list[SourceOutlineDocument],
) -> tuple[list[TargetOutlineSection], list[str], dict[str, Any]]:
    prompt = _build_outline_prompt(document_name, source_documents)
    debug = {
        "input_summary": outline_stage_input_summary(source_documents),
        "raw_output": "",
        "input": _outline_input_payload(document_name, source_documents),
    }
    try:
        _ = prompt
        output = await generate_outline_and_placements(_outline_input(document_name, source_documents))
        debug["raw_output"] = output.model_dump()
        outline = build_target_outline_from_outline_output(document_name, output)
        issues = validate_target_outline(outline, document_name)
        if not issues:
            from app.services.requirement_merge.outline_assignment_service import validate_outline_source_refs

            issues = validate_outline_source_refs(source_documents, outline)
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
        issues.append("目标大纲必须包含至少一个二级章节。")

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


def build_target_outline_from_outline_output(document_name: str, output) -> list[TargetOutlineSection]:
    modules = [
        TargetOutlineSection(
            section_id=module.id,
            parent_id="root",
            level=2,
            title=module.title,
            reason=module.reason,
            source_node_ids=[
                placement.source_id
                for placement in output.placements
                if placement.target_id == module.id
            ],
            children=[],
        )
        for module in output.outline
    ]
    return [
        TargetOutlineSection(
            section_id="root",
            level=1,
            title=document_name,
            reason="系统固定的需求文档根节点。",
            children=modules,
        )
    ]


def build_target_outline(document_name: str, sections: list[TargetOutlineSection]) -> list[TargetOutlineSection]:
    root = TargetOutlineSection(
        section_id="root",
        level=1,
        title=document_name,
        reason="系统固定的需求文档根节点。",
        children=_normalize_outline_children(sections, parent_id="root"),
    )
    _move_parent_source_refs_to_leaf(root)
    return [root]


def outline_stage_input_summary(source_documents: list[SourceOutlineDocument]) -> dict:
    nodes = flatten_source_outline(source_documents)
    indexed_nodes = [node for node in nodes if node.level in {2, 3}]
    assignable_nodes = [node for node in indexed_nodes if node.must_assign]
    return {
        "document_count": len(source_documents),
        "source_node_count": len(nodes),
        "indexed_heading_count": len(indexed_nodes),
        "assignable_heading_count": len(assignable_nodes),
        "level_counts": {str(level): sum(1 for node in nodes if node.level == level) for level in sorted({node.level for node in nodes})},
        "indexed_level_counts": {
            str(level): sum(1 for node in indexed_nodes if node.level == level)
            for level in sorted({node.level for node in indexed_nodes})
        },
    }


def _build_outline_prompt(document_name: str, source_documents: list[SourceOutlineDocument]) -> str:
    _ = document_name, source_documents
    return ""


def _outline_input(document_name: str, source_documents: list[SourceOutlineDocument]) -> RequirementMergeOutlineInput:
    return RequirementMergeOutlineInput(
        requirement_name=document_name,
        source_documents=[
            RequirementMergeSourceDocumentIndex(
                document_name=document.source_file,
                source_blocks=[
                    RequirementMergeSourceBlockIndex(
                        id=node.node_id,
                        title=node.title,
                        children=list(node.sub_headings),
                    )
                    for node in _assignable_nodes_for_document(document)
                ],
            )
            for document in source_documents
        ],
    )


def _outline_input_payload(document_name: str, source_documents: list[SourceOutlineDocument]) -> dict:
    return _outline_input(document_name, source_documents).model_dump()


def _assignable_nodes(source_documents: list[SourceOutlineDocument]) -> list[SourceOutlineNode]:
    return [node for node in flatten_source_outline(source_documents) if node.must_assign]


def _assignable_nodes_for_document(document: SourceOutlineDocument) -> list[SourceOutlineNode]:
    return [node for node in flatten_nodes(document.nodes) if node.must_assign]


def _document_index(document: SourceOutlineDocument) -> dict:
    return {
        "document_code": document.document_code,
        "mapping_id": document.mapping_id,
        "source_file": document.source_file,
        "title_tree": [_node_index(node) for node in document.nodes],
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
        "node_role": node.node_role,
        "must_assign": node.must_assign,
        "children": [_node_index(child) for child in node.children],
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


def _move_parent_source_refs_to_leaf(section: TargetOutlineSection) -> None:
    for child in section.children:
        _move_parent_source_refs_to_leaf(child)
    if section.level not in {2, 3} or not section.children or not section.source_node_ids:
        return
    existing_ids = {child.section_id for child in section.children}
    base_id = f"{section.section_id}-leaf"
    overview_id = base_id
    index = 1
    while overview_id in existing_ids:
        overview_id = f"{base_id}-{index:02d}"
        index += 1
    section.children.insert(
        0,
        TargetOutlineSection(
            section_id=overview_id,
            parent_id=section.section_id,
            level=section.level + 1,
            title="概述",
            reason="系统将父章节来源下沉到叶子章节，父章节仅保留结构作用。",
            source_node_ids=list(section.source_node_ids),
            children=[],
        ),
    )
    section.source_node_ids = []


def _parse_source_node_ids(raw_value: Any) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    result: list[str] = []
    for item in raw_value:
        value = str(item or "").strip()
        if value:
            result.append(value)
    return result

