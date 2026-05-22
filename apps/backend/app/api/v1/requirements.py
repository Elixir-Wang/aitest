from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.dependencies.auth import current_user, require_admin
from app.schemas.document import SourceDocumentUpdateIn
from app.services import document_service

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


@router.get("")
def list_requirements(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return document_service.list_documents(project_id, actor)


@router.post("")
async def upload_requirements(
    project_id: str,
    files: list[UploadFile] = File(...),
    name: str = Form(default=""),
    document_type: str = Form(default="PRD"),
    change_summary: str = Form(default=""),
    actor=Depends(current_user),
) -> list[dict]:
    return await document_service.upload_documents(project_id, files, name, document_type, change_summary, actor)


@router.get("/{document_id}/versions")
def list_requirement_versions(project_id: str, document_id: str, actor=Depends(current_user)) -> list[dict]:
    _ = project_id
    _ = actor
    return document_service.get_document_versions(document_id)


@router.get("/{document_id}")
def get_requirement(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_service.get_document_detail(project_id, document_id, actor)


@router.put("/{document_id}")
def update_requirement(
    project_id: str,
    document_id: str,
    payload: SourceDocumentUpdateIn,
    actor=Depends(require_admin),
) -> dict:
    return document_service.update_document(project_id, document_id, payload, actor)


@router.delete("/{document_id}")
def delete_requirement(project_id: str, document_id: str, actor=Depends(require_admin)) -> dict:
    _ = actor
    return document_service.delete_document(project_id, document_id)
