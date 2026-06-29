"""Tests for Playwright CLI wrapper."""

import subprocess

import pytest
from unittest.mock import Mock, patch
from app.core import settings
from app.agents.page_exploration.playwright.cli_wrapper import PlaywrightCLI
from app.agents.page_exploration.playwright.schemas import (
    SnapshotResult,
    NavigateResult,
    ClickResult,
    ElementInfo,
)


@pytest.fixture
def mock_subprocess():
    with patch('subprocess.run') as mock:
        yield mock


def test_snap_success(mock_subprocess):
    """Test successful snap command with YAML parsing."""
    mock_output = """### Page
- Page URL: https://test.com/workspace
- Page Title: 智能体工作台
### Snapshot
- generic [ref=e1]:
  - button "创建智能体" [ref=e15]
  - textbox "搜索" [ref=e20]
"""
    mock_subprocess.side_effect = [
        Mock(returncode=0, stdout="", stderr=""),
        Mock(returncode=0, stdout=mock_output, stderr=""),
    ]

    cli = PlaywrightCLI()
    result = cli.snap("https://test.com/workspace")

    assert isinstance(result, SnapshotResult)
    assert result.url == "https://test.com/workspace"
    assert result.title == "智能体工作台"
    assert len(result.elements) == 3
    assert result.elements[0].ref == "e1"
    assert result.elements[0].role == "generic"
    assert result.elements[0].visible is True
    assert result.elements[1].ref == "e15"
    assert result.elements[1].role == "button"
    assert result.elements[1].name == "创建智能体"
    assert result.raw_output == mock_output
    assert mock_subprocess.call_count == 2
    assert mock_subprocess.call_args_list[0][0][0][-2:] == ["open", "https://test.com/workspace"]
    assert mock_subprocess.call_args_list[1][0][0][-1:] == ["snapshot"]


def test_snap_uses_action_timeouts(mock_subprocess):
    """Test snap command uses per-action timeouts."""
    mock_subprocess.side_effect = [
        Mock(returncode=0, stdout="", stderr=""),
        Mock(returncode=0, stdout="### Page\n- Page URL: https://test.com/slow\n- Page Title: Slow\n### Snapshot\n", stderr=""),
    ]

    cli = PlaywrightCLI()
    cli.snap("https://test.com/slow")

    assert mock_subprocess.call_args_list[0].kwargs["timeout"] == settings.PLAYWRIGHT_CLI_OPEN_TIMEOUT_SECONDS
    assert mock_subprocess.call_args_list[1].kwargs["timeout"] == settings.PLAYWRIGHT_CLI_SNAPSHOT_TIMEOUT_SECONDS


def test_snap_retries_open_once(mock_subprocess):
    """Test snap retries open once before failing."""
    mock_subprocess.side_effect = [
        Mock(returncode=1, stdout="", stderr="temporary error"),
        Mock(returncode=1, stdout="", stderr="temporary error"),
    ]

    cli = PlaywrightCLI()
    result = cli.snap("https://test.com/slow")

    assert result.error == "temporary error"
    assert mock_subprocess.call_count == 2
    assert mock_subprocess.call_args_list[0][0][0][-2:] == ["open", "https://test.com/slow"]
    assert mock_subprocess.call_args_list[1][0][0][-2:] == ["open", "https://test.com/slow"]


def test_click_retries_timeout_once(mock_subprocess):
    """Test action timeout is retried once."""
    mock_subprocess.side_effect = [
        subprocess.TimeoutExpired(cmd="playwright-cli", timeout=settings.PLAYWRIGHT_CLI_CLICK_TIMEOUT_SECONDS),
        Mock(returncode=0, stdout="", stderr=""),
    ]

    cli = PlaywrightCLI()
    result = cli.click("e15")

    assert result.success is True
    assert mock_subprocess.call_count == 2
    assert mock_subprocess.call_args_list[0].kwargs["timeout"] == settings.PLAYWRIGHT_CLI_CLICK_TIMEOUT_SECONDS
    assert mock_subprocess.call_args_list[1].kwargs["timeout"] == settings.PLAYWRIGHT_CLI_CLICK_TIMEOUT_SECONDS


