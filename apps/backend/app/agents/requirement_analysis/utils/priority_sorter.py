"""
优先级排序工具

用于对待澄清项进行优先级排序（v3 schema）
"""

from typing import Literal

from app.agents.requirement_analysis.schemas import ClarificationItem


def sort_clarification_items(
    items: list[ClarificationItem],
) -> list[ClarificationItem]:
    """
    对待澄清项按优先级排序

    排序规则：
    1. priority: P0 → P1 → P2 → P3
    2. resolution_status: needs_input/needs_research → has_options → auto_resolved
    """

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    status_order = {
        "needs_input": 0,
        "needs_research": 0,
        "has_options": 1,
        "auto_resolved": 2,
    }

    def get_priority_key(item: ClarificationItem) -> tuple[int, int]:
        return (
            priority_order.get(item.priority, 999),
            status_order.get(item.resolution_status, 999),
        )

    return sorted(items, key=get_priority_key)


def group_by_priority(
    items: list[ClarificationItem],
) -> dict[Literal["P0", "P1", "P2", "P3"], list[ClarificationItem]]:
    """按 v3 优先级分组"""
    groups: dict[str, list[ClarificationItem]] = {
        "P0": [],
        "P1": [],
        "P2": [],
        "P3": [],
    }

    for item in items:
        if item.priority in groups:
            groups[item.priority].append(item)

    return groups  # type: ignore[return-value]


def group_by_source_stage(
    items: list[ClarificationItem],
) -> dict[str, list[ClarificationItem]]:
    """按来源阶段分组"""
    groups = {
        "understanding": [],
        "completeness": [],
        "clarity": [],
        "testability": [],
        "consistency": [],
    }

    for item in items:
        if item.source_stage in groups:
            groups[item.source_stage].append(item)

    return groups


def group_by_resolution_status(
    items: list[ClarificationItem],
) -> dict[str, list[ClarificationItem]]:
    """按解答状态分组"""
    groups = {
        "auto_resolved": [],
        "has_options": [],
        "needs_input": [],
        "needs_research": [],
    }

    for item in items:
        if item.resolution_status in groups:
            groups[item.resolution_status].append(item)

    return groups


# 兼容旧名称
group_by_severity = group_by_priority
group_by_source = group_by_source_stage


__all__ = [
    "sort_clarification_items",
    "group_by_priority",
    "group_by_severity",
    "group_by_source",
    "group_by_source_stage",
    "group_by_resolution_status",
]
