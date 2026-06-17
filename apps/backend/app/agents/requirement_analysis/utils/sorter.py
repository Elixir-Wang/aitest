"""
优先级排序工具

用于对待澄清项进行优先级排序
"""

from app.agents.requirement_analysis.clarification.schemas import ClarificationItem


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

__all__ = [
    "sort_clarification_items",
]
