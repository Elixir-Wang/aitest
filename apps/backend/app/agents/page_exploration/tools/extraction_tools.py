"""
页面信息提取工具

包含：
- playwright_snap_tool: 捕获页面快照和元素信息
- playwright_extract_elements_tool: 提取特定类型的元素（待实现）
"""

from typing import Optional
from langchain_core.tools import tool

from app.agents.page_exploration.playwright.cli_wrapper import PlaywrightCLI
from app.agents.page_exploration.tools.runtime_context import snapshot_with_runtime_context


@tool
def playwright_snap_tool(url: Optional[str] = None, session_id: Optional[str] = None) -> dict:
    """
    Capture a snapshot of a web page with element information.

    Use this tool to:
    - Get the current page structure
    - Extract all interactive elements (buttons, links, inputs, etc.)
    - Get element roles, names, and visibility

    Args:
        url: Optional URL to navigate before capture. Omit it to snapshot the current page.
        session_id: Optional session ID to maintain browser state across calls

    Returns:
        A dictionary containing:
        - url: The actual URL of the page
        - title: Page title
        - elements: List of element info (ref, role, name, text, visible)
        - raw_output: Raw YAML output from playwright-cli
        - error: Error message if snapshot failed

    Example:
        result = playwright_snap_tool(url="https://app.example.com/workspace")
        # Returns elements like:
        # {
        #   "url": "https://app.example.com/workspace",
        #   "title": "Workspace",
        #   "elements": [
        #     {"ref": "e15", "role": "button", "name": "Create Agent", "visible": true},
        #     {"ref": "e20", "role": "textbox", "name": "Search", "text": "", "visible": true}
        #   ]
        # }
    """
    result = snapshot_with_runtime_context(url)
    if result is None:
        cli = PlaywrightCLI(session_id=session_id)
        result = cli.snap(url) if url else cli.snap_current()

    return {
        "url": result.url,
        "title": result.title,
        "elements": [
            {
                "ref": elem.ref,
                "role": elem.role,
                "name": elem.name,
                "text": elem.text,
                "visible": elem.visible,
            }
            for elem in result.elements
        ],
        "raw_output": result.raw_output,
        "error": result.error,
    }


@tool
def playwright_extract_elements_tool(
    element_types: list[str], session_id: Optional[str] = None
) -> dict:
    """
    Extract specific types of elements from the current page.

    Use this tool to:
    - Filter elements by type (button, link, input, etc.)
    - Get a focused view of specific element types
    - Reduce noise when looking for specific elements

    Args:
        element_types: List of element types to extract (e.g., ["button", "link"])
        session_id: Optional session ID to maintain browser state

    Returns:
        A dictionary containing:
        - elements: Filtered list of elements
        - count: Number of elements found

    Example:
        result = playwright_extract_elements_tool(element_types=["button", "link"])
        # Returns: {"elements": [...], "count": 15}
    """
    # TODO: 实现真实的提取逻辑
    # 当前先返回占位符
    return {
        "elements": [],
        "count": 0,
        "error": "Not yet implemented - use playwright_snap_tool instead",
    }


__all__ = [
    "playwright_snap_tool",
    "playwright_extract_elements_tool",
]
