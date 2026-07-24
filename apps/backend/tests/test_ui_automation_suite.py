from pathlib import Path

import pytest

from app.agents.ui_automation.pytest_playwright.suite import (
    case_artifact_paths,
    project_suite_path,
    resolve_suite_file,
)


def test_business_projects_use_isolated_suites(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.agents.ui_automation.pytest_playwright.suite.settings.PROJECT_FILE_STORAGE_ROOT",
        tmp_path,
    )

    assert project_suite_path("project-1") == tmp_path / "project-1/ui_automation/pytest_playwright"
    assert project_suite_path("project-2") == tmp_path / "project-2/ui_automation/pytest_playwright"
    assert project_suite_path("project-1") != project_suite_path("project-2")


def test_resolve_suite_file_rejects_directory_escape(tmp_path):
    suite_path = tmp_path / "suite"

    with pytest.raises(ValueError, match="工程目录"):
        resolve_suite_file(suite_path, "../outside.py")


def test_case_artifact_paths_are_backend_owned(tmp_path):
    paths = case_artifact_paths(
        tmp_path,
        project_id="project-1",
        automation_case_id="uiauto-123",
        source_test_case_id="case-456",
        title="正确账号登录",
    )

    assert paths["test_file"].relative_to(tmp_path).as_posix().startswith("testcases/generated/project_1/")
    assert paths["data_file"].relative_to(tmp_path).as_posix().startswith("data/projects/project_1/cases/")
    assert paths["plan_file"].name.endswith(".plan.json")
    assert paths["test_file"].name.startswith("test_")
