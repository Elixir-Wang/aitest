from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.ui_automation import (
    UiAutomationAssetOut,
    UiAutomationExecutionCreateIn,
    UiAutomationExecutionRunOut,
    UiAutomationGenerateIn,
    UiAutomationGenerationRunOut,
)
from app.services.ui_automation import service


router = APIRouter(prefix="/projects/{project_id}/ui-automation", tags=["ui-automation"])


@router.post("/generation-runs", response_model=UiAutomationGenerationRunOut)
def create_generation_run(
    project_id: str,
    payload: UiAutomationGenerateIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    created = service.create_generation_run(project_id, payload.model_dump(), actor)
    background_tasks.add_task(service.execute_generation_run, created["id"])
    return created


@router.get("/generation-runs/{run_id}", response_model=UiAutomationGenerationRunOut)
def get_generation_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_generation_run(project_id, run_id, actor)


@router.get("/assets", response_model=list[UiAutomationAssetOut])
def list_assets(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_assets(project_id, actor)


@router.get("/assets/{asset_id}", response_model=UiAutomationAssetOut)
def get_asset(project_id: str, asset_id: str, actor=Depends(current_user)) -> dict:
    return service.get_asset(project_id, asset_id, actor)


@router.post("/assets/{asset_id}/runs", response_model=UiAutomationExecutionRunOut)
def create_execution_run(
    project_id: str,
    asset_id: str,
    payload: UiAutomationExecutionCreateIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    created = service.create_execution_run(project_id, asset_id, payload.environment_id, actor)
    background_tasks.add_task(service.execute_execution_run, created["id"])
    return created


@router.get("/runs/{run_id}", response_model=UiAutomationExecutionRunOut)
def get_execution_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    result = service.get_execution_run(project_id, run_id, actor)
    return result

