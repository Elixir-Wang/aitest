"""state.id 模板生成; {page_id}__{type}__{seq3}; agent 不命名。"""
from __future__ import annotations

from typing import Final

STATE_ID_PATTERN: Final = r"^[a-zA-Z0-9_\-]+__(root|dialog|drawer|form|list)__[0-9]{3}$"


def make_state_id(page_id: str, state_type: str, seq: int) -> str:
    """生成 state.id。seq 从 1 起。"""
    if seq < 1:
        raise ValueError(f"seq must be >= 1, got {seq}")
    return f"{page_id}__{state_type}__{seq:03d}"
