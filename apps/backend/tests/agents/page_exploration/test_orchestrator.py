"""Tests for ExplorationOrchestrator"""

import pytest
import time

from app.agents.page_exploration.orchestrator import ExplorationOrchestrator


@pytest.fixture
def temp_base_dir(tmp_path, monkeypatch):
    """Setup temp directory and patch base path"""
    monkeypatch.setattr(
        'app.agents.page_exploration.artifact_service.Path',
        lambda x: tmp_path if x == "data/projects" else __import__('pathlib').Path(x)
    )
    monkeypatch.setattr(
        'app.agents.page_exploration.services.explored_urls_service.Path',
        lambda x: tmp_path if x == "data/projects" else __import__('pathlib').Path(x)
    )
    return tmp_path


def test_orchestrator_initialization():
    """Test orchestrator initialization"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start",
        max_depth=3,
        max_pages=50
    )

    assert orchestrator.project_id == "proj-test"
    assert orchestrator.run_id == "run-001"
    assert orchestrator.start_url == "https://test.com/start"
    assert orchestrator.max_depth == 3
    assert orchestrator.max_pages == 50


def test_should_continue_initially():
    """Test should_continue returns True initially"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start"
    )

    should_continue, reason = orchestrator.should_continue()
    assert should_continue is True
    assert reason is None


def test_should_continue_when_queue_empty():
    """Test should_continue returns False when queue is empty"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start"
    )

    # Pop the only URL
    orchestrator.get_next_url()

    should_continue, reason = orchestrator.should_continue()
    assert should_continue is False
    assert reason == "all_pages_explored"


def test_should_continue_max_pages_reached():
    """Test should_continue returns False when max_pages reached"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start",
        max_pages=2
    )

    # Mark 2 pages as explored
    orchestrator.mark_page_explored("https://test.com/page1")
    orchestrator.mark_page_explored("https://test.com/page2")

    should_continue, reason = orchestrator.should_continue()
    assert should_continue is False
    assert reason == "max_pages_reached"


def test_should_continue_max_duration_reached():
    """Test should_continue returns False when max_duration reached"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start",
        max_duration_seconds=1  # Very short duration
    )

    orchestrator.start_exploration()
    time.sleep(1.1)  # Wait slightly longer than max_duration

    should_continue, reason = orchestrator.should_continue()
    assert should_continue is False
    assert reason == "max_duration_reached"


def test_get_next_url():
    """Test getting next URL from queue"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start"
    )

    url, depth = orchestrator.get_next_url()
    assert url == "https://test.com/start"
    assert depth == 0


def test_mark_page_explored():
    """Test marking page as explored"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start"
    )

    url = "https://test.com/page1"
    orchestrator.mark_page_explored(url)

    assert orchestrator.is_already_explored(url) is True


def test_add_discovered_links():
    """Test adding discovered links to queue"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start",
        max_depth=3
    )

    links = [
        {
            "url": "https://test.com/page1",
            "text": "Page 1",
            "locator": "getByRole('link', { name: 'Page 1' })"
        },
        {
            "url": "https://test.com/page2",
            "text": "Page 2",
            "locator": "getByRole('link', { name: 'Page 2' })"
        }
    ]

    added_count = orchestrator.add_discovered_links(
        current_url="https://test.com/start",
        links=links,
        current_depth=0
    )

    assert added_count == 2
    assert orchestrator.queue.size() == 3  # start + 2 links


def test_add_discovered_page():
    """Test adding discovered page record"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start"
    )

    orchestrator.add_discovered_page(
        page_id="page-workspace-agents",
        page_file="../../pages/page-workspace-agents.yaml",
        normalized_path="/workspace/agents",
        status="new",
        elements_count=15,
        exploration_status="completed"
    )

    assert len(orchestrator.discovered_pages) == 1
    assert orchestrator.discovered_pages[0]["page_id"] == "page-workspace-agents"
    assert orchestrator.current_page_id == "page-workspace-agents"


def test_add_issue():
    """Test adding issue"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start"
    )

    orchestrator.add_issue("Page not found: /404")
    orchestrator.add_issue("Timeout on /slow")

    assert len(orchestrator.issues) == 2
    assert "Page not found" in orchestrator.issues[0]


def test_get_statistics():
    """Test getting exploration statistics"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start"
    )

    orchestrator.start_exploration()
    time.sleep(0.1)

    stats = orchestrator.get_statistics()

    assert stats["queue_size"] == 1
    assert stats["explored_count"] == 0
    assert stats["discovered_pages"] == 0
    assert stats["issues_count"] == 0
    assert stats["elapsed_seconds"] > 0


def test_finalize_exploration(temp_base_dir):
    """Test finalizing exploration and generating artifacts"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start"
    )

    orchestrator.start_exploration()

    # Add some discovered pages
    orchestrator.add_discovered_page(
        page_id="page-start",
        page_file="../../pages/page-start.yaml",
        normalized_path="/start",
        status="new",
        elements_count=10,
        exploration_status="completed"
    )

    orchestrator.add_discovered_page(
        page_id="page-about",
        page_file="../../pages/page-about.yaml",
        normalized_path="/about",
        status="new",
        elements_count=5,
        exploration_status="completed"
    )

    time.sleep(0.1)  # Ensure some duration

    result = orchestrator.finalize_exploration()

    assert result["run_id"] == "run-001"
    assert result["pages_discovered"] == 2
    assert result["successful_pages"] == 2
    assert result["failed_pages"] == 0
    assert result["elements_found"] == 15
    assert result["duration_seconds"] > 0
    assert "discovered_pages" in result["artifacts"]
    assert "run_summary" in result["artifacts"]
    assert "report" in result["artifacts"]


def test_finalize_exploration_with_failures(temp_base_dir):
    """Test finalization with some failed pages"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start"
    )

    orchestrator.start_exploration()

    orchestrator.add_discovered_page(
        page_id="page-success",
        page_file="../../pages/page-success.yaml",
        normalized_path="/success",
        status="new",
        elements_count=10,
        exploration_status="completed"
    )

    orchestrator.add_discovered_page(
        page_id="page-failed",
        page_file="../../pages/page-failed.yaml",
        normalized_path="/failed",
        status="new",
        elements_count=0,
        exploration_status="failed"
    )

    result = orchestrator.finalize_exploration()

    assert result["successful_pages"] == 1
    assert result["failed_pages"] == 1


def test_generate_recommendations_max_pages():
    """Test recommendations when max_pages is reached"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start",
        max_pages=5
    )

    # Mark 5 pages as explored
    for i in range(5):
        orchestrator.mark_page_explored(f"https://test.com/page{i}")

    recommendations = orchestrator._generate_recommendations()

    assert any("max_pages" in rec for rec in recommendations)


def test_generate_recommendations_low_depth():
    """Test recommendations when depth is low"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start",
        max_depth=1
    )

    recommendations = orchestrator._generate_recommendations()

    assert any("max_depth" in rec for rec in recommendations)


def test_generate_recommendations_many_failures():
    """Test recommendations when many pages failed"""
    orchestrator = ExplorationOrchestrator(
        project_id="proj-test",
        run_id="run-001",
        start_url="https://test.com/start"
    )

    # Add several failed pages
    for i in range(3):
        orchestrator.add_discovered_page(
            page_id=f"page-failed-{i}",
            page_file=f"../../pages/page-failed-{i}.yaml",
            normalized_path=f"/failed{i}",
            status="new",
            elements_count=0,
            exploration_status="failed"
        )

    recommendations = orchestrator._generate_recommendations()

    assert any("failed page" in rec for rec in recommendations)
