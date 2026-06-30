"""Runtime browser context for page exploration tools."""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator

from app.agents.page_exploration.playwright.schemas import (
    ClickResult,
    ElementInfo,
    FillResult,
    NavigateResult,
    SnapshotResult,
)
from app.services.exploration.browser_session import BrowserSessionError, PlaywrightBrowserSession


_browser_session: ContextVar[PlaywrightBrowserSession | None] = ContextVar(
    "page_exploration_browser_session",
    default=None,
)


@contextmanager
def browser_session_context(
    *,
    start_url: str,
    storage_state_path: Path | str | None = None,
) -> Iterator[None]:
    """Bind a long-lived browser session to page exploration tool calls."""
    if not storage_state_path:
        yield
        return

    with PlaywrightBrowserSession(
        start_url=start_url,
        storage_state_path=storage_state_path,
    ) as session:
        token = _browser_session.set(session)
        try:
            yield
        finally:
            _browser_session.reset(token)


def navigate_with_runtime_context(url: str) -> NavigateResult | None:
    session = _browser_session.get()
    if session is None:
        return None
    result = session.navigate(url)
    return NavigateResult(url=str(result.get("url") or url), success=True)


def click_with_runtime_context(locator: str) -> ClickResult | None:
    session = _browser_session.get()
    if session is None or not _looks_like_browser_session_element_id(locator):
        return None
    try:
        session.click(locator)
    except BrowserSessionError as exc:
        if _is_stale_element_error(exc):
            session.observe()
            return ClickResult(success=False, error=f"stale_ref: {exc}")
        raise
    return ClickResult(success=True)


def fill_with_runtime_context(locator: str, value: str) -> FillResult | None:
    session = _browser_session.get()
    if session is None or not _looks_like_browser_session_element_id(locator):
        return None
    try:
        session.fill(locator, value)
    except BrowserSessionError as exc:
        if _is_stale_element_error(exc):
            session.observe()
            return FillResult(success=False, error=f"stale_ref: {exc}")
        raise
    return FillResult(success=True)


def snapshot_with_runtime_context(url: str | None = None) -> SnapshotResult | None:
    session = _browser_session.get()
    if session is None:
        return None
    if url:
        session.navigate(url)
    result = session.observe()
    return SnapshotResult(
        url=str(result.get("url") or url or ""),
        title=str(result.get("title") or ""),
        elements=[
            ElementInfo(
                ref=str(element.get("id") or element.get("ref") or ""),
                role=str(element.get("role") or ""),
                name=str(element.get("name") or ""),
                text=element.get("text"),
                visible=bool(element.get("visible", True)),
            )
            for element in result.get("elements", [])
            if isinstance(element, dict)
        ],
        raw_output=str(result.get("text") or result.get("raw_output") or ""),
    )


def _looks_like_browser_session_element_id(value: str) -> bool:
    stripped = str(value or "").strip()
    if not stripped or any(char in stripped for char in "'\"(){}[] "):
        return False
    return "-" in stripped or stripped.startswith("e")


def _is_stale_element_error(error: Exception) -> bool:
    return "Unknown element id:" in str(error)
