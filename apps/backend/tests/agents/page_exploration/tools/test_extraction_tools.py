from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.agents.page_exploration.tools.extraction_tools import playwright_snap_tool
from app.agents.page_exploration.tools.runtime_context import browser_session_context


def _snapshot_result(url: str = "https://test.com/current"):
    return Mock(
        url=url,
        title="Current Page",
        elements=[
            SimpleNamespace(ref="e1", role="button", name="Save", text=None, visible=True),
        ],
        raw_output="snapshot output",
        error=None,
    )


def test_snap_tool_with_url_navigates_then_snapshots():
    with patch("app.agents.page_exploration.tools.extraction_tools.PlaywrightCLI") as mock_cli:
        mock_cli.return_value.snap.return_value = _snapshot_result("https://test.com/page")

        result = playwright_snap_tool.invoke({"url": "https://test.com/page"})

    mock_cli.return_value.snap.assert_called_once_with("https://test.com/page")
    mock_cli.return_value.snap_current.assert_not_called()
    assert result["url"] == "https://test.com/page"
    assert result["elements"][0]["name"] == "Save"


def test_snap_tool_without_url_observes_current_page():
    with patch("app.agents.page_exploration.tools.extraction_tools.PlaywrightCLI") as mock_cli:
        mock_cli.return_value.snap_current.return_value = _snapshot_result()

        result = playwright_snap_tool.invoke({})

    mock_cli.return_value.snap.assert_not_called()
    mock_cli.return_value.snap_current.assert_called_once()
    assert result["url"] == "https://test.com/current"


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
                "elements": [{"id": "button-save", "role": "button", "name": "Save", "visible": True}],
                "text": "summary",
            }

        def close(self):
            pass

    with (
        patch("app.agents.page_exploration.tools.runtime_context.PlaywrightBrowserSession", FakeSession),
        patch("app.agents.page_exploration.tools.extraction_tools.PlaywrightCLI") as mock_cli,
        browser_session_context(start_url="https://test.com", storage_state_path="/tmp/state.json"),
    ):
        result = playwright_snap_tool.invoke({"url": "https://test.com/authed"})

    mock_cli.assert_not_called()
    assert result["url"] == "https://test.com/authed"
    assert result["title"] == "Authed"
    assert result["elements"][0]["ref"] == "button-save"
