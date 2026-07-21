from app.agents.page_exploration.prompts.system_prompt import SYSTEM_PROMPT
from app.agents.page_exploration.tools import get_local_tools


def test_agent_has_no_locator_or_keyboard_escape_hatches():
    names = {tool.name for tool in get_local_tools()}

    assert "playwright_scoped_query_tool" not in names
    assert "playwright_press_tool" not in names
    assert "playwright_screenshot_tool" not in names
    assert {"playwright_snap_tool", "playwright_click_tool", "playwright_fill_tool"} <= names


def test_agent_prompt_forbids_screenshots():
    assert "禁止调用截图工具" in SYSTEM_PROMPT
    assert "调用 `playwright_screenshot_tool`" not in SYSTEM_PROMPT
