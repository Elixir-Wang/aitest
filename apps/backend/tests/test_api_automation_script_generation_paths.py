from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException

from app.services.api_automation import service


def _endpoint(endpoint_id: str = "apiend-1", *, method: str = "POST", path: str = "/openapi/v1/agent/analysis/") -> dict:
    return {
        "id": endpoint_id,
        "method": method,
        "path": path,
        "normalized_path": path,
    }


def test_pytest_requests_skill_requires_oracle_observation_protocol() -> None:
    skill_text = Path(
        "app/agents/api_automation/pytest_requests/skills/pytest-requests-code-generation/SKILL.md"
    ).read_text(encoding="utf-8")

    assert "API_OBSERVATION_RESULT_PATH" in skill_text
    assert "`inferred` 和 `needs_confirmation`" in skill_text
    assert "msvcrt" in skill_text
    assert "fcntl" in skill_text
    assert "原子替换" in skill_text
    assert "递归脱敏" in skill_text


def test_prepare_endpoint_generation_uses_canonical_artifact_manifest(tmp_path: Path) -> None:
    payload, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])

    expected_dir = "testcases/openapi/v1/agent/analysis/post"
    assert payload[0]["artifacts"] == {
        "directory": expected_dir,
        "test_file": f"{expected_dir}/test_api.py",
        "data_file": f"{expected_dir}/cases.yaml",
    }
    assert artifacts["apiend-1"]["test_file_path"] == tmp_path / expected_dir / "test_api.py"
    assert artifacts["apiend-1"]["data_file_path"] == tmp_path / expected_dir / "cases.yaml"
    assert artifacts["apiend-1"]["script_name"] == "POST /openapi/v1/agent/analysis/"


def test_prepare_endpoint_generation_separates_shared_prefix_endpoints(tmp_path: Path) -> None:
    payload, artifacts = service._prepare_endpoint_generation(
        tmp_path,
        [
            _endpoint("apiend-analysis", path="/openapi/v1/agent/analysis/"),
            _endpoint("apiend-list", method="GET", path="/openapi/v1/agent/list/"),
        ],
    )

    assert len(payload) == 2
    assert artifacts["apiend-analysis"]["test_file_path"] != artifacts["apiend-list"]["test_file_path"]


