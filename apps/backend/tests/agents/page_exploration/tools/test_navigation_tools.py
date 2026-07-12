from unittest.mock import patch

import pytest

from app.agents.page_exploration.tools.navigation_tools import (
    playwright_click_tool,
    playwright_fill_tool,
    playwright_navigate_tool,
    playwright_press_tool,
)
from app.agents.page_exploration.tools import get_local_tools
from app.agents.page_exploration.tools.runtime_context import browser_session_context
from app.services.page_exploration.browser_session import BrowserSessionError


def test_click_and_fill_use_runtime_browser_session_for_snapshot_refs():
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            self.commands = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def click(self, element_id):
            self.commands.append(("click", element_id))
            return {"status": "ok", "action_result": {"success": True, "effective_locator": element_id}}

        def fill(self, element_id, value):
            self.commands.append(("fill", element_id, value))
            return {"status": "ok", "action_result": {"success": True, "effective_locator": element_id}}

        def close(self):
            pass

    fake = FakeSession(start_url="https://test.com", storage_state_path="/tmp/state.json")
    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", lambda **kw: fake),
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        click_result = playwright_click_tool.invoke({"element_id": "button-save"})
        fill_result = playwright_fill_tool.invoke({"element_id": "textbox-name", "value": "hello"})

    assert click_result["success"] is True
    assert "effective_locator" not in click_result
    assert click_result["verification_required"] is True
    assert "业务完成判据" in click_result["next_step_hint"]
    assert fill_result["success"] is True
    assert "effective_locator" not in fill_result
    assert fill_result["verification_required"] is True
    assert "业务完成判据" in fill_result["next_step_hint"]
    # 验证 locator 透传给 session
    assert ("click", "button-save") in fake.commands
    assert ("fill", "textbox-name", "hello") in fake.commands


def test_navigation_tools_require_bound_runtime_browser_session():
    with pytest.raises(BrowserSessionError, match="browser session is not bound"):
        playwright_navigate_tool.invoke({"url": "https://test.com/page"})

    with pytest.raises(BrowserSessionError, match="browser session is not bound"):
        playwright_click_tool.invoke({"element_id": "button-save"})

    with pytest.raises(BrowserSessionError, match="browser session is not bound"):
        playwright_fill_tool.invoke({"element_id": "textbox-name", "value": "hello"})


def test_keyboard_actions_are_not_available_to_exploration_agent():
    tool_names = {tool.name for tool in get_local_tools()}
    assert "playwright_press_tool" not in tool_names

    result = playwright_press_tool.invoke({"key": "Tab"})
    assert result["success"] is False
    assert result["failure"]["error_type"] == "keyboard_action_forbidden"


def test_click_failure_does_not_auto_observe_to_avoid_infinite_loop():
    """click 失败时不应自动 observe，避免物理死循环。

    修复：取消 _is_stale_element_error 静默 observe 分支后，错误
    原样透传给 LLM，由 LLM 决定如何重试。
    """
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            self.observed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def click(self, element_id):
            raise BrowserSessionError(f"Unknown element id: {element_id}")

        def observe(self):
            self.observed = True
            return {"elements": []}

        def close(self):
            pass

    fake = FakeSession(start_url="x", storage_state_path="x")
    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", lambda **kw: fake),
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        result = playwright_click_tool.invoke({"element_id": "button-old"})

    assert result["success"] is False
    assert "Unknown element id" in result["error"]
    # 关键：失败时不应静默 observe
    assert fake.observed is False


def test_click_accepts_playwright_role_locator_string():
    """click 应原样透传 getByRole 字符串（具体解析由 JS 端完成）。"""
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            self.last_click = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def click(self, element_id):
            self.last_click = element_id
            return {"status": "ok", "action_result": {"success": True, "effective_locator": element_id}}

        def close(self):
            pass

    fake = FakeSession(start_url="x", storage_state_path="x")
    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", lambda **kw: fake),
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        result = playwright_click_tool.invoke({
            "element_id": "getByRole('treeitem', { name: '自主规划 Agent' })"
        })

    assert result["success"] is True
    assert fake.last_click == "getByRole('treeitem', { name: '自主规划 Agent' })"


def test_click_preserves_recovered_failure_warning_on_success():
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def click(self, element_id):
            return {
                "status": "ok",
                "action_result": {
                    "success": True,
                    "effective_locator": element_id,
                    "failure": {
                        "error_type": "locator_not_unique",
                        "summary": "定位器匹配到多个元素。",
                        "raw": "strict mode violation",
                        "recovered": True,
                        "recovery_warning": "已自动选择第一个元素，请改用更精确定位器。",
                    },
                },
            }

        def close(self):
            pass

    fake = FakeSession(start_url="x", storage_state_path="x")
    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", lambda **kw: fake),
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        result = playwright_click_tool.invoke({"element_id": "getByRole('button', { name: '编辑' })"})

    assert result["success"] is True
    assert result["failure"]["recovered"] is True
    assert result["failure"]["error_type"] == "locator_not_unique"
    assert "更精确定位器" in result["failure"]["recovery_warning"]
    assert result["verification_required"] is True
    assert result["risk"] == "ambiguous_or_recovered_locator"
    assert "playwright_snap_tool" in result["next_step_hint"]


def test_click_success_with_structural_css_reports_low_confidence_risk():
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def click(self, element_id):
            return {"status": "ok", "action_result": {"success": True, "effective_locator": element_id}}

        def close(self):
            pass

    fake = FakeSession(start_url="x", storage_state_path="x")
    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", lambda **kw: fake),
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        result = playwright_click_tool.invoke({
            "element_id": "page.locator('body > div:nth-of-type(1) > button:nth-of-type(2)')",
        })

    assert result["success"] is True
    assert result["verification_required"] is True
    assert result["risk"] == "structural_css_locator"
    assert "Toast" in result["next_step_hint"]


def test_fill_accepts_playwright_label_locator_string():
    """fill 应原样透传 getByLabel 字符串。"""
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            self.last_fill = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def fill(self, element_id, value):
            self.last_fill = (element_id, value)
            return {"status": "ok", "action_result": {"success": True, "effective_locator": element_id}}

        def close(self):
            pass

    fake = FakeSession(start_url="x", storage_state_path="x")
    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", lambda **kw: fake),
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        result = playwright_fill_tool.invoke({
            "element_id": "getByLabel('用户名')",
            "value": "张三",
        })

    assert result["success"] is True
    assert fake.last_fill == ("getByLabel('用户名')", "张三")
