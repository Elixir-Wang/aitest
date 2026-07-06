"""Pydantic schemas for page exploration browser tool results."""
from typing import Any

from pydantic import BaseModel


class ElementInfo(BaseModel):
    """Information about a single executable page element."""

    role: str
    role_source: str = ""
    name: str
    text: str | None = None
    action_type: str = ""
    primary_selector: dict[str, Any] | None = None
    fallback_selector: dict[str, Any] | None = None
    visible: bool
    # 元素所属 dialog（observePage 在收集 elementFacts 时按 DOM 树归属标记）
    dialog_id: str | None = None


class DialogInfo(BaseModel):
    """A dialog / modal currently visible on the page.

    来自 observePage() 收集的 facts.dialogs 列表（line 1000-1007 of browser-session.mjs）。
    之前 SnapshotResult schema 缺这个字段，被 unmarshal 时丢弃。
    """

    id: str
    title: str = ""
    role: str = ""  # dialog / alertdialog


class AccessibilityNodeInfo(BaseModel):
    """Compact accessibility node for model-readable page state."""

    id: str = ""
    role: str = ""
    name: str = ""
    level: int | None = None
    checked: bool | None = None
    disabled: bool | None = None
    expanded: bool | None = None


class SnapshotResult(BaseModel):
    """Result from a browser page snapshot."""

    url: str
    title: str
    elements: list[ElementInfo]
    accessibility_tree: list[AccessibilityNodeInfo] = []
    visible_text_blocks: list[str] = []
    page_text_summary: str = ""
    error: str | None = None
    # 页面级 dialog 列表（observePage 已经收集）
    dialogs: list[DialogInfo] = []
    # 当前 active dialog 的 id（LLM 后续动作 scope 锚定）
    active_dialog_id: str | None = None


class NavigateResult(BaseModel):
    """Result from browser navigation."""

    url: str
    success: bool
    error: str | None = None


# 统一的错误类型枚举（与 browser-session.mjs 的 classifyActionError 对齐）
ACTION_ERROR_TYPES = {
    "pointer_intercepted",
    "locator_not_unique",
    "locator_timeout",
    "not_visible",
    "action_failed",
}


class ActionFailure(BaseModel):
    """结构化的执行失败信息，方便 LLM 直接据此选择下一步。"""

    error_type: str = "action_failed"
    summary: str = ""
    raw: str = ""
    # 兼容旧 runner：历史上 strict mode fail 可能返回 recovered warning。
    recovered: bool = False
    recovery_warning: str = ""


class ClickResult(BaseModel):
    """Result from a browser click.

    透传结构化失败：LLM 看到 success=False 时可直接读 error_type 判断下一步。
    """

    success: bool
    error: str | None = None
    failure: ActionFailure | None = None
    # 真正命中的元素的可复用 locator 字符串（recovered=true 时给 LLM 一份能继续用的）
    effective_locator: str | None = None


class FillResult(BaseModel):
    """Result from a browser fill."""

    success: bool
    error: str | None = None
    failure: ActionFailure | None = None
    effective_locator: str | None = None
