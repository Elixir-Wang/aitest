from pathlib import Path

import pytest

from app.agents.api_automation.pytest_requests.suite import (
    REQUIRED_SUITE_FILES,
    endpoint_artifact_paths,
    ensure_suite_root,
    suite_is_initialized,
    suite_missing_files,
)


def test_incomplete_suite_is_not_identified_by_pytest_ini_alone(tmp_path: Path) -> None:
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    assert suite_is_initialized(tmp_path) is False
    assert "utils/data_loader.py" in suite_missing_files(tmp_path)


def test_complete_suite_is_initialized(tmp_path: Path) -> None:
    for relative_path in REQUIRED_SUITE_FILES:
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")

    assert suite_is_initialized(tmp_path) is True
    assert suite_missing_files(tmp_path) == []


def test_ensure_suite_root_creates_only_root_and_agent_state(tmp_path: Path) -> None:
    suite_path = ensure_suite_root(tmp_path / "pytest_requests")

    assert suite_path == (tmp_path / "pytest_requests").resolve()
    assert (suite_path / ".deepagents").is_dir()
    assert suite_is_initialized(suite_path) is False


def test_endpoint_artifact_paths_use_full_normalized_path_and_method() -> None:
    endpoint_dir, test_file, data_file = endpoint_artifact_paths(
        {
            "id": "apiend-1",
            "method": "POST",
            "path": "/ignored/path/",
            "normalized_path": "/openapi/v1/agent/analysis/",
        }
    )

    assert endpoint_dir == "testcases/openapi/v1/agent/analysis/post"
    assert test_file == "testcases/openapi/v1/agent/analysis/post/test_api.py"
    assert data_file == "testcases/openapi/v1/agent/analysis/post/cases.yaml"


def test_endpoint_artifact_paths_separate_methods_on_same_path() -> None:
    get_dir, _, _ = endpoint_artifact_paths({"method": "GET", "path": "/users"})
    post_dir, _, _ = endpoint_artifact_paths({"method": "POST", "path": "/users"})

    assert get_dir == "testcases/users/get"
    assert post_dir == "testcases/users/post"


def test_endpoint_artifact_paths_convert_path_parameters() -> None:
    endpoint_dir, test_file, data_file = endpoint_artifact_paths(
        {"method": "GET", "path": "/organizations/{org_id}/users/{user_id}"}
    )

    assert endpoint_dir == "testcases/organizations/by_org_id/users/by_user_id/get"
    assert test_file == f"{endpoint_dir}/test_api.py"
    assert data_file == f"{endpoint_dir}/cases.yaml"


def test_endpoint_artifact_paths_support_root_path() -> None:
    endpoint_dir, test_file, data_file = endpoint_artifact_paths({"method": "GET", "path": "/"})

    assert endpoint_dir == "testcases/root/get"
    assert test_file == "testcases/root/get/test_api.py"
    assert data_file == "testcases/root/get/cases.yaml"


@pytest.mark.parametrize(
    "endpoint",
    [
        {"method": "CONNECT", "path": "/users"},
        {"method": "GET", "path": "/../users"},
        {"method": "GET", "path": "/users/{}/detail"},
    ],
)
def test_endpoint_artifact_paths_reject_invalid_inputs(endpoint: dict) -> None:
    with pytest.raises(ValueError):
        endpoint_artifact_paths(endpoint)
