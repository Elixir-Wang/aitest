"""Tests for artifact tools"""
import pytest
from pathlib import Path
import yaml

from app.agents.page_exploration.tools.artifact_tools import (
    read_page_artifact,
    merge_page_artifact,
)


def _write_existing(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_read_non_existent(tmp_path):
    r = read_page_artifact(
        page_id="page-x",
        project_id="proj-x",
        base_dir=tmp_path,
    )
    assert r["exists"] is False
    assert r["page"] is None


def test_read_existing(tmp_path):
    project_dir = tmp_path / "proj-x"
    project_dir.mkdir()
    page_yaml = project_dir / "pages" / "page-x.yaml"
    _write_existing(page_yaml, {
        "schema_version": "2.0",
        "page": {"id":"page-x","title":"x","normalized_path":"/x","observed_url":"/x",
                 "first_observed_at":"2026-07-04T10:00:00Z",
                 "last_observed_at":"2026-07-04T10:00:00Z","observed_by_runs":["r1"]},
        "states": [],
    })
    r = read_page_artifact(page_id="page-x", project_id="proj-x", base_dir=tmp_path)
    assert r["exists"] is True
    assert r["schema_version"] == "2.0"


def test_merge_root_state_creates_new_file(tmp_path):
    r = merge_page_artifact(
        page_id="page-x",
        project_id="proj-x",
        run_id="r1",
        base_dir=tmp_path,
        observed_states=[{
            "page_id": "page-x", "page_title": "x", "normalized_path": "/x",
            "observed_url": "/x", "run_id": "r1",
            "observed_at": "2026-07-04T10:00:00Z",
            "state_type": "root", "title": "r",
            "dom_signature": "sha256:t", "triggered_by": None,
            "parent_state_id": None, "elements": [],
        }],
    )
    assert r["skipped_due_to_lock"] is False
    assert any(s.endswith("__root__001") for s in r["added_state_ids"])
