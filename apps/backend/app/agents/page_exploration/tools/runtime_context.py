"""Runtime browser context for page exploration tools."""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator

from app.agents.page_exploration.playwright.schemas import (
    AccessibilityNodeInfo,
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
        raise BrowserSessionError("Page exploration browser session is not bound.")
    result = session.navigate(url)
    return NavigateResult(url=str(result.get("url") or url), success=True)


def click_with_runtime_context(locator: str) -> ClickResult | None:
    """Click via the long-lived browser session.

    locator 支持两种形式：
    1) Playwright Locator 字符串（推荐，跨调用稳定）：
       - getByRole('button', { name: '创建智能体' })
       - getByRole('treeitem', { name: '自主规划 Agent' })
       - getByLabel('用户名')
       - getByTestId('user-avatar')
       - getByText('提交订单')
       - getByPlaceholder('请输入手机号')
    2) 上一次 snap 返回的 element.id（形如 "button-create-agent-001"）：
       - 优点：snap 已验证 unique + visible
       - 缺点：页面变化后 id 会失效，需重新 snap

    与前一版不同：失败不再自动 observe（observe 会让 LLM 拿到的旧 id
    仍然在上下文中，下一轮 click 同样失败，形成物理死循环）。
    改为把错误原样透传给 LLM，由它通过 playwright_snap_tool 主动
    刷新或直接改用 Playwright Locator 字符串重试。
    """
    session = _browser_session.get()
    if session is None:
        raise BrowserSessionError("Page exploration browser session is not bound.")
    try:
        session.click(locator)
    except BrowserSessionError as exc:
        # 把错误原样透出：让 LLM 看见具体的 element_id / 完整错误信息
        # 错误信息（由 JS 端 classifyActionError 生成）已经包含 actionable 提示
        return ClickResult(success=False, error=str(exc))
    return ClickResult(success=True)


def fill_with_runtime_context(locator: str, value: str) -> FillResult | None:
    """Fill via the long-lived browser session. 接受 ref 与 Playwright Locator 字符串两种形式。

    失败时同样不再自动 observe，避免物理死循环。
    """
    session = _browser_session.get()
    if session is None:
        raise BrowserSessionError("Page exploration browser session is not bound.")
    try:
        session.fill(locator, value)
    except BrowserSessionError as exc:
        return FillResult(success=False, error=str(exc))
    return FillResult(success=True)


def snapshot_with_runtime_context(url: str | None = None) -> SnapshotResult | None:
    session = _browser_session.get()
    if session is None:
        raise BrowserSessionError("Page exploration browser session is not bound.")
    if url:
        session.navigate(url)
    result = session.observe()
    return SnapshotResult(
        url=str(result.get("url") or url or ""),
        title=str(result.get("title") or ""),
        page_text_summary=str(result.get("page_text_summary") or ""),
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
        accessibility_tree=[
            AccessibilityNodeInfo(
                id=str(node.get("id") or ""),
                role=str(node.get("role") or ""),
                name=str(node.get("name") or ""),
                level=node.get("level") if isinstance(node.get("level"), int) else None,
                checked=node.get("checked") if isinstance(node.get("checked"), bool) else None,
                disabled=node.get("disabled") if isinstance(node.get("disabled"), bool) else None,
                expanded=node.get("expanded") if isinstance(node.get("expanded"), bool) else None,
            )
            for node in result.get("accessibility_tree", [])
            if isinstance(node, dict)
        ],
        visible_text_blocks=[
            str(item).strip()
            for item in result.get("visible_text_blocks", [])
            if str(item).strip()
        ],
    )
