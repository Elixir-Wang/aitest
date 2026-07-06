"""Runtime browser context for page exploration tools."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator, Any, Mapping

from app.agents.page_exploration.playwright.schemas import (
    AccessibilityNodeInfo,
    ActionFailure,
    ClickResult,
    DialogInfo,
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


def _enrich_locator_not_unique_summary(raw_summary: str, error_type: str, raw: str) -> str:
    """locator_not_unique 时给 summary 追加消歧指引，让 LLM 知道下一步怎么走。

    加什么：
    1. 保留原文数字（"matched 3 elements"）
    2. 明确告诉 LLM 重新 snap 看 match_groups
    3. 给出可执行的下一步模板（filter + hasText / 父级容器）

    why: 单纯"匹配 N 个"对 LLM 没用——LLM 不知道 N 个匹配各自是什么；
    重新 snap 后能在 match_groups[(name, role)].candidates 看到 N 个候选的位置，
    按 dialog_id / context_hint 区分。
    """
    if error_type != "locator_not_unique":
        return raw_summary
    # raw 通常包含 "Locator matched N elements: ..." 形式
    if not raw_summary.rstrip().endswith("。"):
        raw_summary = raw_summary.rstrip() + "。"
    return (
        f"{raw_summary} "
        "再次调用 playwright_snap_tool 查响应里 match_groups 字段，"
        "找到 (name, role) 对应组的 candidates 列表（每项含 dialog_id 与 primary_selector_code），"
        "按上下文（弹窗内 / 主页面）选用 filter({ hasText }) 或父级容器链式定位。"
    )


def _parse_action_result(
    result: Mapping[str, Any],
    *,
    raw_expr: str,
    default_error: str,
) -> dict:
    """把 Node 端 action_result 解析成 LLM 友好的结构化字段。

    协议（与 browser-session.mjs 对齐）：
    - success=true            → {"success": True, "effective_locator": str|None}
    - success=false           → {"success": False,
                                  "failure": ActionFailure,
                                  "effective_locator": str|None}
    - 异常（status: error）   → {"success": False,
                                  "failure": ActionFailure(error_type="action_failed", ...)}
    """
    action = result.get("action_result") or result
    if not isinstance(action, Mapping):
        action = {}

    failure_raw = action.get("failure") or {}
    if not isinstance(failure_raw, Mapping):
        failure_raw = {}

    # 若 Node 端没给 failure 字段（兼容旧版本），降级用 default_error 兜底
    error_type = str(failure_raw.get("error_type") or "action_failed")
    raw_summary = str(failure_raw.get("summary") or default_error or "动作执行失败")
    raw = str(
        failure_raw.get("raw")
        or action.get("error")
        or default_error
        or "动作执行失败"
    )
    recovered = bool(failure_raw.get("recovered", False))
    recovery_warning = str(failure_raw.get("recovery_warning") or "")
    # locator_not_unique 时 summary 必须指引 LLM 怎么消歧：
    # 单纯说"匹配 3 个"对 LLM 无信息量，需要：
    # 1. 保留原始数字（让 LLM 知道歧义程度）
    # 2. 提示重新 snap 看 match_groups[(name, role)].candidates 列表
    # 3. 提示用 filter / hasText / has 缩小范围（已有 prompt 模式）
    summary = _enrich_locator_not_unique_summary(raw_summary, error_type, raw)
    failure = ActionFailure(
        error_type=error_type,
        summary=summary,
        raw=raw,
        recovered=recovered,
        recovery_warning=recovery_warning,
    )

    if action.get("success") is True:
        parsed = {
            "success": True,
            "effective_locator": action.get("effective_locator") or raw_expr,
        }
        if failure_raw:
            parsed["failure"] = failure
        return parsed

    return {
        "success": False,
        "failure": failure,
        "effective_locator": action.get("effective_locator") or raw_expr,
    }


def click_with_runtime_context(locator: str) -> ClickResult | None:
    """Click via the long-lived browser session.

    locator 优先使用可复用的 Playwright Locator 字符串：
       - getByRole('button', { name: '创建智能体' })
       - getByRole('treeitem', { name: '自主规划 Agent' })
       - getByLabel('用户名')
       - getByText('提交订单')
       - getByPlaceholder('请输入手机号')
       - getByTestId('user-avatar')
       - getByRole('listitem').filter({ hasText: '自主规划' })
              .getByRole('button', { name: '编辑' })  # 链式 filter
       - page.locator('[role="popover"]').filter({ hasText: '自主规划 Agent' })
              .getByText('能够自主规划任务')  # 浮层/卡片容器内定位
       - page.locator('[data-testid="workspace-nav"]')  # 仅在以上定位器都不可用时兜底

    失败结构化透传：返回 success=False + failure(error_type, summary, raw, recovered)
    - error_type ∈ {pointer_intercepted, locator_not_unique, locator_timeout, not_visible, action_failed}
    - recovered=true 仅兼容历史 runner 的降级执行结果；后续应改用更精确的链式定位器。
    - 不要用 .first() / .nth() 解决歧义；必须用容器、hasText 或 has 缩小到唯一元素。
    """
    session = _browser_session.get()
    if session is None:
        raise BrowserSessionError("Page exploration browser session is not bound.")
    try:
        result = session.click(locator)
    except BrowserSessionError as exc:
        # Node 端协议层崩溃 → action_failed
        return ClickResult(
            success=False,
            error=str(exc),
            failure=ActionFailure(
                error_type="action_failed",
                summary="浏览器会话协议错误。",
                raw=str(exc),
            ),
            effective_locator=locator,
        )

    parsed = _parse_action_result(
        result,
        raw_expr=locator,
        default_error=f"Locator did not resolve to a visible element: {locator}",
    )
    if parsed["success"]:
        return ClickResult(
            success=True,
            failure=parsed.get("failure"),
            effective_locator=parsed["effective_locator"],
        )

    failure: ActionFailure = parsed["failure"]
    return ClickResult(
        success=False,
        # 给 LLM 看的"一句话错误"，优先级：summary > raw
        error=failure.summary or failure.raw,
        failure=failure,
        effective_locator=parsed["effective_locator"],
    )


def fill_with_runtime_context(locator: str, value: str) -> FillResult | None:
    """Fill via the long-lived browser session. 只接受可复用 Playwright Locator 字符串。

    失败结构化透传，语义与 click_with_runtime_context 一致。
    """
    session = _browser_session.get()
    if session is None:
        raise BrowserSessionError("Page exploration browser session is not bound.")
    try:
        result = session.fill(locator, value)
    except BrowserSessionError as exc:
        return FillResult(
            success=False,
            error=str(exc),
            failure=ActionFailure(
                error_type="action_failed",
                summary="浏览器会话协议错误。",
                raw=str(exc),
            ),
            effective_locator=locator,
        )

    parsed = _parse_action_result(
        result,
        raw_expr=locator,
        default_error=f"Locator did not resolve to a visible element: {locator}",
    )
    if parsed["success"]:
        return FillResult(
            success=True,
            failure=parsed.get("failure"),
            effective_locator=parsed["effective_locator"],
        )

    failure: ActionFailure = parsed["failure"]
    return FillResult(
        success=False,
        error=failure.summary or failure.raw,
        failure=failure,
        effective_locator=parsed["effective_locator"],
    )


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
                role=str(element.get("role") or ""),
                role_source=str(element.get("role_source") or ""),
                name=str(element.get("name") or ""),
                text=element.get("text"),
                action_type=str(element.get("action_type") or ""),
                primary_selector=element.get("primary_selector") if isinstance(element.get("primary_selector"), dict) else None,
                fallback_selector=element.get("fallback_selector") if isinstance(element.get("fallback_selector"), dict) else None,
                visible=bool(element.get("visible", True)),
                dialog_id=element.get("dialog_id") if isinstance(element.get("dialog_id"), str) else None,
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
        dialogs=[
            DialogInfo(
                id=str(d.get("id") or f"dialog-{idx}"),
                title=str(d.get("title") or ""),
                role=str(d.get("role") or ""),
            )
            for idx, d in enumerate(result.get("dialogs", []), start=1)
            if isinstance(d, dict)
        ],
        active_dialog_id=result.get("active_dialog_id") if isinstance(result.get("active_dialog_id"), str) else None,
    )
