"""toast / snackbar 启发式过滤：role=status/alert 且短 timeout 或已知容器, 都不进 state 树。"""
from __future__ import annotations

from typing import Iterable

_KNOWN_TOAST_CONTAINERS = (
    ".ant-message",
    ".ant-notification",
    "#root > .toast-container",
    ".toast",
    ".snackbar",
)

_DIALOG_LIKE = {"dialog", "alertdialog"}


def is_toast(info: dict) -> bool:
    role = info.get("role")
    aria_modal = info.get("aria_modal")
    if role in _DIALOG_LIKE or aria_modal is True:
        return False

    timeout = info.get("timeout_ms")
    dom_path = info.get("dom_path") or ""

    known_container = any(seg in dom_path for seg in _KNOWN_TOAST_CONTAINERS)
    short_timeout = isinstance(timeout, (int, float)) and timeout <= 5000

    if role in {"status", "alert"}:
        return short_timeout or known_container

    # 没有任何 role 标签但命中已知容器 -> 认为是 toast
    return known_container and role is None


def filter_snapshot(snapshot: Iterable[dict]) -> list[dict]:
    return [el for el in snapshot if not is_toast(el)]
