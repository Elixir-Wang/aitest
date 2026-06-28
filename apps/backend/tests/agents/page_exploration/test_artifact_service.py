"""Tests for ArtifactService"""

import pytest
from pathlib import Path
import yaml

from app.agents.page_exploration.artifact_service import ArtifactService


@pytest.fixture
def temp_base_dir(tmp_path):
    """Temp directory for isolated file system testing"""
    return tmp_path


def test_write_discovered_pages(temp_base_dir):
    """Test writing discovered_pages.yaml"""
    service = ArtifactService("proj-test", "run-001", base_dir=temp_base_dir)

    pages = [
        {
            "page_id": "page-workspace-agents",
            "page_file": "../../pages/page-workspace-agents.yaml",
            "normalized_path": "/workspace/agents",
            "status": "new",
            "elements_count": 15,
            "exploration_status": "completed"
        }
    ]

    file_path = service.write_discovered_pages(pages)

    assert file_path.exists()
    assert "discovered_pages.yaml" in str(file_path)

    # Verify content
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["run_id"] == "run-001"
    assert len(data["pages"]) == 1
    assert data["pages"][0]["page_id"] == "page-workspace-agents"


def test_write_run_summary(temp_base_dir):
    """Test writing run.yaml summary"""
    service = ArtifactService("proj-test", "run-001", base_dir=temp_base_dir)

    file_path = service.write_run_summary(
        start_url="https://test.com/start",
        total_pages=10,
        successful_pages=9,
        failed_pages=1,
        start_time="2026-06-27T10:00:00Z",
        end_time="2026-06-27T10:05:00Z",
        duration_seconds=300.5,
    )

    assert file_path.exists()
    assert "run.yaml" in str(file_path)

    # Verify content
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["run_id"] == "run-001"
    assert data["project_id"] == "proj-test"
    assert data["start_url"] == "https://test.com/start"
    assert data["status"] == "completed"
    assert data["statistics"]["total_pages_discovered"] == 10
    assert data["statistics"]["successful_pages"] == 9
    assert data["statistics"]["failed_pages"] == 1
    assert data["statistics"]["success_rate"] == 90.0


def test_write_run_summary_with_error(temp_base_dir):
    """Test writing run summary with error"""
    service = ArtifactService("proj-test", "run-001", base_dir=temp_base_dir)

    file_path = service.write_run_summary(
        start_url="https://test.com/start",
        total_pages=5,
        successful_pages=0,
        failed_pages=5,
        start_time="2026-06-27T10:00:00Z",
        end_time="2026-06-27T10:02:00Z",
        duration_seconds=120.0,
        error="Authentication failed"
    )

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["status"] == "failed"
    assert data["error"] == "Authentication failed"


def test_write_exploration_graph(temp_base_dir):
    """Test writing graph.yaml"""
    service = ArtifactService("proj-test", "run-001", base_dir=temp_base_dir)

    edges = [
        {
            "from_page": "page-workspace-agents",
            "to_page": "page-agent-detail",
            "link_text": "View Details",
            "locator": "getByRole('link', { name: 'View Details' })"
        },
        {
            "from_page": "page-agent-detail",
            "to_page": "page-agent-settings",
            "link_text": "Settings",
            "locator": "getByRole('link', { name: 'Settings' })"
        }
    ]

    file_path = service.write_exploration_graph(edges)

    assert file_path.exists()
    assert "graph.yaml" in str(file_path)

    # Verify content
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["run_id"] == "run-001"
    assert len(data["edges"]) == 2
    assert data["edges"][0]["from_page"] == "page-workspace-agents"
    assert data["edges"][0]["to_page"] == "page-agent-detail"


def test_write_exploration_report(temp_base_dir):
    """Test writing report.md"""
    service = ArtifactService("proj-test", "run-001", base_dir=temp_base_dir)

    issues = ["Failed to load page /timeout", "Element not found on /broken"]
    recommendations = [
        "Increase timeout for slow pages",
        "Check element locators on /broken"
    ]

    file_path = service.write_exploration_report(
        start_url="https://test.com/start",
        pages_explored=10,
        elements_found=150,
        issues=issues,
        recommendations=recommendations,
    )

    assert file_path.exists()
    assert "report.md" in str(file_path)

    # Verify content
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "# Exploration Report" in content
    assert "run-001" in content
    assert "Pages Explored**: 10" in content
    assert "Elements Found**: 150" in content
    assert "Failed to load page /timeout" in content
    assert "Increase timeout for slow pages" in content


def test_create_logs_directory(temp_base_dir):
    """Test creating logs directory"""
    service = ArtifactService("proj-test", "run-001", base_dir=temp_base_dir)

    logs_dir = service.create_logs_directory()

    assert logs_dir.exists()
    assert logs_dir.is_dir()
    assert "logs" in str(logs_dir)


def test_create_screenshots_directory(temp_base_dir):
    """Test creating screenshots directory"""
    service = ArtifactService("proj-test", "run-001", base_dir=temp_base_dir)

    screenshots_dir = service.create_screenshots_directory()

    assert screenshots_dir.exists()
    assert screenshots_dir.is_dir()
    assert "screenshots" in str(screenshots_dir)


def test_multiple_runs_isolated(temp_base_dir):
    """Test that multiple runs create separate directories"""
    service1 = ArtifactService("proj-test", "run-001", base_dir=temp_base_dir)
    service2 = ArtifactService("proj-test", "run-002", base_dir=temp_base_dir)

    pages = [{"page_id": "test", "page_file": "test.yaml", "normalized_path": "/test",
              "status": "new", "elements_count": 1, "exploration_status": "completed"}]

    path1 = service1.write_discovered_pages(pages)
    path2 = service2.write_discovered_pages(pages)

    assert "run-001" in str(path1)
    assert "run-002" in str(path2)
    assert path1 != path2
