from pathlib import Path


def test_page_exploration_api_has_no_operations_or_replay_routes() -> None:
    backend_root = Path(__file__).parents[3]
    artifacts_source = (
        backend_root / "app" / "api" / "v1" / "page_exploration" / "artifacts.py"
    ).read_text(encoding="utf-8")
    schemas_source = (
        backend_root / "app" / "api" / "v1" / "page_exploration" / "schemas.py"
    ).read_text(encoding="utf-8")

    for legacy_text in (
        '"/projects/{project_id}/operations"',
        '"/projects/{project_id}/operations/{operation_key}"',
        '"/projects/{project_id}/replay"',
        '"/projects/{project_id}/replay-runs/{run_id}"',
        "ReplayRunService",
        "ReplayService",
        "ReplayOperationRequest",
        "SaveReplayOperationRequest",
    ):
        assert legacy_text not in artifacts_source
        assert legacy_text not in schemas_source


def test_output_registry_does_not_write_draft_operations() -> None:
    backend_root = Path(__file__).parents[3]
    source = (
        backend_root / "app" / "services" / "page_exploration" / "output_registry.py"
    ).read_text(encoding="utf-8")

    assert "_write_draft_operation" not in source
    assert "OperationsStore" not in source
    assert "ReplayOperation" not in source
