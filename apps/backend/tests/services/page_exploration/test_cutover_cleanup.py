from pathlib import Path

from app.services.page_exploration.cutover_cleanup import clear_legacy_exploration_artifacts


def test_clear_legacy_exploration_artifacts_deletes_only_exploration_outputs(tmp_path: Path) -> None:
    project_root = tmp_path / "project-1"
    exploration_root = project_root / "page_exploration"
    for directory in ("pages", "runs"):
        target = exploration_root / directory
        target.mkdir(parents=True, exist_ok=True)
        (target / "artifact.yaml").write_text("legacy", encoding="utf-8")
    for name in (
        "page_edges.yaml",
        "operations.yaml",
        "operations.yaml.lock",
        "subgoals.yaml",
        "exploration-coverage.yaml",
    ):
        (exploration_root / name).write_text("legacy", encoding="utf-8")
    (exploration_root / "project-settings.yaml").write_text("keep", encoding="utf-8")
    (project_root / "environment.yaml").write_text("keep", encoding="utf-8")
    (project_root / "auth-state.json").write_text("keep", encoding="utf-8")

    result = clear_legacy_exploration_artifacts(tmp_path, "project-1")

    assert set(result["deleted"]) == {
        "pages",
        "runs",
        "page_edges.yaml",
        "operations.yaml",
        "operations.yaml.lock",
        "subgoals.yaml",
        "exploration-coverage.yaml",
    }
    assert (exploration_root / "project-settings.yaml").read_text(encoding="utf-8") == "keep"
    assert (project_root / "environment.yaml").read_text(encoding="utf-8") == "keep"
    assert (project_root / "auth-state.json").read_text(encoding="utf-8") == "keep"


def test_clear_legacy_exploration_artifacts_is_idempotent(tmp_path: Path) -> None:
    result = clear_legacy_exploration_artifacts(tmp_path, "project-1")

    assert result == {"deleted": [], "missing": 7}
