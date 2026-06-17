"""
需求增强器

从 auto_resolved 的澄清项生成增强版需求文档
"""

from typing import List

from app.agents.requirement_analysis.clarification.schemas import ClarificationItem


def generate_enhanced_requirement(
    original_markdown: str,
    auto_resolved_items: List[ClarificationItem],
) -> str:
    """
    生成增强版需求文档

    将 auto_resolved 的澄清项的答案补充到原始需求文档中
    """
    if not auto_resolved_items:
        return original_markdown

    items_by_module = _group_by_module(auto_resolved_items)
    sections = [
        "# 增强版需求文档\n",
        "> 本文档基于原始需求，补充了从辅助文档中自动解决的问题\n",
        "> 标记为 **[自动补充]** 的内容来自辅助文档的增强\n",
        "\n---\n",
        "## 原始需求内容\n",
        original_markdown,
        "\n---\n",
        "## 自动补充的内容\n",
        "> 以下内容从辅助文档中提取，用于补充原始需求中缺失或模糊的部分\n\n",
    ]

    for _, items in items_by_module.items():
        module_name = items[0].module_name if items else "通用"
        sections.append(f"### {module_name}\n")
        for item in items:
            sections.append(_build_enhancement_block(item))
            sections.append("\n")

    return "\n".join(sections)


def _group_by_module(items: List[ClarificationItem]) -> dict[str, List[ClarificationItem]]:
    groups: dict[str, List[ClarificationItem]] = {}
    for item in items:
        module_key = item.module_key or "general"
        groups.setdefault(module_key, []).append(item)
    return groups


def _build_enhancement_block(item: ClarificationItem) -> str:
    lines = [
        f"> **[自动补充]** {item.title}",
        ">",
        f"> **裁决点**: {item.decision_point}",
        ">",
    ]

    if item.source_excerpt:
        lines.append(f"> **原始描述**: {item.source_excerpt}")
        lines.append(">")

    if item.auto_resolution:
        lines.append(f"> **补充内容**: {item.auto_resolution}")
    elif item.options:
        lines.append("> **建议选项**:")
        for option in item.options:
            lines.append(f">   - {option.label}: {option.description}")
            if option.source:
                lines.append(f">     - 来源: {option.source}")
    lines.append(">")

    if item.auto_resolution_source:
        lines.append(f"> **来源**: {item.auto_resolution_source}")
        lines.append(">")

    if item.test_impact:
        lines.append(f"> **测试影响**: {item.test_impact}")

    return "\n".join(lines)


def get_auto_resolved_items(all_items: List[ClarificationItem]) -> List[ClarificationItem]:
    return [item for item in all_items if item.resolution_status == "auto_resolved"]


__all__ = [
    "generate_enhanced_requirement",
    "get_auto_resolved_items",
]
