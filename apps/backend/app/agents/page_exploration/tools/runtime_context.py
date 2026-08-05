"""Runtime browser context for page exploration tools."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Iterator, Any, Mapping
from urllib.parse import urlparse

from app.agents.page_exploration.playwright.schemas import (
    AccessibilityNodeInfo,
    ActionFailure,
    ClickResult,
    ElementInfo,
    FillResult,
    NavigateResult,
    SnapshotResult,
)
from app.services.page_exploration.browser_session import BrowserSessionError, PlaywrightBrowserSession
from app.agents.page_exploration.utils.element_key import build_element_key
from app.agents.page_exploration.utils.page_id import make_page_id


_browser_session: ContextVar[PlaywrightBrowserSession | None] = ContextVar(
    "page_exploration_browser_session",
    default=None,
)
_state_tracker: ContextVar[dict[str, Any] | None] = ContextVar("page_exploration_state_tracker", default=None)
_exploration_runtime: ContextVar["ExplorationRuntime | None"] = ContextVar(
    "page_exploration_runtime",
    default=None,
)


class PageExplorationRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExplorationRuntime:
    project_id: str
    run_id: str
    storage_root: Path


@contextmanager
def exploration_runtime_context(
    *,
    project_id: str,
    run_id: str,
    storage_root: Path | str,
) -> Iterator[None]:
    runtime = ExplorationRuntime(
        project_id=str(project_id),
        run_id=str(run_id),
        storage_root=Path(storage_root).resolve(),
    )
    token = _exploration_runtime.set(runtime)
    try:
        yield
    finally:
        _exploration_runtime.reset(token)


def require_exploration_runtime() -> ExplorationRuntime:
    runtime = _exploration_runtime.get()
    if runtime is None:
        raise PageExplorationRuntimeError("Page exploration runtime is not bound.")
    return runtime


ACTION_VERIFICATION_HINT = (
    "动作已执行，但这不代表当前 todo 的业务完成判据已满足。"
    "请调用 playwright_snap_tool 验证 URL、Toast、弹窗、字段值或状态文本变化后，"
    "再决定是否标记子步骤 completed。"
)


def _locator_risk(locator: str, failure: ActionFailure | None = None) -> str:
    """Return a compact risk flag for locators that need stricter post-action checks."""
    lowered = locator.lower()
    if failure is not None and failure.recovered:
        return "ambiguous_or_recovered_locator"
    if "nth-of-type" in lowered or "nth-child" in lowered:
        return "structural_css_locator"
    if "page.locator(" in locator and not any(token in lowered for token in ("data-testid", "[role=", "#")):
        return "low_confidence_css_locator"
    return ""


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
        state_token = _state_tracker.set({"stack": [], "last_action": None})
        try:
            yield
        finally:
            _state_tracker.reset(state_token)
            _browser_session.reset(token)
            session.close()


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
    每个候选含 ancestor_chain 让 LLM 判断哪个在弹窗里。
    """
    if error_type != "locator_not_unique":
        return raw_summary
    # raw 通常包含 "Locator matched N elements: ..." 形式
    if not raw_summary.rstrip().endswith("。"):
        raw_summary = raw_summary.rstrip() + "。"
    return (
        f"{raw_summary} "
        "再次调用 playwright_snap_tool 查响应里 match_groups 字段，"
        "找到 (name, role) 对应组的 candidates 列表（每项含 ancestor_chain 与 primary_selector_code），"
        "按 ancestor_chain 中的结构信息（popover / dialog / main 等）选用 filter({ hasText }) 或父级容器链式定位。"
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
            "before_url": str(action.get("before_url") or ""),
            "after_url": str(action.get("after_url") or ""),
            "url_changed": bool(action.get("url_changed", False)),
        }
        if failure_raw:
            parsed["failure"] = failure
        return parsed

    return {
        "success": False,
        "failure": failure,
        "effective_locator": action.get("effective_locator") or raw_expr,
    }


def click_with_runtime_context(element_id: str) -> ClickResult | None:
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
    element_key = _current_element_key(element_id)
    element_context = _current_element_context(element_id)
    try:
        result = session.click(element_id)
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
            effective_locator=element_id,
            next_step_hint="动作失败。请先 snap 观察当前页面状态，再更换定位器或处理遮挡/歧义。",
        )

    parsed = _parse_action_result(
        result,
        raw_expr=element_id,
        default_error=f"Element is not executable in the current observation: {element_id}",
    )
    if parsed["success"]:
        tracker = _state_tracker.get()
        if tracker is not None:
            tracker["last_action"] = {"action": "click", "element_id": element_id}
        return ClickResult(
            success=True,
            failure=parsed.get("failure"),
            effective_locator=parsed["effective_locator"],
            verification_required=True,
            next_step_hint=ACTION_VERIFICATION_HINT,
            risk=_locator_risk(parsed["effective_locator"], parsed.get("failure")),
            element_key=element_key,
            before_url=parsed["before_url"],
            after_url=parsed["after_url"],
            url_changed=parsed["url_changed"],
            source_region_type=str(element_context.get("region_type") or "content"),
            navigation_group=str(element_context.get("navigation_group") or ""),
        )

    failure: ActionFailure = parsed["failure"]
    return ClickResult(
        success=False,
        # 给 LLM 看的"一句话错误"，优先级：summary > raw
        error=failure.summary or failure.raw,
        failure=failure,
        effective_locator=parsed["effective_locator"],
        verification_required=False,
        next_step_hint="动作失败。不要重复尝试同一 locator；请 snap 后结合 failure.error_type 和 match_groups 重新定位。",
        risk=_locator_risk(parsed["effective_locator"], failure),
        element_key=element_key,
    )


