"""
页面导航和交互工具

包含：
- playwright_navigate_tool: 导航到URL
- playwright_click_tool: 点击元素
- playwright_fill_tool: 填充表单
"""

from typing import Optional
from langchain_core.tools import tool

from app.agents.page_exploration.playwright.cli_wrapper import PlaywrightCLI
from app.agents.page_exploration.tools.runtime_context import (
    click_with_runtime_context,
    fill_with_runtime_context,
    navigate_with_runtime_context,
)


@tool
def playwright_navigate_tool(url: str, session_id: Optional[str] = None) -> dict:
    """
    Navigate to a URL in the browser.

    Use this tool to:
    - Visit a new page
    - Follow a link without clicking (direct navigation)
    - Start exploration from a specific URL

    Args:
        url: The URL to navigate to
        session_id: Optional session ID to maintain browser state

    Returns:
        A dictionary containing:
        - url: The URL that was navigated to
        - success: True if navigation succeeded, False otherwise
        - error: Error message if navigation failed

    Example:
        result = playwright_navigate_tool(url="https://app.example.com/agents")
        # Returns: {"url": "https://...", "success": true, "error": null}
    """
    result = navigate_with_runtime_context(url)
    if result is None:
        cli = PlaywrightCLI(session_id=session_id)
        result = cli.navigate(url)

    return {
        "url": result.url,
        "success": result.success,
        "error": result.error,
    }


@tool
def playwright_click_tool(locator: str, session_id: Optional[str] = None) -> dict:
    """
    Click an element on the current page.

    Use this tool to:
    - Click buttons, links, or other interactive elements
    - Trigger navigation or UI changes
    - Interact with the page

    IMPORTANT: Use the ref returned by the latest playwright_snap_tool result.
    - Good: button-create-agent
    - Good: e15
    - Bad: getByRole('button', { name: 'Create Agent' })

    Args:
        locator: Element ref from the latest snapshot result
        session_id: Optional session ID to maintain browser state

    Returns:
        A dictionary containing:
        - success: True if click succeeded, False otherwise
        - error: Error message if click failed

    Example:
        result = playwright_click_tool(locator="getByRole('button', { name: 'Create' })")
        # Returns: {"success": true, "error": null}
    """
    result = click_with_runtime_context(locator)
    if result is None:
        cli = PlaywrightCLI(session_id=session_id)
        result = cli.click(locator)

    return {
        "success": result.success,
        "error": result.error,
    }


@tool
def playwright_fill_tool(
    locator: str, value: str, session_id: Optional[str] = None
) -> dict:
    """
    Fill an input element with text.

    Use this tool to:
    - Enter text into input fields, textareas, or editable elements
    - Fill form fields during exploration

    IMPORTANT: Use the ref returned by the latest playwright_snap_tool result.
    - Good: textbox-email
    - Good: e20
    - Bad: getByLabel('Email')

    Args:
        locator: Element ref from the latest snapshot result
        value: Text to fill into the element
        session_id: Optional session ID to maintain browser state

    Returns:
        A dictionary containing:
        - success: True if fill succeeded, False otherwise
        - error: Error message if fill failed

    Example:
        result = playwright_fill_tool(
            locator="getByLabel('Search')",
            value="test query"
        )
        # Returns: {"success": true, "error": null}
    """
    result = fill_with_runtime_context(locator, value)
    if result is None:
        cli = PlaywrightCLI(session_id=session_id)
        result = cli.fill(locator, value)

    return {
        "success": result.success,
        "error": result.error,
    }


__all__ = [
    "playwright_navigate_tool",
    "playwright_click_tool",
    "playwright_fill_tool",
]
