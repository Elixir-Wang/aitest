"""
页面导航和交互工具。
"""

from langchain_core.tools import tool

from app.agents.page_exploration.tools.runtime_context import (
    click_with_runtime_context,
    fill_with_runtime_context,
    navigate_with_runtime_context,
)


@tool
def playwright_navigate_tool(url: str) -> dict:
    """
    Navigate to a URL in the browser.

    Use this tool to:
    - Visit a new page
    - Follow a link without clicking (direct navigation)
    - Start exploration from a specific URL

    Args:
        url: The URL to navigate to

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

    return {
        "url": result.url,
        "success": result.success,
        "error": result.error,
    }


@tool
def playwright_click_tool(locator: str) -> dict:
    """
    Click an element on the current page.

    locator 支持两种形式（按推荐顺序）：

    1) Playwright Locator 字符串（推荐，跨调用稳定）：

       getByRole('button', { name: '创建智能体' })
       getByRole('treeitem', { name: '自主规划 Agent' })
       getByLabel('用户名')
       getByTestId('user-avatar')
       getByText('提交订单', { exact: true })
       getByPlaceholder('请输入手机号')

       优点：每次执行实时查找，DOM 抖动不会失效；定位串可直接复用到
             后续自动化测试代码（Playwright / pytest-playwright 原生支持）。

    2) 上一次 snap 返回的 element.id（如 "button-create-agent-001"）：

       优点：snap 已验证 unique + visible，确定性高。
       缺点：页面变化后 id 失效，需要重新 snap。

    不支持：临时 ref（"e15" / "e20"），CSS / XPath 字符串。

    失败处理：失败时不要再次尝试同一 locator。改用 snap 拿新 ref，或
    直接用 Playwright Locator 字符串重试。

    Args:
        locator: Playwright Locator 字符串 或 snap 返回的 element.id

    Returns:
        A dictionary containing:
        - success: True if click succeeded, False otherwise
        - error: Error message if click failed
    """
    result = click_with_runtime_context(locator)

    return {
        "success": result.success,
        "error": result.error,
    }


@tool
def playwright_fill_tool(locator: str, value: str) -> dict:
    """
    Fill an input element with text.

    locator 支持 Playwright Locator 字符串（推荐）和 snap 返回的 element.id。
    常用形式：

    - getByLabel('用户名')
    - getByPlaceholder('请输入手机号')
    - getByRole('textbox', { name: 'Email' })
    - getByTestId('search-input')

    Args:
        locator: Playwright Locator 字符串 或 snap 返回的 element.id
        value: Text to fill into the element

    Returns:
        A dictionary containing:
        - success: True if fill succeeded, False otherwise
        - error: Error message if fill failed
    """
    result = fill_with_runtime_context(locator, value)

    return {
        "success": result.success,
        "error": result.error,
    }


__all__ = [
    "playwright_navigate_tool",
    "playwright_click_tool",
    "playwright_fill_tool",
]
