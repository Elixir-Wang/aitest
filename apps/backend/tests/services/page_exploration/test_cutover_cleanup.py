from pathlib import Path
import subprocess
import sys

import yaml
import pytest

from app.services.page_exploration.cutover_cleanup import (
    apply_legacy_cleanup_manifest,
    build_legacy_cleanup_manifest,
)


def _write_page(path: Path, schema_version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": schema_version,
                "page": {"id": path.stem, "normalized_path": "/" + path.stem},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_manifest_only_targets_legacy_files_and_preserves_schema4_and_runs(tmp_path: Path) -> None:
    exploration_root = tmp_path / "project-1" / "page_exploration"
    _write_page(exploration_root / "pages" / "legacy.yaml", "3.0")
    _write_page(exploration_root / "pages" / "current.yaml", "4.0")
    (exploration_root / "operations.yaml").write_text("legacy", encoding="utf-8")
    (exploration_root / "subgoals.yaml").write_text("legacy", encoding="utf-8")
    (exploration_root / "runs" / "run-1" / "trace.json").parent.mkdir(parents=True)
    (exploration_root / "runs" / "run-1" / "trace.json").write_text("keep", encoding="utf-8")

    manifest = build_legacy_cleanup_manifest(tmp_path)

    targets = {entry["path"] for project in manifest["projects"] for entry in project["delete"]}
    assert targets == {
        "project-1/page_exploration/operations.yaml",
        "project-1/page_exploration/subgoals.yaml",
        "project-1/page_exploration/pages/legacy.yaml",
    }
    assert "project-1/page_exploration/pages/current.yaml" in {
        entry["path"] for project in manifest["projects"] for entry in project["preserve"]
    }
    assert "project-1/page_exploration/runs/run-1/trace.json" in {
        entry["path"] for project in manifest["projects"] for entry in project["preserve"]
    }
    assert (exploration_root / "operations.yaml").exists()


def test_apply_requires_unchanged_manifest_and_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "project-1" / "page_exploration" / "operations.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("legacy", encoding="utf-8")

    manifest = build_legacy_cleanup_manifest(tmp_path)
    result = apply_legacy_cleanup_manifest(tmp_path, manifest)

    assert result["deleted"] == ["project-1/page_exploration/operations.yaml"]
    assert not target.exists()
    assert apply_legacy_cleanup_manifest(tmp_path, manifest)["skipped"] == [
        "project-1/page_exploration/operations.yaml"
    ]


def test_apply_rejects_changed_target_and_path_escape(tmp_path: Path) -> None:
    target = tmp_path / "project-1" / "page_exploration" / "operations.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("legacy", encoding="utf-8")
    manifest = build_legacy_cleanup_manifest(tmp_path)
    target.write_text("changed", encoding="utf-8")

    with pytest.raises(ValueError, match="manifest fingerprint changed"):
        apply_legacy_cleanup_manifest(tmp_path, manifest)

    manifest["projects"][0]["delete"][0]["path"] = "../outside.txt"
    with pytest.raises(ValueError, match="path escapes storage root"):
        apply_legacy_cleanup_manifest(tmp_path, manifest)


def test_cleanup_cli_can_run_directly() -> None:
    backend_root = Path(__file__).parents[3]
    result = subprocess.run(
        [sys.executable, "scripts/cleanup_page_exploration_legacy_artifacts.py", "--help"],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--manifest" in result.stdout