def fill_with_runtime_context(element_id: str, value: str) -> FillResult | None:
    """Fill via the long-lived browser session. 只接受可复用 Playwright Locator 字符串。

    失败结构化透传，语义与 click_with_runtime_context 一致。
    """
    session = _browser_session.get()
    if session is None:
        raise BrowserSessionError("Page exploration browser session is not bound.")
    element_key = _current_element_key(element_id)
    try:
        result = session.fill(element_id, value)
    except BrowserSessionError as exc:
        return FillResult(
            success=False,
            error=str(exc),
            failure=ActionFailure(
                error_type="action_failed",
                summary="浏览器会话协议错误。",
                raw=str(exc),
            ),
            effective_locator=element_id,
            next_step_hint="填充失败。请先 snap 观察当前页面状态，再更换定位器或处理遮挡/歧义。",
        )

    parsed = _parse_action_result(
        result,
        raw_expr=element_id,
        default_error=f"Element is not executable in the current observation: {element_id}",
    )
    if parsed["success"]:
        return FillResult(
            success=True,
            failure=parsed.get("failure"),
            effective_locator=parsed["effective_locator"],
            verification_required=True,
            next_step_hint=ACTION_VERIFICATION_HINT,
            risk=_locator_risk(parsed["effective_locator"], parsed.get("failure")),
            element_key=element_key,
        )

    failure: ActionFailure = parsed["failure"]
    return FillResult(
        success=False,
        error=failure.summary or failure.raw,
        failure=failure,
        effective_locator=parsed["effective_locator"],
        verification_required=False,
        next_step_hint="填充失败。不要重复尝试同一 locator；请 snap 后结合 failure.error_type 和 match_groups 重新定位。",
        risk=_locator_risk(parsed["effective_locator"], failure),
        element_key=element_key,
    )


def _current_element_key(element_id: str) -> str:
    tracker = _state_tracker.get()
    if tracker is None or not tracker.get("stack"):
        return ""
    state = tracker["stack"][-1]
    return str(state.get("element_keys", {}).get(element_id) or "")


def _current_element_context(element_id: str) -> dict[str, str]:
    tracker = _state_tracker.get()
    if tracker is None or not tracker.get("stack"):
        return {}
    state = tracker["stack"][-1]
    contexts = (
        state.get("element_contexts")
        if isinstance(state.get("element_contexts"), dict)
        else {}
    )
    context = contexts.get(element_id)
    return context if isinstance(context, dict) else {}


def _element_region(element: Mapping[str, Any]) -> dict[str, str]:
    ancestor_chain = element.get("ancestor_chain") if isinstance(element.get("ancestor_chain"), list) else []
    ancestor_roles = {
        str(item.get("role") or "").strip().lower()
        for item in ancestor_chain
        if isinstance(item, Mapping)
    }
    selector_parts = [str(element.get("action_locator") or "")]
    for field in ("primary_selector", "fallback_selector"):
        selector = element.get(field)
        if isinstance(selector, Mapping):
            selector_parts.append(str(selector.get("code") or selector.get("css") or ""))
    selector_text = " ".join(selector_parts).lower()
    is_navigation = bool(ancestor_roles & {"navigation", "complementary", "menu"}) or any(
        marker in selector_text for marker in ("aside", "<nav", "[role=\"navigation\"]", "[role='navigation']")
    )
    if is_navigation:
        return {"region_type": "navigation", "navigation_group": "primary-navigation"}
    return {"region_type": "content", "navigation_group": ""}


def press_with_runtime_context(locator: str = "", key: str = "") -> dict:
    """Reject keyboard actions because exploration must produce reusable element identity."""
    return {
        "success": False,
        "error": "探索阶段禁止使用键盘命令。",
        "failure": {
            "error_type": "keyboard_action_forbidden",
            "summary": "Tab、Enter、Escape 等键盘命令无法生成稳定元素定位，禁止用于探索恢复或推进流程。",
            "raw": f"key={key}, locator={locator}",
            "recovered": False,
            "recovery_warning": "",
        },
        "effective_locator": locator,
        "verification_required": False,
        "next_step_hint": "重新观察并选择唯一元素；无法定位时保存截图并标记 blocked。",
        "risk": "forbidden_keyboard_action",
    }


