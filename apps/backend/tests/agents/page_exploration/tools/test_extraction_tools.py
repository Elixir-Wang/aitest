from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.agents.page_exploration.tools.extraction_tools import _focus_elements, playwright_snap_tool
from app.agents.page_exploration.tools.navigation_tools import playwright_click_tool
from app.agents.page_exploration.tools.runtime_context import browser_session_context
from app.services.page_exploration.browser_session import BrowserSessionError


def _snapshot_result(url: str = "https://test.com/current"):
    return Mock(
        url=url,
        title="Current Page",
        elements=[
            SimpleNamespace(ref="e1", role="button", name="Save", text=None, visible=True),
        ],
        accessibility_tree=[
            SimpleNamespace(id="ax-1", role="button", name="Save", level=None, checked=None, disabled=None, expanded=None),
        ],
        visible_text_blocks=["Save"],
        page_text_summary="Current Page summary.",
        error=None,
    )


def test_focus_keeps_unnamed_fill_targets_for_rich_text_editors():
    elements = [
        {"element_id": "obs-1.el-1", "name": "Prompt", "text": "Prompt", "action_type": "click"},
        {"element_id": "obs-1.el-2", "name": "", "text": "", "action_type": "fill"},
        {"element_id": "obs-1.el-3", "name": "欢迎语", "text": "", "action_type": "fill"},
    ]

    focused = _focus_elements(elements, ["Prompt"])

    assert [item["element_id"] for item in focused] == ["obs-1.el-1", "obs-1.el-2"]


def test_snap_tool_requires_bound_runtime_browser_session():
    with pytest.raises(BrowserSessionError, match="browser session is not bound"):
        playwright_snap_tool.invoke({})


def test_overlay_snapshot_records_direct_parent_trigger():
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            self.overlay_open = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def observe(self):
            if not self.overlay_open:
                return {
                    "observation_id": "obs-000001",
                    "url": "https://test.com/agents",
                    "title": "Agents",
                    "interaction_scope": "page",
                    "elements": [{
                        "element_id": "obs-000001.el-001",
                        "role": "button", "role_source": "native", "name": "创建智能体",
                        "action_type": "click", "visible": True,
                        "primary_selector": {"kind": "role", "code": "page.getByRole('button', { name: '创建智能体' })"},
                    }],
                    "accessibility_tree": [], "visible_text_blocks": [],
                }
            return {
                "observation_id": "obs-000002",
                "url": "https://test.com/agents",
                "title": "Agents",
                "interaction_scope": "overlay",
                "overlay": {"type": "dialog", "role": "dialog", "name": "创建智能体"},
                "elements": [{
                    "element_id": "obs-000002.el-001",
                    "role": "button", "role_source": "native", "name": "创建",
                    "action_type": "click", "visible": True,
                    "primary_selector": {"kind": "contextual", "code": "page.getByRole('dialog', { name: '创建智能体' }).getByRole('button', { name: '创建' })"},
                }],
                "accessibility_tree": [], "visible_text_blocks": [],
            }

        def click(self, locator):
            self.overlay_open = True
            return {"action_result": {"success": True, "effective_locator": locator}}

        def close(self):
            pass

    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", FakeSession),
        browser_session_context(start_url="https://test.com/agents", storage_state_path=None),
    ):
        root = playwright_snap_tool.invoke({})
        playwright_click_tool.invoke({"element_id": "obs-000001.el-001"})
        overlay = playwright_snap_tool.invoke({})

    assert root["state_context"]["state_type"] == "root"
    assert overlay["state_context"]["state_type"] == "dialog"
    assert overlay["state_context"]["parent_state_id"] == root["state_context"]["state_id"]
    assert overlay["state_context"]["triggered_by"]["from_state"] == root["state_context"]["state_id"]
    assert overlay["state_context"]["triggered_by"]["element_key"].startswith("button-创建智能体")


def test_snap_tool_uses_runtime_browser_session_when_available():
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            self.start_url = start_url
            self.storage_state_path = storage_state_path
            self.commands = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def navigate(self, url):
            self.commands.append(("navigate", url))
            return {"url": url}

        def observe(self):
            self.commands.append(("observe",))
            return {
                "url": "https://test.com/authed",
                "title": "Authed",
                "page_text_summary": "Authed summary.",
                "elements": [{"id": "button-save", "role": "button", "name": "Save", "visible": True}],
                "accessibility_tree": [{"id": "ax-1", "role": "button", "name": "Save"}],
                "visible_text_blocks": ["Save"],
            }

        def close(self):
            pass

    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", FakeSession),
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        result = playwright_snap_tool.invoke({"url": "https://test.com/authed"})

    assert result["url"] == "https://test.com/authed"
    assert result["title"] == "Authed"
    assert result["page_text_summary"] == "Authed summary."
    assert result["elements"][0]["role"] == "button"
    assert result["elements"][0]["name"] == "Save"
    assert result["accessibility_tree"][0]["name"] == "Save"
    assert result["visible_text_blocks"] == ["Save"]
    assert "raw_output" not in result


def test_snap_tool_preserves_observed_url_for_server_projection():
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            self.start_url = start_url
            self.storage_state_path = storage_state_path

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def navigate(self, url):
            return {"url": url}

        def observe(self):
            return {
                "url": "https://test.com/workspace/botSetting?id=19221&type=add&tab=1",
                "title": "Bot Setting",
                "page_text_summary": "Bot Setting summary.",
                "elements": [{"id": "button-save", "role": "button", "name": "Save", "visible": True}],
                "accessibility_tree": [{"id": "ax-1", "role": "button", "name": "Save"}],
                "visible_text_blocks": ["Save"],
            }

        def close(self):
            pass

    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", FakeSession),
        browser_session_context(start_url="https://test.com", storage_state_path=None),
    ):
        result = playwright_snap_tool.invoke({"url": "https://test.com/workspace/botSetting?id=19221&type=add"})

    assert result["url"] == "https://test.com/workspace/botSetting?id=19221&type=add&tab=1"
    assert "state_observation_hint" not in result


