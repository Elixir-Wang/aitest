"""Tests for ExploredUrlsService"""

import pytest
from pathlib import Path
from datetime import datetime
import yaml

from app.agents.page_exploration.services.explored_urls_service import ExploredUrlsService


@pytest.fixture
def temp_base_dir(tmp_path):
    """Temp directory for isolated file system testing"""
    return tmp_path


def test_check_not_explored_yet(temp_base_dir):
    """File doesn't exist - should return explored: False"""
    service = ExploredUrlsService("proj-test", base_dir=temp_base_dir)
    result = service.check("/workspace/agents")
    assert result == {"explored": False}


def test_check_already_explored(temp_base_dir):
    """URL found in existing file - should return full record"""
    # Setup: create file with one explored URL
    project_dir = temp_base_dir / "proj-test" / "page_exploration"
    project_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "1.0",
        "project_id": "proj-test",
        "urls": [
            {
                "normalized_path": "/workspace/agents",
                "page_id": "page-001",
                "page_file": "pages/page-001.yaml",
                "last_explored_at": "2026-06-27T10:00:00Z",
                "last_run_id": "run-001"
            }
        ]
    }

    with open(project_dir / "explored_urls.yaml", "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    # Test
    service = ExploredUrlsService("proj-test", base_dir=temp_base_dir)
    result = service.check("/workspace/agents")

    assert result == {
        "explored": True,
        "page_id": "page-001",
        "page_file": "pages/page-001.yaml",
        "last_explored_at": "2026-06-27T10:00:00Z",
        "last_run_id": "run-001"
    }


def test_check_not_found_in_existing_file(temp_base_dir):
    """File exists but URL not in it - should return explored: False"""
    # Setup: create file with different URL
    project_dir = temp_base_dir / "proj-test" / "page_exploration"
    project_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "1.0",
        "project_id": "proj-test",
        "urls": [
            {
                "normalized_path": "/other/path",
                "page_id": "page-002",
                "page_file": "pages/page-002.yaml",
                "last_explored_at": "2026-06-27T10:00:00Z",
                "last_run_id": "run-002"
            }
        ]
    }

    with open(project_dir / "explored_urls.yaml", "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    # Test
    service = ExploredUrlsService("proj-test", base_dir=temp_base_dir)
    result = service.check("/workspace/agents")

    assert result == {"explored": False}


def test_update_new_url(temp_base_dir):
    """First time update - should create file and add record"""
    service = ExploredUrlsService("proj-test", base_dir=temp_base_dir)

    # Update
    service.update("/workspace/agents", "page-001", "run-001")

    # Verify file was created
    yaml_path = temp_base_dir / "proj-test" / "page_exploration" / "explored_urls.yaml"
    assert yaml_path.exists()

    # Verify content
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["version"] == "1.0"
    assert data["project_id"] == "proj-test"
    assert len(data["urls"]) == 1

    url_record = data["urls"][0]
    assert url_record["normalized_path"] == "/workspace/agents"
    assert url_record["page_id"] == "page-001"
    assert url_record["page_file"] == "pages/page-001.yaml"
    assert url_record["last_run_id"] == "run-001"

    # Check timestamp format (ISO format with Z)
    timestamp = url_record["last_explored_at"]
    assert timestamp.endswith("Z")
    # Verify it's a valid datetime
    datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def test_update_existing_url(temp_base_dir):
    """Update existing URL - should overwrite with new run_id and timestamp"""
    # Setup: create file with one URL
    project_dir = temp_base_dir / "proj-test" / "page_exploration"
    project_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "1.0",
        "project_id": "proj-test",
        "urls": [
            {
                "normalized_path": "/workspace/agents",
                "page_id": "page-001",
                "page_file": "pages/page-001.yaml",
                "last_explored_at": "2026-06-27T10:00:00Z",
                "last_run_id": "run-001"
            }
        ]
    }

    with open(project_dir / "explored_urls.yaml", "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    # Update with new run_id
    service = ExploredUrlsService("proj-test", base_dir=temp_base_dir)
    service.update("/workspace/agents", "page-001", "run-002")

    # Verify content was updated
    with open(project_dir / "explored_urls.yaml", "r", encoding="utf-8") as f:
        updated_data = yaml.safe_load(f)

    assert len(updated_data["urls"]) == 1
    url_record = updated_data["urls"][0]
    assert url_record["last_run_id"] == "run-002"
    assert url_record["last_explored_at"] != "2026-06-27T10:00:00Z"  # Should be updated
    assert url_record["page_id"] == "page-001"


def test_update_adds_second_url(temp_base_dir):
    """Update with different URL - should add new record, not replace"""
    # Setup: create file with one URL
    project_dir = temp_base_dir / "proj-test" / "page_exploration"
    project_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "1.0",
        "project_id": "proj-test",
        "urls": [
            {
                "normalized_path": "/workspace/agents",
                "page_id": "page-001",
                "page_file": "pages/page-001.yaml",
                "last_explored_at": "2026-06-27T10:00:00Z",
                "last_run_id": "run-001"
            }
        ]
    }

    with open(project_dir / "explored_urls.yaml", "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    # Update with different URL
    service = ExploredUrlsService("proj-test", base_dir=temp_base_dir)
    service.update("/workspace/settings", "page-002", "run-002")

    # Verify both URLs exist
    with open(project_dir / "explored_urls.yaml", "r", encoding="utf-8") as f:
        updated_data = yaml.safe_load(f)

    assert len(updated_data["urls"]) == 2
    paths = [u["normalized_path"] for u in updated_data["urls"]]
    assert "/workspace/agents" in paths
    assert "/workspace/settings" in paths
