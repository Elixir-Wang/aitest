from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.dependencies.auth import current_user, require_admin
from app.schemas.ui_automation import (
    UiAutomationAssetDetailOut,
    UiAutomationAssetOut,
    UiAutomationExecutionCreateIn,
    UiAutomationExecutionRunOut,
    UiAutomationGenerateIn,
    UiAutomationGenerationRunOut,
    UiAutomationLiveViewOut,
    UiAutomationRunDetailOut,
    UiAutomationRunEventsOut,
    UiAutomationRunLogsOut,
)
from app.services.ui_automation import service


router = APIRouter(prefix="/projects/{project_id}/ui-automation", tags=["ui-automation"])


@router.post("/generation-runs", response_model=UiAutomationGenerationRunOut)
def create_generation_run(
    project_id: str,
    payload: UiAutomationGenerateIn,
    actor=Depends(require_admin),
) -> dict:
    created = service.create_generation_run(project_id, payload.model_dump(), actor)
    service.schedule_generation_run(created["id"])
    return created


@router.get("/generation-runs/{run_id}", response_model=UiAutomationGenerationRunOut)
def get_generation_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_generation_run(project_id, run_id, actor)


@router.get("/generation-runs", response_model=list[UiAutomationGenerationRunOut])
def list_generation_runs(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_generation_runs(project_id, actor)


@router.get("/assets", response_model=list[UiAutomationAssetOut])
def list_assets(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_assets(project_id, actor)


@router.get("/assets/{asset_id}", response_model=UiAutomationAssetDetailOut)
def get_asset(project_id: str, asset_id: str, actor=Depends(current_user)) -> dict:
    return service.get_asset(project_id, asset_id, actor)


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(project_id: str, asset_id: str, actor=Depends(require_admin)) -> None:
    service.delete_asset(project_id, asset_id, actor)


@router.get("/assets/{asset_id}/generation-runs", response_model=list[UiAutomationGenerationRunOut])
def list_asset_generation_runs(project_id: str, asset_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_asset_generation_runs(project_id, asset_id, actor)


@router.get("/assets/{asset_id}/runs", response_model=list[UiAutomationExecutionRunOut])
def list_asset_execution_runs(project_id: str, asset_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_asset_execution_runs(project_id, asset_id, actor)


@router.post("/assets/{asset_id}/runs", response_model=UiAutomationExecutionRunOut)
def create_execution_run(
    project_id: str,
    asset_id: str,
    payload: UiAutomationExecutionCreateIn,
    actor=Depends(require_admin),
) -> dict:
    created = service.create_execution_run(project_id, asset_id, payload.environment_id, actor)
    service.schedule_execution_run(created["id"])
    return created


@router.get("/runs/{run_id}", response_model=UiAutomationExecutionRunOut)
def get_execution_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    result = service.get_execution_run(project_id, run_id, actor)
    return result


@router.post("/runs/{run_id}/stop", response_model=UiAutomationExecutionRunOut)
def stop_execution_run(project_id: str, run_id: str, actor=Depends(require_admin)) -> dict:
    return service.stop_execution_run(project_id, run_id, actor)


@router.delete("/runs/{run_id}", status_code=204)
def delete_execution_run(project_id: str, run_id: str, actor=Depends(require_admin)) -> None:
    service.delete_execution_run(project_id, run_id, actor)


@router.get("/runs/{run_id}/logs", response_model=UiAutomationRunLogsOut)
def get_execution_logs(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_execution_logs(project_id, run_id, actor)


@router.get("/runs/{run_id}/result-detail", response_model=UiAutomationRunDetailOut)
def get_execution_result_detail(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_execution_result_detail(project_id, run_id, actor)


@router.get("/runs/{run_id}/events", response_model=UiAutomationRunEventsOut)
def get_execution_events(
    project_id: str,
    run_id: str,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    actor=Depends(current_user),
) -> dict:
    return service.get_execution_events(project_id, run_id, actor, after=after, limit=limit)


@router.get("/runs/{run_id}/step-artifacts/{artifact_id}", response_class=FileResponse)
def get_execution_step_artifact(
    project_id: str,
    run_id: str,
    artifact_id: str,
    actor=Depends(current_user),
):
    return service.get_execution_step_artifact(project_id, run_id, artifact_id, actor)


@router.get("/runs/{run_id}/live-view", response_model=UiAutomationLiveViewOut)
def get_execution_live_view(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_execution_live_view(project_id, run_id, actor)


@router.get("/runs/{run_id}/live-view/stream")
def stream_execution_live_view(project_id: str, run_id: str, token: str = Query(min_length=32)):
    return service.stream_execution_live_view(project_id, run_id, token)


@router.get("/runs/{run_id}/artifacts/{artifact_kind}", response_class=FileResponse)
def get_execution_artifact(
    project_id: str,
    run_id: str,
    artifact_kind: Literal["screenshot"],
    index: int = Query(default=0, ge=0),
    actor=Depends(current_user),
):
    return service.get_execution_artifact(project_id, run_id, artifact_kind, index, actor)
