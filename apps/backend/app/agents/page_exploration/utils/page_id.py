"""Page identity utilities shared between agent tools and service layer.

所有页面 ID 计算必须走这里，确保 agent 和 service 对同一
normalized_path 产生完全一致的 page_id。
"""
from __future__ import annotations


def make_page_id(normalized_path: str) -> str:
    """把 URL 路径（去除协议/host/query 的 path）转换为稳定的 page_id。

    规则：
    - 去除首尾斜杠，空路径 → "home"
    - 输入应为不带 query 的 canonical path
    - ?, &, =, #, %, : → -（仅兜底清理旧调用）
    - / → -
    - 合并连续 -
    - 过滤空段
    - 前缀 "page-"

    例：
        /workspace/botSetting
        → page-workspace-botSetting
    """
    value = (normalized_path or "").strip("/") or "home"
    for char in ("?", "&", "=", "#", "%", ":"):
        value = value.replace(char, "-")
    value = value.replace("/", "-")
    value = "-".join(part for part in value.split("-") if part)
    return f"page-{value or 'home'}"

