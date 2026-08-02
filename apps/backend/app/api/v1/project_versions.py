from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.project_version import ProjectVersionCreateIn, ProjectVersionOut, ProjectVersionUpdateIn
from app.services import project_version_service


router = APIRouter(prefix="/projects/{project_id}/versions", tags=["project-versions"])


@router.get("", response_model=list[ProjectVersionOut])
def list_project_versions(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return project_version_service.list_versions(project_id, actor)


@router.post("", response_model=ProjectVersionOut)
def create_project_version(project_id: str, payload: ProjectVersionCreateIn, actor=Depends(require_admin)) -> dict:
    return project_version_service.create_version(project_id, payload, actor)


@router.patch("/{version_id}", response_model=ProjectVersionOut)
def update_project_version(project_id: str, version_id: str, payload: ProjectVersionUpdateIn, actor=Depends(require_admin)) -> dict:
    return project_version_service.update_version(project_id, version_id, payload, actor)


@router.post("/{version_id}/set-default", response_model=ProjectVersionOut)
def set_default_project_version(project_id: str, version_id: str, actor=Depends(require_admin)) -> dict:
    return project_version_service.set_default_version(project_id, version_id, actor)


@router.delete("/{version_id}")
def delete_project_version(project_id: str, version_id: str, actor=Depends(require_admin)) -> dict:
    return project_version_service.delete_version(project_id, version_id, actor)
