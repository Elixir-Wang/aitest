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


class NavigateResult(BaseModel):
    """Result from browser navigation."""

    url: str
    success: bool
    error: str | None = None


class ClickResult(BaseModel):
    """Result from a browser click."""

    success: bool
    error: str | None = None


class FillResult(BaseModel):
    """Result from a browser fill."""

    success: bool
    error: str | None = None
