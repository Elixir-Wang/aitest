"""
页面信息提取工具。
"""

from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from app.agents.page_exploration.tools.runtime_context import snapshot_with_runtime_context


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
        - elements: List of element info (ref, role, name, text, visible)
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
        #     {"ref": "e15", "role": "button", "name": "Create Agent", "visible": true}
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
            "ref": elem.ref,
            "role": elem.role,
            "name": elem.name,
            "text": elem.text,
            "visible": elem.visible,
        }
        for elem in result.elements
    ]
    accessibility_tree = [node.model_dump() for node in result.accessibility_tree]
    visible_text_blocks = result.visible_text_blocks
    if keywords:
        elements = _focus_elements(elements, keywords)
        accessibility_tree = _focus_accessibility_tree(accessibility_tree, keywords)
        visible_text_blocks = _focus_visible_text_blocks(visible_text_blocks, keywords)
    return {
        "url": result.url,
        "title": result.title,
        "page_text_summary": result.page_text_summary,
        "elements": elements,
        "accessibility_tree": accessibility_tree,
        "visible_text_blocks": visible_text_blocks,
        "error": result.error,
    }


def _matches_keywords(text: Optional[str], keywords: List[str]) -> bool:
    value = str(text or "").lower()
    return any(keyword.lower() in value for keyword in keywords)


def _focus_elements(elements: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    if not keywords:
        return elements
    matched = []
    for element in elements:
        if _matches_keywords(element.get("name"), keywords) or _matches_keywords(element.get("text"), keywords):
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
]
