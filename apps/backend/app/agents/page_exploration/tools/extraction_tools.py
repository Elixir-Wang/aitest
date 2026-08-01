"""
页面信息提取工具。
"""
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from app.agents.page_exploration.tools.runtime_context import (
    observe_overlays_with_runtime_context,
    scoped_query_with_runtime_context,
    screenshot_with_runtime_context,
    snapshot_with_runtime_context,
)

@tool
def playwright_snap_tool(
    url: Optional[str] = None,
    focus_keywords: Optional[List[str]] = None,
) -> dict:
    """
    Capture a semantic snapshot of the current page.

    Use this tool to:
    - Get compact accessibility-tree page state for model reasoning
    - Extract verified executable elements for browser actions
    - Get visible text blocks as a fallback for popovers and custom UI
    - Focus on goal-relevant areas to reduce token usage

    Args:
        url: Optional URL to navigate before capture. Omit it to snapshot the current page.
        focus_keywords: Optional keywords to focus the snapshot on. When provided,
            the snapshot will prioritize elements and accessibility nodes whose
            name or text contains any of these keywords. This is useful for
            goal-oriented exploration to reduce token usage while keeping
            relevant page context.

    Returns:
        A dictionary containing:
        - url: The actual URL of the page
        - title: Page title
        - page_text_summary: One-line summary of the page
        - elements: List of element info with verified reusable selectors
        - accessibility_tree: Compact accessibility nodes (id, role, name, state)
        - visible_text_blocks: Compact visible text blocks from the page
            Only included when focus_keywords is provided.
        - error: Error message if snapshot failed

    Example:
        result = playwright_snap_tool(url="https://app.example.com/workspace")
        # Returns elements like:
        # {
        #   "url": "https://...",
        #   "title": "Workspace",
        #   "page_text_summary": "标题：Workspace。可交互元素：12...",
        #   "elements": [
        #     {
        #       "role": "button",
        #       "name": "Create Agent",
        #       "primary_selector": {"kind": "role", "code": "page.getByRole('button', { name: 'Create Agent' })"}
        #     }
        #   ],
        #   "accessibility_tree": [
        #     {"id": "ax-1", "role": "button", "name": "Create Agent"}
        #   ]
        # }

        focused = playwright_snap_tool(
            url="https://app.example.com/workspace",
            focus_keywords=["agent", "create"]
        )
        # Returns a smaller snapshot focused on agent-related elements.
    """
    result = snapshot_with_runtime_context(url)
    keywords = [kw.strip() for kw in (focus_keywords or []) if str(kw).strip()]
    elements = [
        {
            "element_id": elem.element_id,
            "role": elem.role,
            "role_source": elem.role_source,
            "name": elem.name,
            "text": elem.text,
            "value": elem.value,
            "overlay_id": elem.overlay_id,
            "primary_selector": getattr(elem, "primary_selector", None),
            "fallback_selector": getattr(elem, "fallback_selector", None),
            "context": elem.context,
            "action_type": elem.action_type,
            "visible": elem.visible,
            "ancestor_chain": elem.ancestor_chain,
        }
        for elem in result.elements
    ]
    # 给每个 element 标 sibling_count（页面级，同 name+role 全页面出现次数），
    # 让 LLM 看到 ambiguous 元素，避免写 getByRole 触发严格模式多匹配。
    _annotate_ambiguity(elements)
    accessibility_tree = [node.model_dump() for node in result.accessibility_tree]
    visible_text_blocks = result.visible_text_blocks
    if keywords:
        elements = _focus_elements(elements, keywords)
        accessibility_tree = _focus_accessibility_tree(accessibility_tree, keywords)
        visible_text_blocks = _focus_visible_text_blocks(visible_text_blocks, keywords)

    return {
        "observation_id": result.observation_id,
        "url": result.url,
        "title": result.title,
        "interaction_scope": result.interaction_scope,
        "overlay": result.overlay,
        "overlay_registry": result.overlay_registry,
        "state_context": result.state_context,
        "page_text_summary": result.page_text_summary,
        "state_signature": result.state_signature,
        "elements": elements,
        "accessibility_tree": accessibility_tree,
        "visible_text_blocks": visible_text_blocks,
        "error": result.error,
    }


@tool
def playwright_scoped_query_tool(
    scope: str = "",
    text: str = "",
    role: str = "",
    limit: int = 30,
) -> dict:
    """
    Query visible elements inside a smaller DOM scope without changing page state.

    Use this after a full snap when the next target is inside a dialog/popover/menu
    or when the full page snapshot is too broad. Prefer this over repeated full
    page snaps while stuck on the same URL/state.

    Args:
        scope: Optional Playwright selector or supported Locator expression, e.g.
            "[role='popover']", "section:has-text('Prompt')", or
            "page.getByRole('dialog')". If omitted, the runner chooses the first
            visible overlay, then main/body.
        text: Optional text filter.
        role: Optional role filter, e.g. "button", "textbox".
        limit: Maximum matches to return.

    Returns:
        {url, title, scope_used, match_count, matches, error_type, error_summary}
    """
    return scoped_query_with_runtime_context(scope=scope, text=text, role=role, limit=limit)