def test_validate_generated_endpoint_artifacts_rejects_missing_test_file(tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    artifacts["apiend-1"]["data_file_path"].parent.mkdir(parents=True)
    artifacts["apiend-1"]["data_file_path"].write_text("[]\n", encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        service._validate_generated_endpoint_artifacts(tmp_path, artifacts)

    assert exc_info.value.detail["code"] == "API_SCRIPT_ARTIFACT_MISSING"
    assert "testcases/openapi/v1/agent/analysis/post/test_api.py" in exc_info.value.detail["message"]


def test_validate_generated_endpoint_artifacts_rejects_missing_data_file(tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    artifacts["apiend-1"]["test_file_path"].parent.mkdir(parents=True)
    artifacts["apiend-1"]["test_file_path"].write_text("def test_api():\n    pass\n", encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        service._validate_generated_endpoint_artifacts(tmp_path, artifacts)

    assert exc_info.value.detail["code"] == "API_SCRIPT_ARTIFACT_MISSING"
    assert "testcases/openapi/v1/agent/analysis/post/cases.yaml" in exc_info.value.detail["message"]


def test_validate_generated_endpoint_artifacts_accepts_exact_files(tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    artifact = artifacts["apiend-1"]
    artifact["test_file_path"].parent.mkdir(parents=True)
    artifact["test_file_path"].write_text("def test_api():\n    pass\n", encoding="utf-8")
    artifact["data_file_path"].write_text(
        yaml.safe_dump([{"id": "case-1", "endpoint_id": "apiend-1"}]),
        encoding="utf-8",
    )

    service._validate_generated_endpoint_artifacts(tmp_path, artifacts)


def test_validate_generated_endpoint_artifacts_requires_observation_for_uncertain_oracle(tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    artifact = artifacts["apiend-1"]
    artifact["test_file_path"].parent.mkdir(parents=True)
    artifact["test_file_path"].write_text(
        "def test_api():\n    pass\n",
        encoding="utf-8",
    )
    artifact["data_file_path"].write_text(
        yaml.safe_dump(
            [
                {
                    "id": "case-1",
                    "endpoint_id": "apiend-1",
                    "oracle_status": "needs_confirmation",
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(HTTPException) as exc_info:
        service._validate_generated_endpoint_artifacts(tmp_path, artifacts)

    assert exc_info.value.detail["code"] == "API_SCRIPT_ORACLE_OBSERVATION_MISSING"


def test_write_canonical_endpoint_data_replaces_agent_output_with_exact_database_snapshot(tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    artifact = artifacts["apiend-1"]
    artifact["data_file_path"].parent.mkdir(parents=True)
    artifact["data_file_path"].write_text(
        yaml.safe_dump({"cases": [{"case_id": "case-1"}, {"case_id": "case-1"}]}),
        encoding="utf-8",
    )
    expected_cases = [
        {"id": "case-1", "endpoint_id": "apiend-1", "title": "first"},
        {"id": "case-2", "endpoint_id": "apiend-1", "title": "second"},
    ]

    service._write_canonical_endpoint_data(artifacts, {"apiend-1": expected_cases})

    assert yaml.safe_load(artifact["data_file_path"].read_text(encoding="utf-8")) == [
        {**expected_cases[0], "case_id": "case-1"},
        {**expected_cases[1], "case_id": "case-2"},
    ]


def test_restore_endpoint_artifacts_rolls_back_existing_and_new_files(tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    artifact = artifacts["apiend-1"]
    artifact["test_file_path"].parent.mkdir(parents=True)
    artifact["test_file_path"].write_text("original test\n", encoding="utf-8")
    snapshot = service._snapshot_endpoint_artifacts(artifacts)

    artifact["test_file_path"].write_text("broken test\n", encoding="utf-8")
    artifact["data_file_path"].write_text("broken data\n", encoding="utf-8")
    service._restore_endpoint_artifacts(snapshot)

    assert artifact["test_file_path"].read_text(encoding="utf-8") == "original test\n"
    assert not artifact["data_file_path"].exists()


def test_validate_generated_endpoint_artifacts_rejects_wrong_endpoint_data(tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    artifact = artifacts["apiend-1"]
    artifact["test_file_path"].parent.mkdir(parents=True)
    artifact["test_file_path"].write_text("def test_api():\n    pass\n", encoding="utf-8")
    artifact["data_file_path"].write_text(
        yaml.safe_dump([{"id": "case-1", "endpoint_id": "apiend-2"}]),
        encoding="utf-8",
    )

    with pytest.raises(HTTPException) as exc_info:
        service._validate_generated_endpoint_artifacts(tmp_path, artifacts)

    assert exc_info.value.detail["code"] == "API_SCRIPT_ARTIFACT_ENDPOINT_MISMATCH"


def test_validate_generated_endpoint_artifacts_rejects_wrong_case_set(tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    artifact = artifacts["apiend-1"]
    artifact["expected_case_ids"] = ["case-1", "case-2"]
    artifact["test_file_path"].parent.mkdir(parents=True)
    artifact["test_file_path"].write_text("def test_api():\n    pass\n", encoding="utf-8")
    artifact["data_file_path"].write_text(
        yaml.safe_dump([{"id": "case-1", "endpoint_id": "apiend-1"}]),
        encoding="utf-8",
    )

    with pytest.raises(HTTPException) as exc_info:
        service._validate_generated_endpoint_artifacts(tmp_path, artifacts)

    assert exc_info.value.detail["code"] == "API_SCRIPT_ARTIFACT_CASE_MISMATCH"


def test_validate_generated_endpoint_artifacts_rejects_path_outside_suite(tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    artifacts["apiend-1"]["test_file_path"] = tmp_path.parent / "outside.py"

    with pytest.raises(HTTPException) as exc_info:
        service._validate_generated_endpoint_artifacts(tmp_path, artifacts)

    assert exc_info.value.detail["code"] == "API_SCRIPT_ARTIFACT_PATH_INVALID"


def test_script_artifacts_are_not_current_for_legacy_paths(tmp_path: Path) -> None:
    legacy_test = tmp_path / "testcases" / "v1" / "agent" / "test_agent.py"
    legacy_data = tmp_path / "testcases" / "v1" / "agent" / "test_agent.yaml"
    legacy_test.parent.mkdir(parents=True)
    legacy_test.write_text("def test_api():\n    pass\n", encoding="utf-8")
    legacy_data.write_text("[]\n", encoding="utf-8")

    assert service._script_artifacts_are_current(
        {
            "test_file_path": str(legacy_test),
            "data_file_path": str(legacy_data),
        },
        tmp_path,
        _endpoint(),
    ) is False


def test_script_artifacts_are_current_only_when_canonical_files_exist(tmp_path: Path) -> None:
    payload, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    artifact = artifacts["apiend-1"]
    existing = {
        "test_file_path": str(artifact["test_file_path"]),
        "data_file_path": str(artifact["data_file_path"]),
    }

    assert payload[0]["artifacts"]["test_file"].endswith("/test_api.py")
    assert service._script_artifacts_are_current(existing, tmp_path, _endpoint()) is False

    artifact["test_file_path"].parent.mkdir(parents=True)
    artifact["test_file_path"].write_text("def test_api():\n    pass\n", encoding="utf-8")
    artifact["data_file_path"].write_text("[]\n", encoding="utf-8")

    assert service._script_artifacts_are_current(existing, tmp_path, _endpoint()) is True


def test_collect_generated_suite_collects_changed_files_then_whole_suite(monkeypatch, tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    calls = []

    def fake_collect_script_suite(*, suite_path, timeout, test_paths=None):
        calls.append((suite_path, timeout, test_paths))
        return {"ok": True, "exitcode": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(service, "collect_script_suite", fake_collect_script_suite)

    service._collect_generated_suite(tmp_path, artifacts)

    assert calls == [
        (tmp_path.resolve(), 120, ["testcases/openapi/v1/agent/analysis/post/test_api.py"]),
        (tmp_path.resolve(), 120, None),
    ]


def test_collect_generated_suite_stops_when_changed_collection_fails(monkeypatch, tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    calls = []

    def fake_collect_script_suite(*, suite_path, timeout, test_paths=None):
        calls.append(test_paths)
        return {"ok": False, "exitcode": 4, "stdout": "", "stderr": "broken changed file"}

    monkeypatch.setattr(service, "collect_script_suite", fake_collect_script_suite)

    with pytest.raises(HTTPException) as exc_info:
        service._collect_generated_suite(tmp_path, artifacts)

    assert calls == [["testcases/openapi/v1/agent/analysis/post/test_api.py"]]
    assert exc_info.value.detail["code"] == "API_SCRIPT_COLLECTION_FAILED"
    assert "broken changed file" in exc_info.value.detail["message"]


def test_find_legacy_endpoint_artifacts_uses_verified_endpoint_ids(tmp_path: Path) -> None:
    _, artifacts = service._prepare_endpoint_generation(tmp_path, [_endpoint()])
    canonical = artifacts["apiend-1"]
    canonical["data_file_path"].parent.mkdir(parents=True)
    canonical["test_file_path"].write_text("def test_api():\n    pass\n", encoding="utf-8")
    canonical["data_file_path"].write_text(yaml.safe_dump([{"endpoint_id": "apiend-1"}]), encoding="utf-8")

    legacy_dir = tmp_path / "testcases" / "v1" / "agent"
    legacy_dir.mkdir(parents=True)
    legacy_test = legacy_dir / "test_agent.py"
    legacy_data = legacy_dir / "test_agent.yaml"
    legacy_test.write_text("def test_agent():\n    pass\n", encoding="utf-8")
    legacy_data.write_text(yaml.safe_dump([{"endpoint_id": "apiend-1"}]), encoding="utf-8")

    unrelated_dir = tmp_path / "testcases" / "v1" / "other"
    unrelated_dir.mkdir(parents=True)
    unrelated_test = unrelated_dir / "test_other.py"
    unrelated_data = unrelated_dir / "test_other.yaml"
    unrelated_test.write_text("def test_other():\n    pass\n", encoding="utf-8")
    unrelated_data.write_text(yaml.safe_dump([{"endpoint_id": "apiend-2"}]), encoding="utf-8")

    legacy_paths = service._find_legacy_endpoint_artifacts(tmp_path, "apiend-1", canonical)

    assert legacy_paths == [legacy_test.resolve(), legacy_data.resolve()]


def test_remove_legacy_endpoint_artifacts_preserves_unrelated_files(tmp_path: Path) -> None:
    legacy_dir = tmp_path / "testcases" / "v1" / "agent"
    legacy_dir.mkdir(parents=True)
    legacy_test = legacy_dir / "test_agent.py"
    legacy_data = legacy_dir / "test_agent.yaml"
    unrelated = legacy_dir / "README.md"
    legacy_test.write_text("test", encoding="utf-8")
    legacy_data.write_text("data", encoding="utf-8")
    unrelated.write_text("keep", encoding="utf-8")

    backups = service._remove_legacy_endpoint_artifacts([legacy_test.resolve(), legacy_data.resolve()])

    assert not legacy_test.exists()
    assert not legacy_data.exists()
    assert unrelated.is_file()

    service._restore_removed_endpoint_artifacts(backups)

    assert legacy_test.read_text(encoding="utf-8") == "test"
    assert legacy_data.read_text(encoding="utf-8") == "data"


def test_cleanup_legacy_endpoint_artifacts_restores_files_when_collection_fails(monkeypatch, tmp_path: Path) -> None:
    legacy_test = tmp_path / "test_agent.py"
    legacy_data = tmp_path / "test_agent.yaml"
    legacy_test.write_text("test", encoding="utf-8")
    legacy_data.write_text("data", encoding="utf-8")

    def fail_collection(*args, **kwargs):
        raise HTTPException(status_code=422, detail={"code": "API_SCRIPT_COLLECTION_FAILED", "message": "broken"})

    monkeypatch.setattr(service, "_collect_suite_or_raise", fail_collection)

    with pytest.raises(HTTPException):
        service._cleanup_legacy_endpoint_artifacts(tmp_path, [legacy_test.resolve(), legacy_data.resolve()])

    assert legacy_test.read_text(encoding="utf-8") == "test"
    assert legacy_data.read_text(encoding="utf-8") == "data"
