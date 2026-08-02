from app.api.v1 import ui_automation
from app.api.v1 import v1_router
from app.schemas.ui_automation import UiAutomationExecutionCreateIn, UiAutomationGenerateIn


def test_generation_input_accepts_one_case_only():
    payload = UiAutomationGenerateIn(test_case_id="case-1", environment_id="env-1")
    assert payload.test_case_id == "case-1"
    assert not hasattr(payload, "test_case_ids")


def test_ui_automation_routes_are_registered():
    paths = {route.path for route in v1_router.routes}
    assert "/projects/{project_id}/ui-automation/generation-runs" in paths
    assert "/projects/{project_id}/ui-automation/assets" in paths
    assert "/projects/{project_id}/ui-automation/assets/{asset_id}" in paths
    assert "/projects/{project_id}/ui-automation/assets/{asset_id}/generation-runs" in paths
    assert "/projects/{project_id}/ui-automation/assets/{asset_id}/runs" in paths
    assert "/projects/{project_id}/ui-automation/assets/{asset_id}/files" not in paths
    assert "/projects/{project_id}/ui-automation/assets/{asset_id}/files/{file_kind}" not in paths
    assert "/projects/{project_id}/ui-automation/runs/{run_id}" in paths
    assert "/projects/{project_id}/ui-automation/runs/{run_id}/stop" in paths
    assert "/projects/{project_id}/ui-automation/runs/{run_id}/logs" in paths
    assert "/projects/{project_id}/ui-automation/runs/{run_id}/result-detail" in paths
    assert "/projects/{project_id}/ui-automation/runs/{run_id}/events" in paths
    assert "/projects/{project_id}/ui-automation/runs/{run_id}/step-artifacts/{artifact_id}" in paths
    assert "/projects/{project_id}/ui-automation/runs/{run_id}/live-view" in paths
    assert "/projects/{project_id}/ui-automation/runs/{run_id}/live-view/stream" in paths
    assert "/projects/{project_id}/ui-automation/runs/{run_id}/artifacts/{artifact_kind}" in paths
    delete_route = next(
        route
        for route in v1_router.routes
        if route.path == "/projects/{project_id}/ui-automation/runs/{run_id}" and "DELETE" in route.methods
    )
    assert delete_route.status_code == 204
    delete_asset_route = next(
        route
        for route in v1_router.routes
        if route.path == "/projects/{project_id}/ui-automation/assets/{asset_id}" and "DELETE" in route.methods
    )
    assert delete_asset_route.status_code == 204


def test_delete_asset_route_delegates_to_service(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        ui_automation.service,
        "delete_asset",
        lambda project_id, asset_id, actor: captured.update(
            project_id=project_id,
            asset_id=asset_id,
            actor=actor,
        ),
    )

    ui_automation.delete_asset("project-1", "uiasset-1", actor={"id": "user-1"})

    assert captured == {"project_id": "project-1", "asset_id": "uiasset-1", "actor": {"id": "user-1"}}


def test_generation_route_schedules_managed_execution(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        ui_automation.service,
        "create_generation_run",
        lambda project_id, payload, actor: {"id": "uigen-1", "project_id": project_id, **payload},
    )

    monkeypatch.setattr(
        ui_automation.service,
        "schedule_generation_run",
        lambda run_id: captured.update(run_id=run_id),
    )

    result = ui_automation.create_generation_run(
        "project-1",
        UiAutomationGenerateIn(test_case_id="case-1", environment_id="env-1"),
        actor={"id": "user-1"},
    )

    assert result["id"] == "uigen-1"
    assert captured == {"run_id": "uigen-1"}


def test_execution_route_schedules_managed_execution(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        ui_automation.service,
        "create_execution_run",
        lambda project_id, asset_id, environment_id, actor: {
            "id": "uirun-1",
            "project_id": project_id,
            "asset_id": asset_id,
            "environment_id": environment_id,
        },
    )
    monkeypatch.setattr(
        ui_automation.service,
        "schedule_execution_run",
        lambda run_id: captured.update(run_id=run_id),
    )

    result = ui_automation.create_execution_run(
        "project-1",
        "uiasset-1",
        UiAutomationExecutionCreateIn(environment_id="env-1"),
        actor={"id": "user-1"},
    )

    assert result["id"] == "uirun-1"
    assert captured == {"run_id": "uirun-1"}
