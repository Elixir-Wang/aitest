"""Tests for Playwright tools"""

import pytest
from unittest.mock import Mock, patch

from app.agents.page_exploration.tools.playwright_tools import (
    playwright_snap_tool,
    playwright_navigate_tool,
    playwright_click_tool,
    playwright_fill_tool,
)


@pytest.fixture
def mock_cli():
    with patch('app.agents.page_exploration.tools.playwright_tools.PlaywrightCLI') as mock:
        yield mock


def test_playwright_snap_tool_success(mock_cli):
    """Test successful snap tool execution"""
    # Mock CLI response
    mock_snap_result = Mock(
        url="https://test.com/page",
        title="Test Page",
        elements=[
            Mock(ref="e15", role="button", name="Click Me", text=None, visible=True),
            Mock(ref="e20", role="textbox", name="Input", text="", visible=True),
        ],
        raw_output="yaml output",
        error=None,
    )
    mock_cli.return_value.snap.return_value = mock_snap_result

    # Execute tool
    result = playwright_snap_tool.invoke({"url": "https://test.com/page"})

    # Verify
    assert result["url"] == "https://test.com/page"
    assert result["title"] == "Test Page"
    assert len(result["elements"]) == 2
    assert result["elements"][0]["ref"] == "e15"
    assert result["elements"][0]["role"] == "button"
    assert result["elements"][0]["name"] == "Click Me"
    assert result["error"] is None


def test_playwright_snap_tool_with_session_id(mock_cli):
    """Test snap tool with session_id"""
    mock_snap_result = Mock(
        url="https://test.com/page",
        title="Test Page",
        elements=[],
        raw_output="yaml output",
        error=None,
    )
    mock_cli.return_value.snap.return_value = mock_snap_result

    # Execute with session_id
    result = playwright_snap_tool.invoke({
        "url": "https://test.com/page",
        "session_id": "test-session-123"
    })

    # Verify PlaywrightCLI was initialized with session_id
    mock_cli.assert_called_once_with(session_id="test-session-123")


def test_playwright_navigate_tool_success(mock_cli):
    """Test successful navigate tool"""
    mock_navigate_result = Mock(
        url="https://test.com/page",
        success=True,
        error=None,
    )
    mock_cli.return_value.navigate.return_value = mock_navigate_result

    result = playwright_navigate_tool.invoke({"url": "https://test.com/page"})

    assert result["url"] == "https://test.com/page"
    assert result["success"] is True
    assert result["error"] is None


def test_playwright_navigate_tool_failure(mock_cli):
    """Test navigate tool failure"""
    mock_navigate_result = Mock(
        url="https://test.com/404",
        success=False,
        error="Page not found",
    )
    mock_cli.return_value.navigate.return_value = mock_navigate_result

    result = playwright_navigate_tool.invoke({"url": "https://test.com/404"})

    assert result["success"] is False
    assert result["error"] == "Page not found"


def test_playwright_click_tool_success(mock_cli):
    """Test successful click tool"""
    mock_click_result = Mock(success=True, error=None)
    mock_cli.return_value.click.return_value = mock_click_result

    result = playwright_click_tool.invoke({
        "locator": "getByRole('button', { name: 'Submit' })"
    })

    assert result["success"] is True
    assert result["error"] is None


def test_playwright_click_tool_failure(mock_cli):
    """Test click tool failure"""
    mock_click_result = Mock(success=False, error="Element not found")
    mock_cli.return_value.click.return_value = mock_click_result

    result = playwright_click_tool.invoke({
        "locator": "getByRole('button', { name: 'NonExistent' })"
    })

    assert result["success"] is False
    assert result["error"] == "Element not found"


def test_playwright_fill_tool_success(mock_cli):
    """Test successful fill tool"""
    mock_fill_result = Mock(success=True, error=None)
    mock_cli.return_value.fill.return_value = mock_fill_result

    result = playwright_fill_tool.invoke({
        "locator": "getByLabel('Email')",
        "value": "test@example.com"
    })

    assert result["success"] is True
    assert result["error"] is None
    mock_cli.return_value.fill.assert_called_once_with("getByLabel('Email')", "test@example.com")


def test_playwright_fill_tool_failure(mock_cli):
    """Test fill tool failure"""
    mock_fill_result = Mock(success=False, error="Element not editable")
    mock_cli.return_value.fill.return_value = mock_fill_result

    result = playwright_fill_tool.invoke({
        "locator": "getByLabel('ReadOnly')",
        "value": "test"
    })

    assert result["success"] is False
    assert result["error"] == "Element not editable"
