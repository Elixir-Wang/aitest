from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.project import ProjectCreateIn, ProjectOut, ProjectUpdateIn
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(actor=Depends(current_user)) -> list[dict]:
    return project_service.list_projects(actor)


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreateIn, actor=Depends(require_admin)) -> dict:
    return project_service.create_project(payload, actor)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, payload: ProjectUpdateIn, actor=Depends(require_admin)) -> dict:
    return project_service.update_project(project_id, payload, actor)


@router.delete("/{project_id}")
def delete_project(project_id: str, actor=Depends(require_admin)) -> dict:
    return project_service.delete_project(project_id, actor)
