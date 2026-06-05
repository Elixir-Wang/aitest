from __future__ import annotations

from app.agents.requirement_merge.schemas import RequirementMergeSectionInput, RequirementMergeSectionSourceBlock
from app.agents.requirement_merge.service import merge_requirement_section
from app.schemas.requirement_merge import (
    OutlineAssignment,
    OutlineMergeConflict,
    OutlineSectionBlock,
    OutlineSectionDecision,
    OutlineSectionMergeResult,
    SourceOutlineDocument,
    SourceOutlineNode,
    TargetOutlineSection,
)
from app.services.requirement_merge.outline_service import assignable_target_sections
from app.services.requirement_merge.outline_assignment_service import assignable_source_nodes


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
                    status="merged",
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
    output = await merge_requirement_section(
        RequirementMergeSectionInput(
            module_id=section.section_id,
            module_title=section.title,
            source_blocks=[
                RequirementMergeSectionSourceBlock(
                    id=node.node_id,
                    title=node.title,
                    children=list(node.sub_headings),
                    markdown=node.content_markdown,
                )
                for node in source_nodes
            ],
        )
    )
    section_result = _section_output_to_result(section, output, source_nodes)
    issues = validate_section_result(section_result, source_nodes)
    if issues:
        raise ValueError("；".join(issues))
    return section_result


def _section_output_to_result(section: TargetOutlineSection, output, source_nodes: list[SourceOutlineNode]) -> OutlineSectionMergeResult:
    source_ids = {node.node_id for node in source_nodes}
    decisions = [
        OutlineSectionDecision(
            section_id=section.section_id,
            source_node_id=item.source_id,
            status=item.status,
            target_heading=section.title,
            reason=item.reason or "模块正文归并处理。",
        )
        for item in output.coverage
        if item.source_id in source_ids
    ]
    blocks: list[OutlineSectionBlock] = []
    for item in output.sections:
        if item.section_heading.strip():
            blocks.append(OutlineSectionBlock(type="paragraph", content=f"### {item.section_heading.strip()}"))
        for paragraph in item.markdown_blocks:
            if paragraph.strip():
                blocks.append(OutlineSectionBlock(type="paragraph", content=paragraph.strip()))
    conflicts = [
        OutlineMergeConflict(
            conflict_id=item.conflict_id,
            title=item.title,
            conflict_type=item.conflict_type,
            severity=item.severity,
            source_node_ids=[source_id for source_id in item.source_ids if source_id in source_ids],
            fragment_a=item.fragment_a,
            fragment_b=item.fragment_b,
            agent_suggestion=item.agent_suggestion,
        )
        for item in output.conflicts
    ]
    return OutlineSectionMergeResult(
        section_id=section.section_id,
        blocks=blocks,
        decisions=decisions,
        conflicts=conflicts,
    )


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
    return issues

