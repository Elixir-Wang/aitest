from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.environment import ProjectEnvironmentCreateIn, ProjectEnvironmentOut, ProjectEnvironmentUpdateIn
from app.services import environment_service

router = APIRouter(prefix="/projects", tags=["environments"])
global_router = APIRouter(prefix="/environments", tags=["environments"])


@global_router.get("", response_model=list[ProjectEnvironmentOut])
def list_visible_environments(actor=Depends(current_user)) -> list[dict]:
    return environment_service.list_visible_environments(actor)


@router.get("/{project_id}/environments", response_model=list[ProjectEnvironmentOut])
def list_project_environments(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return environment_service.list_project_environments(project_id, actor)


@router.post("/{project_id}/environments", response_model=ProjectEnvironmentOut)
def create_project_environment(
    project_id: str,
    payload: ProjectEnvironmentCreateIn,
    actor=Depends(require_admin),
) -> dict:
    return environment_service.create_project_environment(project_id, payload, actor)


@router.patch("/{project_id}/environments/{environment_id}", response_model=ProjectEnvironmentOut)
def update_project_environment(
    project_id: str,
    environment_id: str,
    payload: ProjectEnvironmentUpdateIn,
    actor=Depends(require_admin),
) -> dict:
    return environment_service.update_project_environment(project_id, environment_id, payload, actor)


@router.delete("/{project_id}/environments/{environment_id}")
def delete_project_environment(project_id: str, environment_id: str, actor=Depends(require_admin)) -> dict:
    return environment_service.delete_project_environment(project_id, environment_id, actor)
