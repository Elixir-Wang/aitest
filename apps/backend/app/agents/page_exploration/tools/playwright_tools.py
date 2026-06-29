"""LangChain tools for Playwright CLI operations"""

from typing import Optional
from langchain_core.tools import tool

from app.agents.page_exploration.playwright.cli_wrapper import PlaywrightCLI
from app.agents.page_exploration.playwright.schemas import (
    SnapshotResult,
    NavigateResult,
    ClickResult,
    FillResult,
)


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

    IMPORTANT: Use semantic locators, NOT ref!
    - ✅ Good: getByRole('button', { name: 'Create Agent' })
    - ✅ Good: getByLabel('Search')
    - ❌ Bad: e15 (ref is temporary and changes every snapshot)

    Args:
        locator: Playwright locator string (use semantic locators)
        session_id: Optional session ID to maintain browser state

    Returns:
        A dictionary containing:
        - success: True if click succeeded, False otherwise
        - error: Error message if click failed

    Example:
        result = playwright_click_tool(locator="getByRole('button', { name: 'Create' })")
        # Returns: {"success": true, "error": null}
    """
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

    IMPORTANT: Use semantic locators, NOT ref!
    - ✅ Good: getByLabel('Email')
    - ✅ Good: getByRole('textbox', { name: 'Username' })
    - ✅ Good: getByPlaceholder('Enter your name')
    - ❌ Bad: e20 (ref is temporary)

    Args:
        locator: Playwright locator string (use semantic locators)
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
    cli = PlaywrightCLI(session_id=session_id)
    result = cli.fill(locator, value)

    return {
        "success": result.success,
        "error": result.error,
    }
