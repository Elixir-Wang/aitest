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

    locator 优先使用可复用的 Playwright Locator 字符串：

       getByRole('button', { name: '创建智能体' })
       getByRole('treeitem', { name: '自主规划 Agent' })
       getByLabel('用户名')
       getByText('提交订单', { exact: true })
       getByPlaceholder('请输入手机号')
       getByTestId('user-avatar')
       page.locator('[data-testid="workspace-nav"]')  # 仅在以上定位器都不可用时兜底

    不支持：observe element.id、临时 ref（"e15" / "e20"）和 XPath 字符串。
    不要因为元素可点击就猜测为 button；只有真实原生/显式无障碍 role 才用 getByRole。

    失败处理：失败时不要再次尝试同一 locator。应重新 observe，选择
    verified 的 Playwright Locator 字符串后重试。

    Args:
        locator: Playwright Locator 字符串

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

    locator 只支持可复用 Playwright Locator 字符串。
    常用形式：

    - getByLabel('用户名')
    - getByPlaceholder('请输入手机号')
    - getByRole('textbox', { name: 'Email' })
    - getByTestId('search-input')

    Args:
        locator: Playwright Locator 字符串
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
