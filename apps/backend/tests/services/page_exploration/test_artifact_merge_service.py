from pathlib import Path

import yaml

from app.services.page_exploration.artifact_merge_service import (
    capture_page_baseline,
    merge_goal_run_artifacts,
    merge_page_delta,
)


def test_merge_page_delta_preserves_baseline_and_adds_new_facts() -> None:
    base = {
        "schema_version": "4.0",
        "page": {"id": "page-workspace"},
        "elements": [{"key": "button-create", "name": "创建"}],
    }
    delta = {
        "run_id": "run-goal-1",
        "schema_version": "4.0",
        "page": {"id": "page-workspace"},
        "elements": [{"key": "button-import", "name": "批量导入"}],
    }

    merged, summary = merge_page_delta(base, delta)

    assert summary["status"] == "merged"
    assert summary["added"] == 1
    assert [item["key"] for item in merged["elements"]] == ["button-create", "button-import"]
    assert "merge_history" not in merged


def test_merge_page_delta_reports_conflict_without_overwriting_baseline() -> None:
    base = {
        "schema_version": "4.0",
        "page": {"id": "page-workspace"},
        "elements": [{"key": "button-create", "role": "button", "name": "创建"}],
    }
    delta = {
        "schema_version": "4.0",
        "page": {"id": "page-workspace"},
        "elements": [{"key": "button-create", "role": "link", "name": "创建"}],
    }

    merged, summary = merge_page_delta(base, delta)

    assert summary["status"] == "conflict"
    assert summary["conflicts"][0]["reason"] == "fact_conflict"
    assert merged["elements"][0]["role"] == "button"


def test_goal_run_captures_baseline_and_merges_current_page(tmp_path: Path) -> None:
    pages_dir = tmp_path / "project-1" / "page_exploration" / "pages"
    pages_dir.mkdir(parents=True)
    baseline = {
        "schema_version": "4.0",
        "page": {"id": "page-workspace"},
        "elements": [{"key": "button-create", "name": "创建"}],
    }
    (pages_dir / "page-workspace.yaml").write_text(yaml.safe_dump(baseline), encoding="utf-8")

    capture_page_baseline(tmp_path, "project-1", "run-1")
    current = {
        "schema_version": "4.0",
        "page": {"id": "page-workspace"},
        "elements": [{"key": "button-import", "name": "批量导入"}],
    }
    (pages_dir / "page-workspace.yaml").write_text(yaml.safe_dump(current), encoding="utf-8")

    summary = merge_goal_run_artifacts(tmp_path, "project-1", "run-1")
    merged = yaml.safe_load((pages_dir / "page-workspace.yaml").read_text(encoding="utf-8"))

    assert summary["status"] == "merged"
    assert {item["key"] for item in merged["elements"]} == {"button-create", "button-import"}
