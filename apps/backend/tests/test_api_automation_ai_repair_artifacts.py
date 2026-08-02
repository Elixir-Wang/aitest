from pathlib import Path

from app.core import settings
from app.services.api_automation.self_healing_artifacts import (
    build_manifest,
    create_attempt_workspace,
    create_revision_snapshot,
)


def test_manifest_hashes_source_and_ignores_runtime_files(tmp_path: Path) -> None:
    suite = tmp_path / "suite"
    (suite / "testcases").mkdir(parents=True)
    (suite / "testcases" / "test_api.py").write_text("assert True\n", encoding="utf-8")
    (suite / ".pytest_cache").mkdir()
    (suite / ".pytest_cache" / "state").write_text("ignored", encoding="utf-8")
    (suite / "report.json").write_text("{}", encoding="utf-8")

    manifest = build_manifest(suite)

    assert list(manifest) == ["testcases/test_api.py"]
    assert manifest["testcases/test_api.py"]["size"] == len(b"assert True\n")
    assert len(manifest["testcases/test_api.py"]["sha256"]) == 64


def test_attempt_workspace_and_revision_copy_suite(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    workspace = create_attempt_workspace("project-1", "session-1", 1, suite)
    revision = create_revision_snapshot("project-1", "session-1", 0, suite)

    assert (workspace / "pytest.ini").read_text(encoding="utf-8") == "[pytest]\n"
    assert (revision / "pytest.ini").read_text(encoding="utf-8") == "[pytest]\n"
