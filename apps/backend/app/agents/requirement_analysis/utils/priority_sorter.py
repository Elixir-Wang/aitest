"""
优先级排序工具

用于对待澄清项进行优先级排序
"""

from typing import Literal
from app.agents.requirement_analysis.schemas_v2 import ClarificationItem


def sort_clarification_items(
    items: list[ClarificationItem],
) -> list[ClarificationItem]:
    """
    对待澄清项按优先级排序

    排序规则（7级优先级）：
    1. (blocker, needs_manual) - 最高优先级
    2. (blocker, has_suggestions)
    3. (major, needs_manual)
    4. (major, has_suggestions)
    5. (minor, needs_manual)
    6. (minor, has_suggestions)
    7. (*, auto_resolved) - 最低优先级

    Args:
        items: 待排序的澄清项列表

    Returns:
        排序后的列表
    """

    def get_priority_key(item: ClarificationItem) -> tuple[int, int]:
        """
        获取排序键

        Returns:
            (severity_priority, status_priority)
        """
        severity_priority = {
            "blocker": 0,
            "major": 1,
            "minor": 2,
        }

        status_priority = {
            "needs_manual": 0,
            "has_suggestions": 1,
            "auto_resolved": 2,
        }

        return (
            severity_priority.get(item.severity, 999),
            status_priority.get(item.resolution_status, 999),
        )

    return sorted(items, key=get_priority_key)


def group_by_severity(
    items: list[ClarificationItem],
) -> dict[Literal["blocker", "major", "minor"], list[ClarificationItem]]:
    """
    按严重程度分组

    Args:
        items: 澄清项列表

    Returns:
        按严重程度分组的字典
    """
    groups = {
        "blocker": [],
        "major": [],
        "minor": [],
    }

    for item in items:
        if item.severity in groups:
            groups[item.severity].append(item)

    return groups


def group_by_source(
    items: list[ClarificationItem],
) -> dict[str, list[ClarificationItem]]:
    """
    按来源分组

    Args:
        items: 澄清项列表

    Returns:
        按来源分组的字典
    """
    groups = {
        "understanding": [],
        "completeness": [],
        "clarity": [],
        "testability": [],
        "consistency": [],
    }

    for item in items:
        if item.source in groups:
            groups[item.source].append(item)

    return groups


def group_by_resolution_status(
    items: list[ClarificationItem],
) -> dict[str, list[ClarificationItem]]:
    """
    按解答状态分组

    Args:
        items: 澄清项列表

    Returns:
        按解答状态分组的字典
    """
    groups = {
        "auto_resolved": [],
        "has_suggestions": [],
        "needs_manual": [],
    }

    for item in items:
        if item.resolution_status in groups:
            groups[item.resolution_status].append(item)

    return groups


__all__ = [
    "sort_clarification_items",
    "group_by_severity",
    "group_by_source",
    "group_by_resolution_status",
]