def scoped_query_with_runtime_context(
    *,
    scope: str = "",
    text: str = "",
    role: str = "",
    limit: int = 30,
) -> dict:
    session = _browser_session.get()
    if session is None:
        raise BrowserSessionError("Page exploration browser session is not bound.")
    return session.scoped_query(scope=scope, text=text, role=role, limit=limit)


def observe_overlays_with_runtime_context() -> dict:
    session = _browser_session.get()
    if session is None:
        raise BrowserSessionError("Page exploration browser session is not bound.")
    return session.observe_overlays()


def screenshot_with_runtime_context(path: str, *, full_page: bool = True) -> dict:
    session = _browser_session.get()
    if session is None:
        raise BrowserSessionError("Page exploration browser session is not bound.")
    return session.screenshot(path, full_page=full_page)


def snapshot_with_runtime_context(url: str | None = None) -> SnapshotResult | None:
    session = _browser_session.get()
    if session is None:
        raise BrowserSessionError("Page exploration browser session is not bound.")
    if url:
        session.navigate(url)
    result = session.observe()
    state_context = _update_state_tracker(result)
    return SnapshotResult(
        observation_id=str(result.get("observation_id") or ""),
        url=str(result.get("url") or url or ""),
        title=str(result.get("title") or ""),
        interaction_scope=str(result.get("interaction_scope") or "page"),
        overlay=result.get("overlay") if isinstance(result.get("overlay"), dict) else None,
        overlay_registry=result.get("overlay_registry") if isinstance(result.get("overlay_registry"), dict) else {},
        state_context=state_context,
        page_text_summary=str(result.get("page_text_summary") or ""),
        elements=[
            ElementInfo(
                element_id=str(element.get("element_id") or element.get("id") or ""),
                action_locator=str(element.get("action_locator") or ""),
                role=str(element.get("role") or ""),
                role_source=str(element.get("role_source") or ""),
                name=str(element.get("name") or ""),
                text=element.get("text"),
                value=str(element.get("value") or ""),
                context=element.get("context") if isinstance(element.get("context"), dict) else {},
                action_type=str(element.get("action_type") or ""),
                primary_selector=element.get("primary_selector") if isinstance(element.get("primary_selector"), dict) else None,
                fallback_selector=element.get("fallback_selector") if isinstance(element.get("fallback_selector"), dict) else None,
                visible=bool(element.get("visible", True)),
                ancestor_chain=element.get("ancestor_chain") if isinstance(element.get("ancestor_chain"), list) else [],
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
        collections=[
            item for item in result.get("collections", []) if isinstance(item, dict)
        ],
        state_signature=str(result.get("state_signature") or ""),
    )


def _update_state_tracker(result: Mapping[str, Any]) -> dict[str, Any]:
    tracker = _state_tracker.get()
    if tracker is None:
        return {}
    url = str(result.get("url") or "")
    page_id = make_page_id(urlparse(url).path or "/")
    scope = str(result.get("interaction_scope") or "page")
    overlay = result.get("overlay") if isinstance(result.get("overlay"), Mapping) else {}
    identity = "|".join(str(overlay.get(key) or "") for key in ("type", "role", "name"))
    stack = tracker["stack"]

    if scope == "page":
        state = {"state_id": f"{page_id}__root__001", "state_type": "root", "parent_state_id": None, "triggered_by": None}
        stack[:] = [state]
    elif stack and any(item.get("overlay_identity") == identity for item in stack):
        index = max(i for i, item in enumerate(stack) if item.get("overlay_identity") == identity)
        del stack[index + 1:]
        state = stack[index]
    else:
        parent = stack[-1] if stack else {"state_id": f"{page_id}__root__001", "element_keys": {}}
        action = tracker.get("last_action") or {}
        element_key = parent.get("element_keys", {}).get(str(action.get("element_id") or ""), "")
        digest = sha1(f"{parent['state_id']}|{identity}|{element_key}".encode()).hexdigest()[:8]
        state_type = str(overlay.get("type") or "dialog")
        state = {
            "state_id": f"{page_id}__{state_type}__{digest}",
            "state_type": state_type,
            "parent_state_id": parent["state_id"],
            "triggered_by": ({
                "from_state": parent["state_id"],
                "element_key": element_key,
                "action": str(action.get("action") or "click"),
                "url_changed": False,
                "observed_url": url,
            } if element_key else None),
            "overlay_identity": identity,
        }
        stack.append(state)

    element_keys: dict[str, str] = {}
    element_contexts: dict[str, dict[str, str]] = {}
    for element in result.get("elements", []):
        if not isinstance(element, Mapping):
            continue
        key = build_element_key({"role": element.get("role"), "name": element.get("name")})
        element_id = str(element.get("element_id") or element.get("id") or "")
        if element_id:
            element_keys[element_id] = key
            element_contexts[element_id] = _element_region(element)
    state["element_keys"] = element_keys
    state["element_contexts"] = element_contexts
    tracker["last_action"] = None
    return {
        key: value
        for key, value in state.items()
        if key not in {"element_contexts", "element_keys", "overlay_identity"}
    }
