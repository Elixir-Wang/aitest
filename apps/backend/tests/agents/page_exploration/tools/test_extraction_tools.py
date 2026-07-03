from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.agents.page_exploration.tools.extraction_tools import playwright_snap_tool
from app.agents.page_exploration.tools.runtime_context import browser_session_context
from app.services.exploration.browser_session import BrowserSessionError


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


def test_snap_tool_requires_bound_runtime_browser_session():
    with pytest.raises(BrowserSessionError, match="browser session is not bound"):
        playwright_snap_tool.invoke({})


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
    assert result["elements"][0]["ref"] == "button-save"
    assert result["accessibility_tree"][0]["name"] == "Save"
    assert result["visible_text_blocks"] == ["Save"]
    assert "raw_output" not in result


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

    assert [element["ref"] for element in result["elements"]] == ["create-btn"]
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

    assert [element["ref"] for element in result["elements"]] == ["save-btn"]
    assert [node["name"] for node in result["accessibility_tree"]] == ["Save"]
