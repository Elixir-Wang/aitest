"""Tests for explored URLs tools"""

import pytest
from pathlib import Path
import yaml

from app.agents.page_exploration.tools.explored_urls_tools import (
    check_explored_url_tool,
    update_explored_url_tool,
)


@pytest.fixture
def temp_base_dir(tmp_path, monkeypatch):
    """Setup temp directory and patch base path"""
    # Patch Path to use temp directory
    monkeypatch.setattr(
        'app.agents.page_exploration.services.explored_urls_service.Path',
        lambda x: tmp_path if x == "data/projects" else Path(x)
    )
    return tmp_path


def test_check_explored_url_tool_not_explored(temp_base_dir):
    """Test checking a URL that hasn't been explored"""
    result = check_explored_url_tool.invoke({
        "url": "https://test.example.com/workspace/agents",
        "project_id": "proj-test"
    })

    assert result["explored"] is False
    assert result["normalized_path"] == "/workspace/agents"


def test_check_explored_url_tool_already_explored(temp_base_dir):
    """Test checking a URL that has been explored"""
    # Setup: create explored_urls.yaml
    project_dir = temp_base_dir / "proj-test" / "page_exploration"
    project_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "1.0",
        "project_id": "proj-test",
        "urls": [
            {
                "normalized_path": "/workspace/agents",
                "page_id": "page-workspace-agents",
                "page_file": "pages/page-workspace-agents.yaml",
                "last_explored_at": "2026-06-27T10:00:00Z",
                "last_run_id": "run-001"
            }
        ]
    }

    with open(project_dir / "explored_urls.yaml", "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    # Test
    result = check_explored_url_tool.invoke({
        "url": "https://test.example.com/workspace/agents",
        "project_id": "proj-test"
    })

    assert result["explored"] is True
    assert result["page_id"] == "page-workspace-agents"
    assert result["page_file"] == "pages/page-workspace-agents.yaml"
    assert result["last_explored_at"] == "2026-06-27T10:00:00Z"
    assert result["last_run_id"] == "run-001"
    assert result["normalized_path"] == "/workspace/agents"


def test_check_explored_url_tool_cross_environment(temp_base_dir):
    """Test URL normalization works across environments"""
    # Setup
    project_dir = temp_base_dir / "proj-test" / "page_exploration"
    project_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "1.0",
        "project_id": "proj-test",
        "urls": [
            {
                "normalized_path": "/workspace/agents",
                "page_id": "page-workspace-agents",
                "page_file": "pages/page-workspace-agents.yaml",
                "last_explored_at": "2026-06-27T10:00:00Z",
                "last_run_id": "run-001"
            }
        ]
    }

    with open(project_dir / "explored_urls.yaml", "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    # Test with different environment URLs
    test_urls = [
        "https://test.example.com/workspace/agents",
        "https://prod.example.com/workspace/agents",
        "https://local.example.com/workspace/agents?tab=all",
        "https://dev.example.com/workspace/agents/",
    ]

    for url in test_urls:
        result = check_explored_url_tool.invoke({
            "url": url,
            "project_id": "proj-test"
        })
        assert result["explored"] is True, f"Failed for URL: {url}"
        assert result["page_id"] == "page-workspace-agents"


def test_update_explored_url_tool_new(temp_base_dir):
    """Test updating a new URL"""
    result = update_explored_url_tool.invoke({
        "url": "https://test.example.com/workspace/agents",
        "page_id": "page-workspace-agents",
        "project_id": "proj-test",
        "run_id": "run-001"
    })

    assert result["success"] is True
    assert result["normalized_path"] == "/workspace/agents"
    assert result["page_id"] == "page-workspace-agents"
    assert result["run_id"] == "run-001"

    # Verify file was created
    yaml_path = temp_base_dir / "proj-test" / "page_exploration" / "explored_urls.yaml"
    assert yaml_path.exists()

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["project_id"] == "proj-test"
    assert len(data["urls"]) == 1
    assert data["urls"][0]["normalized_path"] == "/workspace/agents"
    assert data["urls"][0]["page_id"] == "page-workspace-agents"


def test_update_explored_url_tool_update_existing(temp_base_dir):
    """Test updating an existing URL"""
    # Setup: create initial file
    project_dir = temp_base_dir / "proj-test" / "page_exploration"
    project_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "1.0",
        "project_id": "proj-test",
        "urls": [
            {
                "normalized_path": "/workspace/agents",
                "page_id": "page-workspace-agents",
                "page_file": "pages/page-workspace-agents.yaml",
                "last_explored_at": "2026-06-27T10:00:00Z",
                "last_run_id": "run-001"
            }
        ]
    }

    with open(project_dir / "explored_urls.yaml", "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    # Update with new run_id
    result = update_explored_url_tool.invoke({
        "url": "https://test.example.com/workspace/agents",
        "page_id": "page-workspace-agents",
        "project_id": "proj-test",
        "run_id": "run-002"
    })

    assert result["success"] is True
    assert result["run_id"] == "run-002"

    # Verify file was updated
    with open(project_dir / "explored_urls.yaml", "r", encoding="utf-8") as f:
        updated_data = yaml.safe_load(f)

    assert len(updated_data["urls"]) == 1
    assert updated_data["urls"][0]["last_run_id"] == "run-002"
    assert updated_data["urls"][0]["last_explored_at"] != "2026-06-27T10:00:00Z"
