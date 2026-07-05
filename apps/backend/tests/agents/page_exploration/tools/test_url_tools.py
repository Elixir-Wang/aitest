"""Tests for url_tools"""
import pytest
from pathlib import Path

from app.agents.page_exploration.tools.url_tools import check_explored_url


def test_unexplored_url(tmp_path: Path):
    result = check_explored_url(
        normalized_path="/workspace",
        project_id="proj-x",
        base_dir=tmp_path,
    )
    assert result == {"explored": False, "has_state_tree": False}


def test_old_yaml_no_state_tree(tmp_path: Path):
    project_dir = tmp_path / "proj-x"
    project_dir.mkdir()
    page_yaml = project_dir / "page_exploration" / "pages" / "page-x.yaml"
    page_yaml.parent.mkdir(parents=True, exist_ok=True)
    page_yaml.write_text(
        "page:\n  id: page-x\n"
        "states: []\n",
        encoding="utf-8"
    )
    result = check_explored_url(
        normalized_path="/workspace",
        project_id="proj-x",
        base_dir=tmp_path,
    )
    assert result == {"explored": False, "has_state_tree": False}


def test_v2_yaml_has_state_tree(tmp_path: Path):
    project_dir = tmp_path / "proj-x"
    project_dir.mkdir()
    page_yaml = project_dir / "page_exploration" / "pages" / "page-x.yaml"
    page_yaml.parent.mkdir(parents=True, exist_ok=True)
    page_yaml.write_text(
        "schema_version: \"2.0\"\n"
        "page:\n  id: page-x\n  title: x\n  normalized_path: /x\n"
        "  observed_url: /x\n  first_observed_at: 2026-07-04T10:00:00Z\n"
        "  last_observed_at: 2026-07-04T10:00:00Z\n  observed_by_runs: [r1]\n"
        "states: []\n",
        encoding="utf-8"
    )
    result = check_explored_url(
        normalized_path="/x",
        project_id="proj-x",
        base_dir=tmp_path,
    )
    assert result["explored"] is True
    assert result["has_state_tree"] is True


def test_v2_yaml_for_different_path_does_not_mark_current_url_explored(tmp_path: Path):
    project_dir = tmp_path / "proj-x"
    project_dir.mkdir()
    page_yaml = project_dir / "page_exploration" / "pages" / "page-x.yaml"
    page_yaml.parent.mkdir(parents=True, exist_ok=True)
    page_yaml.write_text(
        "schema_version: \"2.0\"\n"
        "page:\n  id: page-x\n  title: x\n  normalized_path: /x\n"
        "  observed_url: /x\n  first_observed_at: 2026-07-04T10:00:00Z\n"
        "  last_observed_at: 2026-07-04T10:00:00Z\n  observed_by_runs: [r1]\n"
        "states: []\n",
        encoding="utf-8"
    )
    result = check_explored_url(
        normalized_path="/workspace",
        project_id="proj-x",
        base_dir=tmp_path,
    )
    assert result == {"explored": False, "has_state_tree": False}