def test_browser_session_context_starts_clean_browser_without_auth_state():
    created_sessions = []

    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            self.start_url = start_url
            self.storage_state_path = storage_state_path
            created_sessions.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def navigate(self, url):
            return {"url": url}

        def observe(self):
            return {
                "url": self.start_url,
                "title": "Clean",
                "page_text_summary": "Clean summary.",
                "elements": [],
                "accessibility_tree": [],
                "visible_text_blocks": [],
            }

        def close(self):
            pass

    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", FakeSession),
        browser_session_context(start_url="https://test.com", storage_state_path=None),
    ):
        result = playwright_snap_tool.invoke({})

    assert result["url"] == "https://test.com"
    assert result["title"] == "Clean"
    assert result["elements"] == []
    assert result["accessibility_tree"] == []
    assert created_sessions[0].storage_state_path is None


def test_snap_tool_focus_keywords_filters_elements_and_tree():
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            self.start_url = start_url
            self.storage_state_path = storage_state_path

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def navigate(self, url):
            return {"url": url}

        def observe(self):
            return {
                "url": "https://test.com/workspace",
                "title": "Workspace",
                "page_text_summary": "Workspace summary.",
                "elements": [
                    {"id": "save-btn", "role": "button", "name": "Save", "text": None, "visible": True},
                    {"id": "create-btn", "role": "button", "name": "Create Agent", "text": None, "visible": True},
                ],
                "accessibility_tree": [
                    {"id": "ax-1", "role": "button", "name": "Save"},
                    {"id": "ax-2", "role": "button", "name": "Create Agent"},
                    {"id": "ax-3", "role": "textbox", "name": "Search"},
                ],
                "visible_text_blocks": ["Save", "Create Agent", "Search"],
            }

        def close(self):
            pass

    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", FakeSession),
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        result = playwright_snap_tool.invoke({
            "url": "https://test.com/workspace",
            "focus_keywords": ["create"],
        })

    # focus_keywords 过滤后只剩 create 相关元素
    assert len(result["elements"]) == 1
    assert {el["name"] for el in result["elements"]} == {"Create Agent"}
    assert [node["name"] for node in result["accessibility_tree"]] == ["Create Agent"]
    assert result["visible_text_blocks"] == ["Create Agent"]


def test_snap_tool_focus_keywords_falls_back_to_full_snapshot_when_no_match():
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            self.start_url = start_url
            self.storage_state_path = storage_state_path

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def navigate(self, url):
            return {"url": url}

        def observe(self):
            return {
                "url": "https://test.com/workspace",
                "title": "Workspace",
                "page_text_summary": "Workspace summary.",
                "elements": [
                    {"id": "save-btn", "role": "button", "name": "Save", "text": None, "visible": True},
                ],
                "accessibility_tree": [
                    {"id": "ax-1", "role": "button", "name": "Save"},
                ],
                "visible_text_blocks": ["Save"],
            }

        def close(self):
            pass

    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", FakeSession),
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        result = playwright_snap_tool.invoke({
            "url": "https://test.com/workspace",
            "focus_keywords": ["missing"],
        })

    assert len(result["elements"]) == 1
    assert result["elements"][0]["name"] == "Save"
    assert [node["name"] for node in result["accessibility_tree"]] == ["Save"]


def test_snap_tool_returns_distinct_runtime_ids_for_ambiguous_elements():
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            self.start_url = start_url
            self.storage_state_path = storage_state_path

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def navigate(self, url):
            return {"url": url}

        def observe(self):
            return {
                "observation_id": "obs-000001",
                "url": "https://test.com/agentStore",
                "title": "Agent Store",
                "page_text_summary": "Agent Store summary.",
                "elements": [
                    {
                        "element_id": "obs-000001.el-001",
                        "role": "button",
                        "role_source": "native",
                        "name": "创建",
                        "text": "创建",
                        "visible": True,
                        "primary_selector": {
                            "kind": "role",
                            "code": "page.getByRole('button', { name: '创建' })",
                        },
                        "ancestor_chain": [
                            {"role": "navigation", "name": "创建智能体 工作台"},
                        ],
                    },
                    {
                        "element_id": "obs-000001.el-002",
                        "role": "button",
                        "role_source": "native",
                        "name": "创建",
                        "text": "创建",
                        "visible": True,
                        "primary_selector": {
                            "kind": "role",
                            "code": "page.getByRole('button', { name: '创建' })",
                        },
                        "ancestor_chain": [
                            {"role": "div", "name": "智能体名称 请输入智能体名称 智能体功能介绍 创建"},
                        ],
                    },
                ],
                "accessibility_tree": [],
                "visible_text_blocks": ["创建", "智能体名称", "请输入智能体名称"],
            }

        def close(self):
            pass

    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", FakeSession),
        browser_session_context(start_url="https://test.com", storage_state_path=None),
    ):
        result = playwright_snap_tool.invoke({})

    assert [item["element_id"] for item in result["elements"]] == [
        "obs-000001.el-001", "obs-000001.el-002",
    ]
    assert result["elements"][1]["ancestor_chain"][0]["name"] == "智能体名称 请输入智能体名称 智能体功能介绍 创建"
    assert "match_groups" not in result
