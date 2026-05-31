from __future__ import annotations

from app.schemas.requirement_merge import (
    OutlineAssignment,
    OutlineMergeConflict,
    OutlineSectionMergeResult,
    SourceOutlineDocument,
    SourceOutlineNode,
    TargetOutlineSection,
)
from app.services.requirement_merge_outline_service import flatten_target_outline
from app.services.requirement_source_outline_service import flatten_source_outline


def render_merged_markdown(
    document_name: str,
    source_documents: list[SourceOutlineDocument],
    target_outline: list[TargetOutlineSection],
    section_results: list[OutlineSectionMergeResult],
) -> str:
    nodes_by_id = {node.node_id: node for node in flatten_source_outline(source_documents)}
    results_by_id = {result.section_id: result for result in section_results}
    lines = [f"# {document_name}", ""]

    def has_renderable_content(section: TargetOutlineSection) -> bool:
        result = results_by_id.get(section.section_id)
        if result and result.blocks:
            return True
        return any(has_renderable_content(child) for child in section.children)

    def render_section(section: TargetOutlineSection) -> None:
        if section.level == 1:
            for child in section.children:
                render_section(child)
            return
        if not has_renderable_content(section):
            return
        heading_level = "#" * max(2, section.level)
        lines.extend([f"{heading_level} {section.title}", ""])
        result = results_by_id.get(section.section_id)
        if result:
            for block in result.blocks:
                if block.type == "paragraph" and block.content.strip():
                    lines.extend([block.content.strip(), ""])
                elif block.type == "bullet_list":
                    for item in block.items:
                        if item.strip():
                            lines.append(f"- {item.strip()}")
                    lines.append("")
                elif block.type == "table" and block.content.strip():
                    lines.extend([block.content.strip(), ""])
                elif block.type == "source_node_ref":
                    node = nodes_by_id.get(block.source_node_id)
                    if node and node.content_markdown.strip():
                        lines.extend([node.content_markdown.strip(), ""])
                elif block.type == "pending_clarification_ref" and block.content.strip():
                    lines.extend([f"- 待澄清：{block.content.strip()}", ""])
                elif block.type == "conflict_ref":
                    text = block.content.strip() or "存在冲突，详见待确认项。"
                    lines.extend([f"- 冲突：{text}", ""])
        for child in section.children:
            render_section(child)

    for section in target_outline:
        render_section(section)
    return "\n".join(lines).strip() + "\n"


def render_mapping_markdown(
    source_documents: list[SourceOutlineDocument],
    target_outline: list[TargetOutlineSection],
    assignments: list[OutlineAssignment],
    section_results: list[OutlineSectionMergeResult],
) -> str:
    nodes_by_id = {node.node_id: node for node in flatten_source_outline(source_documents)}
    sections_by_id = {section.section_id: section for section in flatten_target_outline(target_outline)}
    decisions_by_node = {}
    for result in section_results:
        for decision in result.decisions:
            decisions_by_node.setdefault(decision.source_node_id, []).append(decision)
    rows = [
        "# 段落映射",
        "",
        "## 来源文档",
        "",
        "| 代号 | 源文档 |",
        "| --- | --- |",
    ]
    for document in source_documents:
        rows.append(f"| {md_cell(document.document_code)} | {md_cell(document.source_file)} |")
    rows.extend(
        [
            "",
            "## 旧大纲到新大纲映射",
            "",
            "| 旧节点ID | 源文档 | 旧标题路径 | 新章节 | 处理方式 | 是否原文保留 | 原因 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for assignment in assignments:
        node = nodes_by_id.get(assignment.source_node_id)
        if not node:
            continue
        section = sections_by_id.get(assignment.target_section_id)
        section_title = section.title if section else ""
        decisions = decisions_by_node.get(node.node_id, [])
        status = "、".join(_decision_label(decision.status) for decision in decisions) or _assignment_label(assignment.assignment_type)
        preserved = "是" if node.preserve_original and any(decision.status in {"preserved_original", "merged_and_preserved"} for decision in decisions) else "否"
        rows.append(
            "| {node_id} | {source_file} | {heading_path} | {target} | {status} | {preserved} | {reason} |".format(
                node_id=md_cell(node.node_id),
                source_file=md_cell(node.source_file),
                heading_path=md_cell(" / ".join(node.heading_path)),
                target=md_cell(section_title or "-"),
                status=md_cell(status),
                preserved=preserved,
                reason=md_cell(_decision_reasons(decisions) or assignment.reason),
            )
        )
    return "\n".join(rows).strip() + "\n"


def render_conflicts_markdown(conflicts: list[OutlineMergeConflict], quality_issues: list[str]) -> str:
    rows = [
        "# 明显冲突与待确认",
        "",
        "| 冲突ID | 主题 | 涉及旧节点 | 差异描述 | 需要确认的问题 | 当前处理 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if conflicts:
        for conflict in conflicts:
            rows.append(
                "| {conflict_id} | {title} | {nodes} | {fragment_a} | {suggestion} | 待人工确认 |".format(
                    conflict_id=md_cell(conflict.conflict_id),
                    title=md_cell(conflict.title),
                    nodes=md_cell("、".join(conflict.source_node_ids)),
                    fragment_a=md_cell(conflict.fragment_a or conflict.fragment_b),
                    suggestion=md_cell(conflict.agent_suggestion),
                )
            )
    else:
        rows.append("| - | 无 | - | - | - | - |")
    rows.extend(["", "## 阻断原因", ""])
    rows.extend([f"- {issue}" for issue in quality_issues] or ["无"])
    return "\n".join(rows).strip() + "\n"


def collect_outline_conflicts(section_results: list[OutlineSectionMergeResult]) -> list[OutlineMergeConflict]:
    conflicts: list[OutlineMergeConflict] = []
    for result in section_results:
        for index, conflict in enumerate(result.conflicts, start=1):
            if not conflict.conflict_id:
                conflict.conflict_id = f"{result.section_id}-C{index:03d}"
            conflicts.append(conflict)
    return conflicts


def md_cell(value: str) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", "<br>").strip()


def _assignment_label(value: str) -> str:
    return {
        "primary": "合并",
        "reference": "引用",
        "appendix": "放入附录",
        "discarded_non_requirement": "非需求忽略",
        "pending_clarification": "放入待确认",
    }.get(value, value)


def _decision_label(value: str) -> str:
    return {
        "merged": "合并",
        "duplicate": "重复去重",
        "preserved_original": "原文保留",
        "merged_and_preserved": "合并+原文保留",
        "conflict": "放入待确认",
        "pending_clarification": "待澄清",
        "discarded": "丢弃",
    }.get(value, value)


def _decision_reasons(decisions) -> str:
    return "；".join(decision.reason for decision in decisions if decision.reason.strip())
