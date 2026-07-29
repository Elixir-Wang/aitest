"""Pydantic schemas for page exploration browser tool results."""
from typing import Any

from pydantic import BaseModel


class ElementInfo(BaseModel):
    """Information about a single executable page element."""

    element_id: str
    role: str
    action_locator: str = ""
    role_source: str = ""
    name: str
    text: str | None = None
    value: str = ""
    overlay_id: str | None = None
    context: dict[str, Any] = {}
    action_type: str = ""
    primary_selector: dict[str, Any] | None = None
    fallback_selector: dict[str, Any] | None = None
    visible: bool
    # 元素到 body 的祖先链（从直接父元素到 body，role + name，最多 5 层）。
    # 用于让 LLM 直接从 DOM 结构判断元素所在上下文，不再依赖 JS 枚举 dialog 容器。
    ancestor_chain: list[dict[str, str]] = []


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

    observation_id: str = ""
    url: str
    title: str
    interaction_scope: str = "page"
    overlay: dict[str, Any] | None = None
    overlay_registry: dict[str, Any] = {}
    state_context: dict[str, Any] = {}
    elements: list[ElementInfo]
    accessibility_tree: list[AccessibilityNodeInfo] = []
    visible_text_blocks: list[str] = []
    collections: list[dict[str, Any]] = []
    page_text_summary: str = ""
    state_signature: str = ""
    error: str | None = None


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
    verification_required: bool = True
    next_step_hint: str = ""
    risk: str = ""
    element_key: str = ""


class FillResult(BaseModel):
    """Result from a browser fill."""

    success: bool
    error: str | None = None
    failure: ActionFailure | None = None
    effective_locator: str | None = None
    verification_required: bool = True
    next_step_hint: str = ""
    risk: str = ""
    element_key: str = ""
