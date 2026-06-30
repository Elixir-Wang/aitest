from unittest.mock import Mock, patch

from app.agents.page_exploration.tools.navigation_tools import (
    playwright_click_tool,
    playwright_fill_tool,
)
from app.agents.page_exploration.tools.runtime_context import browser_session_context
from app.services.exploration.browser_session import BrowserSessionError


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
            return {"status": "passed"}

        def fill(self, element_id, value):
            self.commands.append(("fill", element_id, value))
            return {"status": "passed"}

    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", FakeSession),
        patch("app.agents.page_exploration.tools.navigation_tools.PlaywrightCLI") as mock_cli,
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        click_result = playwright_click_tool.invoke({"locator": "button-save"})
        fill_result = playwright_fill_tool.invoke({"locator": "e20", "value": "hello"})

    mock_cli.assert_not_called()
    assert click_result == {"success": True, "error": None}
    assert fill_result == {"success": True, "error": None}


def test_semantic_locator_falls_back_to_cli_inside_runtime_context():
    class FakeSession:
        def __init__(self, *, start_url, storage_state_path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", FakeSession),
        patch("app.agents.page_exploration.tools.navigation_tools.PlaywrightCLI") as mock_cli,
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        mock_cli.return_value.click.return_value = Mock(success=True, error=None)
        result = playwright_click_tool.invoke({"locator": "getByRole('button', { name: 'Save' })"})

    mock_cli.assert_called_once()
    assert result == {"success": True, "error": None}


def test_stale_snapshot_ref_returns_recoverable_error():
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

    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", FakeSession),
        patch("app.agents.page_exploration.tools.navigation_tools.PlaywrightCLI") as mock_cli,
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        result = playwright_click_tool.invoke({"locator": "button-old"})

    mock_cli.assert_not_called()
    assert result["success"] is False
    assert "stale_ref" in result["error"]
