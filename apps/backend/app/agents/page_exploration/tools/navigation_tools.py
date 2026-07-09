"""
页面导航和交互工具。
"""
from langchain_core.tools import tool

from app.agents.page_exploration.tools.runtime_context import (
    click_with_runtime_context,
    fill_with_runtime_context,
    navigate_with_runtime_context,
    press_with_runtime_context,
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
       getByRole('listitem').filter({ hasText: '自主规划' })
           .getByRole('button', { name: '编辑' })  # 链式 filter
       page.locator('[role="popover"]').filter({ hasText: '自主规划 Agent' })
           .getByText('能够自主规划任务')  # 浮层/卡片容器内定位
       page.locator('[data-testid="workspace-nav"]')  # 仅在以上定位器都不可用时兜底

    失败处理（必读）：
    - 工具返回 success=false 时，error_type 取值固定为以下之一：
      · pointer_intercepted：目标被浮层/遮挡；re-wait + close popover 后重试
      · locator_not_unique：严格模式违规，命中多个元素；改用 filter 链式限定范围
      · locator_timeout：超时；snap 后用更稳的定位器
      · not_visible：被覆盖/折叠/隐藏；snap 重新观察
      · action_failed：其它执行失败
    - 当 recovered=true 时，说明历史 runner 曾降级执行过；后续必须改用更精确的链式定位器。
    - 不要因为元素可点击就猜测为 button；只有真实原生/显式无障碍 role 才用 getByRole。
    - 不要用 .first() / .nth() 解决歧义；必须用容器、hasText 或 has 缩小到唯一元素。

    Args:
        locator: Playwright Locator 字符串

    Returns:
        A dictionary containing:
        - success: True if click succeeded, False otherwise
        - error: 一句话错误摘要（适合日志）
        - failure.error_type: 结构化错误类型（见上）
        - failure.summary: 人类可读的失败原因
        - failure.recovered: 是否来自历史 runner 的降级执行结果
        - effective_locator: 真正命中的元素的 locator 字符串
    """
    result = click_with_runtime_context(locator)
    payload = {
        "success": result.success,
        "error": result.error,
        "effective_locator": result.effective_locator,
        "verification_required": result.verification_required,
        "next_step_hint": result.next_step_hint,
        "risk": result.risk,
    }
    if result.failure is not None:
        payload["failure"] = result.failure.model_dump()
    return payload


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

    失败结构化透传，与 click 工具一致。

    Args:
        locator: Playwright Locator 字符串
        value: Text to fill into the element

    Returns:
        A dictionary containing:
        - success: True if fill succeeded, False otherwise
        - error: Error message if fill failed
        - failure.error_type / failure.summary / failure.recovered
    """
    result = fill_with_runtime_context(locator, value)
    payload = {
        "success": result.success,
        "error": result.error,
        "effective_locator": result.effective_locator,
        "verification_required": result.verification_required,
        "next_step_hint": result.next_step_hint,
        "risk": result.risk,
    }
    if result.failure is not None:
        payload["failure"] = result.failure.model_dump()
    return payload


@tool
def playwright_press_tool(key: str, locator: str = "") -> dict:
    """
    Press a keyboard key on the current focused element or a specific locator.

    Use this only when the UI naturally requires keyboard interaction, for example:
    - press "Enter" after filling a search box or focused form field
    - press "Escape" to close a transient popover before retrying
    - press "Tab" only when focus movement is the explicit goal

    Args:
        key: Playwright key name, e.g. "Enter", "Escape", "Tab".
        locator: Optional reusable Playwright Locator string. If omitted, presses
            the key on the current focused element.

    Returns:
        A dictionary containing success/failure, effective_locator, and verification hints.
    """
    return press_with_runtime_context(locator=locator, key=key)


__all__ = [
    "playwright_navigate_tool",
    "playwright_click_tool",
    "playwright_fill_tool",
    "playwright_press_tool",
]
