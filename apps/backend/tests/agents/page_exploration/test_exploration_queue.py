"""Tests for ExplorationQueue"""

import pytest

from app.agents.page_exploration.exploration_queue import ExplorationQueue


def test_exploration_queue_initialization():
    """Test queue initialization"""
    queue = ExplorationQueue("https://test.com/start", max_depth=3)

    assert queue.size() == 1
    assert queue.explored_count() == 0
    assert queue.max_depth == 3


def test_pop_url():
    """Test popping URL from queue"""
    queue = ExplorationQueue("https://test.com/start")

    url, depth = queue.pop()
    assert url == "https://test.com/start"
    assert depth == 0
    assert queue.is_empty()


def test_add_url_within_scope():
    """Test adding URL within scope"""
    queue = ExplorationQueue("https://test.com/start")

    # Add URL in same domain
    added = queue.add_url("https://test.com/page1", depth=1)
    assert added is True
    assert queue.size() == 2


def test_add_url_out_of_scope():
    """Test adding URL outside scope is rejected"""
    queue = ExplorationQueue("https://test.com/start")

    # Try to add URL from different domain
    added = queue.add_url("https://other.com/page", depth=1)
    assert added is False
    assert queue.size() == 1  # Only start URL


def test_add_url_already_explored():
    """Test adding already explored URL is rejected"""
    queue = ExplorationQueue("https://test.com/start")

    # Pop and mark as explored
    url, depth = queue.pop()
    queue.mark_explored(url)

    # Try to add same URL
    added = queue.add_url("https://test.com/start", depth=0)
    assert added is False


def test_add_url_exceeds_max_depth():
    """Test adding URL that exceeds max depth is rejected"""
    queue = ExplorationQueue("https://test.com/start", max_depth=2)

    # Try to add URL at depth 3 (exceeds max_depth=2)
    added = queue.add_url("https://test.com/deep", depth=3)
    assert added is False


def test_url_normalization_prevents_duplicates():
    """Test URL normalization prevents duplicate URLs"""
    queue = ExplorationQueue("https://test.com/start")

    # Add URL
    queue.add_url("https://test.com/workspace/agents", depth=1)

    # Try to add same URL with trailing slash
    added = queue.add_url("https://test.com/workspace/agents/", depth=1)
    assert added is False

    # Try to add same URL with query params
    added = queue.add_url("https://test.com/workspace/agents?tab=all", depth=1)
    assert added is False


def test_cross_environment_url_detection():
    """Test that URLs from different environments are treated as same"""
    queue = ExplorationQueue("https://test.example.com/start")
    queue.pop()  # Remove start URL

    # Add URL from test environment
    queue.add_url("https://test.example.com/workspace/agents", depth=1)
    queue.mark_explored("https://test.example.com/workspace/agents")

    # Try to add same path from prod environment (should be rejected)
    added = queue.add_url("https://prod.example.com/workspace/agents", depth=1)
    assert added is False


def test_is_explored():
    """Test checking if URL was explored"""
    queue = ExplorationQueue("https://test.com/start")

    url, depth = queue.pop()
    assert queue.is_explored(url) is False

    queue.mark_explored(url)
    assert queue.is_explored(url) is True


def test_breadth_first_order():
    """Test that queue maintains breadth-first order (FIFO)"""
    queue = ExplorationQueue("https://test.com/start")
    queue.pop()  # Remove start URL

    # Add URLs
    queue.add_url("https://test.com/page1", depth=1)
    queue.add_url("https://test.com/page2", depth=1)
    queue.add_url("https://test.com/page3", depth=1)

    # Pop in order
    url1, _ = queue.pop()
    assert "page1" in url1

    url2, _ = queue.pop()
    assert "page2" in url2

    url3, _ = queue.pop()
    assert "page3" in url3


def test_get_explored_urls():
    """Test getting list of explored URLs"""
    queue = ExplorationQueue("https://test.com/start")

    # Explore a few URLs
    url1, _ = queue.pop()
    queue.mark_explored(url1)

    queue.add_url("https://test.com/page1", depth=1)
    url2, _ = queue.pop()
    queue.mark_explored(url2)

    explored = queue.get_explored_urls()
    assert len(explored) == 2
    assert "/start" in explored
    assert "/page1" in explored


def test_custom_scope():
    """Test custom scope parameter"""
    # Set custom scope to only explore /workspace/* paths
    queue = ExplorationQueue(
        "https://test.com/workspace/start",
        scope="https://test.com/workspace"
    )

    # URL within scope
    added = queue.add_url("https://test.com/workspace/agents", depth=1)
    assert added is True

    # URL outside scope
    added = queue.add_url("https://test.com/other/page", depth=1)
    assert added is False