def test_snap_failure(mock_subprocess):
    """测试快照失败（非超时）"""
    mock_subprocess.side_effect = [
        Mock(returncode=1, stdout="", stderr="Page not found"),
        Mock(returncode=1, stdout="", stderr="Page not found"),
    ]

    cli = PlaywrightCLI()
    result = cli.snap("https://test.com/404")

    assert result.error == "Page not found"
    assert result.title == ""
    assert len(result.elements) == 0


def test_navigate_success(mock_subprocess):
    """Test successful navigate command."""
    mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

    cli = PlaywrightCLI()
    result = cli.navigate("https://test.com/page")

    assert isinstance(result, NavigateResult)
    assert result.url == "https://test.com/page"
    assert result.success is True
    assert result.error is None

    mock_subprocess.assert_called_once()
    args = mock_subprocess.call_args[0][0]
    assert args[0].endswith("playwright-cli.cmd")
    assert "goto" in args
    assert "https://test.com/page" in args
    assert mock_subprocess.call_args.kwargs["timeout"] == settings.PLAYWRIGHT_CLI_GOTO_TIMEOUT_SECONDS


def test_navigate_failure(mock_subprocess):
    """Test navigate command failure."""
    mock_subprocess.return_value = Mock(returncode=1, stdout="", stderr="Navigation failed")

    cli = PlaywrightCLI()
    result = cli.navigate("https://invalid.com")

    assert isinstance(result, NavigateResult)
    assert result.success is False
    assert result.error == "Navigation failed"


def test_click_success(mock_subprocess):
    """Test successful click command."""
    mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

    cli = PlaywrightCLI()
    result = cli.click("e15")

    assert isinstance(result, ClickResult)
    assert result.success is True
    assert result.error is None

    mock_subprocess.assert_called_once()
    args = mock_subprocess.call_args[0][0]
    assert args[0].endswith("playwright-cli.cmd")
    assert "click" in args
    assert "e15" in args
    assert mock_subprocess.call_args.kwargs["timeout"] == settings.PLAYWRIGHT_CLI_CLICK_TIMEOUT_SECONDS


def test_click_failure(mock_subprocess):
    """Test click command failure."""
    mock_subprocess.return_value = Mock(returncode=1, stdout="", stderr="Element not found")

    cli = PlaywrightCLI()
    result = cli.click("e99")

    assert isinstance(result, ClickResult)
    assert result.success is False
    assert result.error == "Element not found"


def test_fill_success(mock_subprocess):
    """Test successful fill command."""
    mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

    cli = PlaywrightCLI()
    result = cli.fill("e20", "test input")

    assert result.success is True
    assert result.error is None

    mock_subprocess.assert_called_once()
    args = mock_subprocess.call_args[0][0]
    assert args[0].endswith("playwright-cli.cmd")
    assert "fill" in args
    assert "e20" in args
    assert "test input" in args
    assert mock_subprocess.call_args.kwargs["timeout"] == settings.PLAYWRIGHT_CLI_FILL_TIMEOUT_SECONDS


def test_fill_failure(mock_subprocess):
    """测试填写失败"""
    mock_subprocess.return_value = Mock(returncode=1, stdout="", stderr="Element not found")

    cli = PlaywrightCLI()
    result = cli.fill("getByLabel('missing')", "value")

    assert result.success is False
    assert result.error == "Element not found"


def test_session_id_usage(mock_subprocess):
    """Test that session_id is appended to commands."""
    mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

    cli = PlaywrightCLI(session_id="test-session-123")
    cli.click("e15")

    args = mock_subprocess.call_args[0][0]
    assert "-s=test-session-123" in args
