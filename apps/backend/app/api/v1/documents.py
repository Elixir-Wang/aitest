from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.dependencies.auth import current_user
from app.services import document_service

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])


@router.get("")
def list_documents(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return document_service.list_documents(project_id, actor)


@router.post("")
async def upload_documents(
    project_id: str,
    files: list[UploadFile] = File(...),
    name: str = Form(default=""),
    document_type: str = Form(default="PRD"),
    change_summary: str = Form(default=""),
    actor=Depends(current_user),
) -> list[dict]:
    return await document_service.upload_documents(project_id, files, name, document_type, change_summary, actor)


@router.get("/{document_id}/versions")
def list_versions(project_id: str, document_id: str, actor=Depends(current_user)) -> list[dict]:
    _ = project_id
    return document_service.get_document_versions(document_id)
