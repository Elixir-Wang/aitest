"""Pydantic schemas for Playwright CLI results."""

from typing import Optional
from pydantic import BaseModel, Field


class ElementInfo(BaseModel):
    """Information about a single page element."""
    ref: str
    role: str
    name: str
    text: Optional[str] = None
    visible: bool


class SnapshotResult(BaseModel):
    """Result from playwright-cli snap command."""
    url: str
    title: str
    elements: list[ElementInfo]
    raw_output: str
    error: Optional[str] = None


class NavigateResult(BaseModel):
    """Result from playwright-cli navigate command."""
    url: str
    success: bool
    error: Optional[str] = None


class ClickResult(BaseModel):
    """Result from playwright-cli click command."""
    success: bool
    error: Optional[str] = None


class FillResult(BaseModel):
    """Result from playwright-cli fill command."""
    success: bool
    error: Optional[str] = None
