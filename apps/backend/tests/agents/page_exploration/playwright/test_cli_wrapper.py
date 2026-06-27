"""Tests for Playwright CLI wrapper."""

import pytest
from unittest.mock import Mock, patch
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
    mock_output = """url: https://test.com/workspace
title: 智能体工作台
elements:
  - ref: e15
    role: button
    name: 创建智能体
    visible: true
  - ref: e20
    role: textbox
    name: 搜索
    text: ''
    visible: true
"""
    mock_subprocess.return_value = Mock(returncode=0, stdout=mock_output, stderr="")

    cli = PlaywrightCLI()
    result = cli.snap("https://test.com/workspace")

    assert isinstance(result, SnapshotResult)
    assert result.url == "https://test.com/workspace"
    assert result.title == "智能体工作台"
    assert len(result.elements) == 2
    assert result.elements[0].ref == "e15"
    assert result.elements[0].role == "button"
    assert result.elements[0].name == "创建智能体"
    assert result.elements[0].visible is True
    assert result.raw_output == mock_output


def test_snap_timeout(mock_subprocess):
    """Test snap command timeout handling."""
    import subprocess
    mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="playwright-cli", timeout=30)

    cli = PlaywrightCLI(timeout=30)

    with pytest.raises(subprocess.TimeoutExpired):
        cli.snap("https://test.com/slow")


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
    assert "playwright-cli" in args
    assert "navigate" in args
    assert "https://test.com/page" in args


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
    assert "playwright-cli" in args
    assert "click" in args
    assert "e15" in args


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
    assert "playwright-cli" in args
    assert "fill" in args
    assert "e20" in args
    assert "test input" in args


def test_session_id_usage(mock_subprocess):
    """Test that session_id is appended to commands."""
    mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

    cli = PlaywrightCLI(session_id="test-session-123")
    cli.click("e15")

    args = mock_subprocess.call_args[0][0]
    assert "--session" in args
    assert "test-session-123" in args
