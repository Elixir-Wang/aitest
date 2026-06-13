"""
需求增强器

从 auto_resolved 的澄清项生成增强版需求文档
"""

from typing import List, Optional
from ..schemas import ClarificationItem


def generate_enhanced_requirement(
    original_markdown: str,
    auto_resolved_items: List[ClarificationItem],
) -> str:
    """
    生成增强版需求文档

    将 auto_resolved 的澄清项的答案补充到原始需求文档中

    Args:
        original_markdown: 原始需求文档
        auto_resolved_items: 自动解决的澄清项列表

    Returns:
        增强后的 markdown 文档，补充内容用特殊标记高亮
    """
    if not auto_resolved_items:
        return original_markdown

    # 按模块分组
    items_by_module = _group_by_module(auto_resolved_items)

    # 构建增强版文档
    sections = []

    # 1. 添加说明头部
    sections.append("# 增强版需求文档\n")
    sections.append("> 本文档基于原始需求，补充了从辅助文档中自动解决的问题\n")
    sections.append("> 标记为 **[自动补充]** 的内容来自辅助文档的增强\n")
    sections.append("\n---\n")

    # 2. 添加原始需求
    sections.append("## 原始需求内容\n")
    sections.append(original_markdown)
    sections.append("\n---\n")

    # 3. 添加自动补充的内容
    sections.append("## 自动补充的内容\n")
    sections.append("> 以下内容从辅助文档中提取，用于补充原始需求中缺失或模糊的部分\n\n")

    for module_key, items in items_by_module.items():
        module_name = items[0].module_name if items else "通用"

        sections.append(f"### {module_name}\n")

        for item in items:
            # 构建补充条目
            enhancement_block = _build_enhancement_block(item)
            sections.append(enhancement_block)
            sections.append("\n")

    return "\n".join(sections)


def _group_by_module(items: List[ClarificationItem]) -> dict[str, List[ClarificationItem]]:
    """按模块分组澄清项"""
    groups = {}
    for item in items:
        module_key = item.module_key or "general"
        if module_key not in groups:
            groups[module_key] = []
        groups[module_key].append(item)
    return groups


def _build_enhancement_block(item: ClarificationItem) -> str:
    """
    构建单个增强块

    返回格式：
    > **[自动补充]** {问题}
    >
    > **补充内容**: {suggested_fix 或 recommended_options}
    >
    > **来源**: {evidence 中的文档}
    >
    > **影响**: {impact}
    """
    lines = []

    # 问题标题
    lines.append(f"> **[自动补充]** {item.question}")
    lines.append(">")

    # 当前文本（如果有）
    if item.current_text:
        lines.append(f"> **原始描述**: {item.current_text}")
        lines.append(">")

    # 补充内容
    if item.suggested_fix:
        lines.append(f"> **补充内容**: {item.suggested_fix}")
    elif item.recommended_options:
        lines.append("> **建议选项**:")
        for opt in item.recommended_options:
            lines.append(f">   - {opt.label}: {opt.answer_markdown}")
            if opt.rationale:
                lines.append(f">     - 理由: {opt.rationale}")
    lines.append(">")

    # 来源证据
    if item.evidence:
        sources = set()
        for ev in item.evidence:
            sources.add(ev.filename)
        lines.append(f"> **来源**: {', '.join(sources)}")
        lines.append(">")

    # 影响说明
    if item.impact:
        lines.append(f"> **影响**: {item.impact}")

    return "\n".join(lines)


def generate_inline_enhanced_requirement(
    original_markdown: str,
    auto_resolved_items: List[ClarificationItem],
) -> str:
    """
    生成行内增强版需求文档（实验性）

    尝试将补充内容直接插入到相关位置，而不是单独列出

    注意：这个函数需要更复杂的文本分析和插入逻辑，当前版本为占位实现

    Args:
        original_markdown: 原始需求文档
        auto_resolved_items: 自动解决的澄清项列表

    Returns:
        行内增强后的 markdown 文档
    """
    # TODO: 实现行内插入逻辑
    # 需要：
    # 1. 解析 markdown 结构
    # 2. 根据 current_text 定位插入位置
    # 3. 在相关段落后插入补充内容

    # 当前返回分块版本
    return generate_enhanced_requirement(original_markdown, auto_resolved_items)


def get_auto_resolved_items(all_items: List[ClarificationItem]) -> List[ClarificationItem]:
    """
    从所有澄清项中提取 auto_resolved 的项

    Args:
        all_items: 所有澄清项

    Returns:
        仅包含 auto_resolved 状态的项
    """
    return [
        item for item in all_items
        if item.resolution_status == "auto_resolved"
    ]


def get_pending_items(all_items: List[ClarificationItem]) -> List[ClarificationItem]:
    """
    从所有澄清项中提取待处理的项（用于前端"待处理内容"tab）

    Args:
        all_items: 所有澄清项

    Returns:
        仅包含 needs_manual 和 has_suggestions 状态的项
    """
    return [
        item for item in all_items
        if item.resolution_status in ["needs_manual", "has_suggestions"]
    ]
