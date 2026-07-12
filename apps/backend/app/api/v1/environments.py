from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import current_user, require_admin
from app.schemas.environment import (
    AutoAuthStatusOut,
    ExplorationEnvironmentCreateIn,
    ExplorationEnvironmentOut,
    ExplorationEnvironmentUpdateIn,
    ManualAuthSessionOut,
)
from app.services import auto_auth_service, environment_service, manual_auth_service

router = APIRouter(prefix="/environments", tags=["environments"])


@router.get("", response_model=list[ExplorationEnvironmentOut])
def list_environments(
    project_id: str | None = Query(default=None),
    actor=Depends(current_user),
) -> list[dict]:
    return environment_service.list_visible_environments(actor, project_id)


@router.post("", response_model=ExplorationEnvironmentOut)
def create_environment(payload: ExplorationEnvironmentCreateIn, actor=Depends(require_admin)) -> dict:
    return environment_service.create_environment(payload, actor)


@router.patch("/{environment_id}", response_model=ExplorationEnvironmentOut)
def update_environment(
    environment_id: str,
    payload: ExplorationEnvironmentUpdateIn,
    actor=Depends(require_admin),
) -> dict:
    return environment_service.update_environment(environment_id, payload, actor)


@router.delete("/{environment_id}")
def delete_environment(environment_id: str, actor=Depends(require_admin)) -> dict:
    return environment_service.delete_environment(environment_id, actor)


@router.get("/{environment_id}/auto-auth/status", response_model=AutoAuthStatusOut)
def get_auto_auth_status(environment_id: str, actor=Depends(require_admin)) -> dict:
    _ = actor
    return auto_auth_service.get_auto_auth_status(environment_id)


@router.post("/{environment_id}/auto-auth/start", response_model=ExplorationEnvironmentOut)
def start_environment_auto_auth(environment_id: str, actor=Depends(require_admin)) -> dict:
    return environment_service.start_environment_auto_auth(environment_id, actor)


@router.post("/{environment_id}/manual-auth/start", response_model=ManualAuthSessionOut)
def start_manual_auth_session(environment_id: str, actor=Depends(require_admin)) -> dict:
    return manual_auth_service.start_manual_auth_session(environment_id, actor)


@router.post("/{environment_id}/manual-auth/{session_id}/save", response_model=ManualAuthSessionOut)
def save_manual_auth_session(environment_id: str, session_id: str, actor=Depends(require_admin)) -> dict:
    return manual_auth_service.save_manual_auth_session(environment_id, session_id, actor)


@router.get("/{environment_id}/manual-auth/{session_id}/status", response_model=ManualAuthSessionOut)
def get_manual_auth_session_status(environment_id: str, session_id: str, actor=Depends(require_admin)) -> dict:
    return manual_auth_service.get_manual_auth_session_status(environment_id, session_id, actor)


@router.post("/{environment_id}/manual-auth/{session_id}/cancel", response_model=ManualAuthSessionOut)
def cancel_manual_auth_session(environment_id: str, session_id: str, actor=Depends(require_admin)) -> dict:
    return manual_auth_service.cancel_manual_auth_session(environment_id, session_id, actor)
