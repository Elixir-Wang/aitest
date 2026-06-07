from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.environment import (
    ManualAuthSessionOut,
    ProjectEnvironmentCreateIn,
    ProjectEnvironmentOut,
    ProjectEnvironmentUpdateIn,
)
from app.services import environment_service, manual_auth_service

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


@router.post("/{project_id}/environments/{environment_id}/manual-auth/start", response_model=ManualAuthSessionOut)
def start_manual_auth_session(project_id: str, environment_id: str, actor=Depends(require_admin)) -> dict:
    return manual_auth_service.start_manual_auth_session(project_id, environment_id, actor)


@router.post(
    "/{project_id}/environments/{environment_id}/manual-auth/{session_id}/save",
    response_model=ManualAuthSessionOut,
)
def save_manual_auth_session(
    project_id: str,
    environment_id: str,
    session_id: str,
    actor=Depends(require_admin),
) -> dict:
    return manual_auth_service.save_manual_auth_session(project_id, environment_id, session_id, actor)


@router.get(
    "/{project_id}/environments/{environment_id}/manual-auth/{session_id}/status",
    response_model=ManualAuthSessionOut,
)
def get_manual_auth_session_status(
    project_id: str,
    environment_id: str,
    session_id: str,
    actor=Depends(require_admin),
) -> dict:
    return manual_auth_service.get_manual_auth_session_status(project_id, environment_id, session_id, actor)


@router.post(
    "/{project_id}/environments/{environment_id}/manual-auth/{session_id}/cancel",
    response_model=ManualAuthSessionOut,
)
def cancel_manual_auth_session(
    project_id: str,
    environment_id: str,
    session_id: str,
    actor=Depends(require_admin),
) -> dict:
    return manual_auth_service.cancel_manual_auth_session(project_id, environment_id, session_id, actor)


@router.delete("/{project_id}/environments/{environment_id}")
def delete_project_environment(project_id: str, environment_id: str, actor=Depends(require_admin)) -> dict:
    return environment_service.delete_project_environment(project_id, environment_id, actor)