@tool
def playwright_observe_overlays_tool() -> dict:
    """
    Observe visible dialogs, popovers, menus, and drawers.

    Use this when a click opens a floating layer, when a locator inside a popover
    fails as not_visible, or before deciding whether to close/reopen an overlay.

    Returns:
        {url, title, overlay_count, overlays}, where each overlay includes visible
        text, bounds, and compact controls.
    """
    return observe_overlays_with_runtime_context()


@tool
def playwright_screenshot_tool(path: str, full_page: bool = True) -> dict:
    """
    Capture a screenshot as evidence for a blocked or ambiguous exploration state.

    Args:
        path: Absolute filesystem path for the PNG.
        full_page: Whether to capture the full page.

    Returns:
        {path, url, title, full_page}
    """
    return screenshot_with_runtime_context(path, full_page=full_page)


def _annotate_ambiguity(elements: list) -> None:
    """给每个 element 加 sibling_count（同 name+role 全页面出现次数）+ is_ambiguous 布尔。

    why: verification.unique 只验证"这个 element 的 selector 在 DOM 中唯一指向它"，
    但严格模式下 getByRole 跨整个 DOM 匹配——同 name+role 有多元素时还是多匹配。
    LLM 看到 sibling_count > 1 就该用 chain 容器而不是裸 getByRole。
    """
    counts: dict[tuple[str, str], int] = {}
    for el in elements:
        if not isinstance(el, dict):
            continue
        key = (str(el.get("name") or ""), str(el.get("role") or ""))
        counts[key] = counts.get(key, 0) + 1

    for el in elements:
        if not isinstance(el, dict):
            continue
        key = (str(el.get("name") or ""), str(el.get("role") or ""))
        sibling_count = counts.get(key, 1)
        el["sibling_count"] = sibling_count
        el["is_ambiguous"] = sibling_count > 1


def _build_scope_hint(*, role: str, name: str, context_hint: str, ancestor_text: str) -> str:
    """Give the LLM a concrete disambiguation pattern without choosing for it."""
    escaped_name = name.replace("'", "\\'")
    if context_hint in {"dialog", "alertdialog"}:
        return (
            f"优先用弹窗容器限定：page.getByRole('{context_hint}')."
            f"filter({{ hasText: '关键表单字段或标题' }}).getByRole('{role}', {{ name: '{escaped_name}' }})"
        )
    if context_hint in {"popover", "menu"}:
        return (
            f"优先用浮层容器限定：page.locator('[role=\"{context_hint}\"]')."
            f"filter({{ hasText: '关键选项文本' }}).getByText('{escaped_name}', {{ exact: true }})"
        )
    if ancestor_text:
        short_text = ancestor_text[:80].replace("'", "\\'")
        return (
            "当前候选的祖先文本可作上下文锚点；优先选择包含目标业务字段/卡片名的容器，"
            f"例如 filter({{ hasText: '{short_text}' }}) 后再定位 '{escaped_name}'。"
        )
    return "该同名元素缺少明显容器上下文；请先 snap 聚焦相关关键词，再用字段/卡片/弹窗文本限定范围。"


def _matches_keywords(text: Optional[str], keywords: List[str]) -> bool:
    value = str(text or "").lower()
    return any(keyword.lower() in value for keyword in keywords)


def _focus_elements(elements: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    if not keywords:
        return elements
    matched = []
    for element in elements:
        unnamed_fill_target = element.get("action_type") == "fill" and not str(element.get("name") or "").strip()
        if (
            unnamed_fill_target
            or _matches_keywords(element.get("name"), keywords)
            or _matches_keywords(element.get("text"), keywords)
        ):
            matched.append(element)
    return matched or elements


def _focus_accessibility_tree(
    tree: List[Dict[str, Any]],
    keywords: List[str],
) -> List[Dict[str, Any]]:
    if not tree or not keywords:
        return tree

    matched_ids = set()
    for node in tree:
        if _matches_keywords(node.get("name"), keywords):
            matched_ids.add(node.get("id"))

    if not matched_ids:
        return tree

    keep = set()
    for node in tree:
        node_id = node.get("id")
        if node_id in matched_ids:
            keep.add(node_id)
            _add_ancestors(tree, node_id, keep)

    return [node for node in tree if node.get("id") in keep]


def _add_ancestors(tree: List[Dict[str, Any]], target_id: str, keep: set) -> None:
    for node in tree:
        children = node.get("children") or []
        if any(child.get("id") == target_id for child in children):
            keep.add(node.get("id"))
            _add_ancestors(tree, node.get("id"), keep)
            return


def _focus_visible_text_blocks(blocks: List[str], keywords: List[str], max_blocks: int = 60) -> List[str]:
    if not blocks or not keywords:
        return []
    matched = [block for block in blocks if _matches_keywords(block, keywords)]
    return matched[:max_blocks]


__all__ = [
    "playwright_snap_tool",
    "playwright_scoped_query_tool",
    "playwright_observe_overlays_tool",
    "playwright_screenshot_tool",
]
