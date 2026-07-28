from pathlib import Path

import yaml

from app.services.page_exploration.loop.loop_artifact_merge_service import merge_loop_page_artifacts, merge_page_delta


def test_merge_page_delta_reports_duplicate_added_and_conflict() -> None:
    base = {
        "page": {"identity_key": "page-home"},
        "elements": [{"stable_key": "button-save", "role": "button"}],
    }
    duplicate, duplicate_summary = merge_page_delta(base, {"page": {"identity_key": "page-home"}, "elements": [{"stable_key": "button-save", "role": "button"}]})
    assert duplicate["elements"] == base["elements"]
    assert duplicate_summary["duplicate"] == 1

    updated, updated_summary = merge_page_delta(base, {"page": {"identity_key": "page-home"}, "elements": [{"stable_key": "button-save", "role": "button", "name": "Save"}]})
    assert updated["elements"][0]["name"] == "Save"
    assert updated_summary["updated"] == 1

    _, conflict_summary = merge_page_delta(base, {"page": {"identity_key": "page-home"}, "elements": [{"stable_key": "button-save", "role": "link"}]})
    assert conflict_summary["status"] == "conflict"
    assert conflict_summary["conflicts"]


def test_merge_loop_page_artifacts_keeps_conflict_file(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    baseline = tmp_path / "baseline"
    conflicts = tmp_path / "conflicts"
    pages.mkdir()
    baseline.mkdir()
    baseline_payload = {"page": {"identity_key": "page-home"}, "elements": [{"stable_key": "button-save", "role": "button"}]}
    delta_payload = {"page": {"identity_key": "page-home"}, "elements": [{"stable_key": "button-save", "role": "link"}]}
    (baseline / "home.yaml").write_text(yaml.safe_dump(baseline_payload), encoding="utf-8")
    (pages / "home.yaml").write_text(yaml.safe_dump(delta_payload), encoding="utf-8")

    summary = merge_loop_page_artifacts(pages_dir=pages, baseline_dir=baseline, conflicts_dir=conflicts, run_id="run-1")
    assert summary["status"] == "conflict"
    assert summary["conflict_count"] == 1
    assert (conflicts / "home.yaml").exists()
    assert yaml.safe_load((pages / "home.yaml").read_text(encoding="utf-8")) == delta_payload

