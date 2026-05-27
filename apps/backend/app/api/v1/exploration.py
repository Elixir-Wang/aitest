from __future__ import annotations

import threading

from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.exploration import (
    ExplorationLogOut,
    ExplorationReportOut,
    ExplorationRunCreateIn,
    ExplorationRunDetailOut,
    ExplorationRunOut,
    ExplorationRunUpdateIn,
)
from app.services import exploration_service, site_exploration_orchestrator

router = APIRouter(prefix="/projects", tags=["exploration"])
global_router = APIRouter(prefix="/exploration-runs", tags=["exploration"])


@global_router.get("", response_model=list[ExplorationRunOut])
def list_visible_runs(actor=Depends(current_user)) -> list[dict]:
    return exploration_service.list_visible_runs(actor)


@router.get("/{project_id}/exploration-runs", response_model=list[ExplorationRunOut])
def list_project_runs(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return exploration_service.list_project_runs(project_id, actor)


@router.get("/{project_id}/exploration-runs/{run_id}", response_model=ExplorationRunOut)
def get_project_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return exploration_service.get_project_run(project_id, run_id, actor)


@router.get("/{project_id}/exploration-runs/{run_id}/detail", response_model=ExplorationRunDetailOut)
def get_project_run_detail(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return exploration_service.get_project_run_detail(project_id, run_id, actor)


@router.get("/{project_id}/exploration-runs/{run_id}/report", response_model=ExplorationReportOut)
def get_project_run_report(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return exploration_service.get_project_run_report(project_id, run_id, actor)


@router.get("/{project_id}/exploration-runs/{run_id}/log", response_model=ExplorationLogOut)
def get_project_run_log(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return exploration_service.get_project_run_log(project_id, run_id, actor)


@router.post("/{project_id}/exploration-runs", response_model=ExplorationRunOut)
def create_project_run(
    project_id: str,
    payload: ExplorationRunCreateIn,
    actor=Depends(require_admin),
) -> dict:
    return exploration_service.create_project_run(project_id, payload, actor)


@router.patch("/{project_id}/exploration-runs/{run_id}", response_model=ExplorationRunOut)
def update_project_run(
    project_id: str,
    run_id: str,
    payload: ExplorationRunUpdateIn,
    actor=Depends(require_admin),
) -> dict:
    return exploration_service.update_project_run(project_id, run_id, payload, actor)


@router.post("/{project_id}/exploration-runs/{run_id}/start", response_model=ExplorationRunOut)
def start_project_run(
    project_id: str,
    run_id: str,
    actor=Depends(require_admin),
) -> dict:
    run = exploration_service.start_project_run(project_id, run_id, actor)
    _dispatch_exploration_run(run_id)
    return run


def _dispatch_exploration_run(run_id: str) -> None:
    thread = threading.Thread(
        target=site_exploration_orchestrator.run_exploration,
        args=(run_id,),
        daemon=True,
    )
    thread.start()


@router.post("/{project_id}/exploration-runs/{run_id}/stop", response_model=ExplorationRunOut)
def stop_project_run(project_id: str, run_id: str, actor=Depends(require_admin)) -> dict:
    return exploration_service.stop_project_run(project_id, run_id, actor)


@router.delete("/{project_id}/exploration-runs/{run_id}")
def delete_project_run(project_id: str, run_id: str, actor=Depends(require_admin)) -> dict:
    return exploration_service.delete_project_run(project_id, run_id, actor)
