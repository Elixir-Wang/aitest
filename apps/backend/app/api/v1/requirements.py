from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.dependencies.auth import current_user, require_admin
from app.schemas.document import SourceDocumentUpdateIn, SourceMarkdownUpdateIn
from app.services import document_service

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])
file_router = APIRouter(prefix="/requirement-files", tags=["requirements"])


@router.get("")
def list_requirements(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return document_service.list_documents(project_id, actor)


@router.post("")
async def upload_requirements(
    project_id: str,
    files: list[UploadFile] = File(...),
    mode: str = Form(default="new"),
    document_name: str = Form(default=""),
    existing_document_id: str = Form(default=""),
    actor=Depends(current_user),
) -> dict:
    return await document_service.upload_documents(
        project_id,
        files,
        actor,
        mode=mode,
        document_name=document_name,
        existing_document_id=existing_document_id,
    )


@router.get("/check-name")
def check_requirement_name(
    project_id: str,
    name: str = Query(default=""),
    exclude_id: str | None = Query(default=None),
    actor=Depends(current_user),
) -> dict:
    _ = actor
    return document_service.check_document_name(project_id, name, exclude_id)


@router.get("/{document_id}/versions")
def list_requirement_versions(project_id: str, document_id: str, actor=Depends(current_user)) -> list[dict]:
    _ = project_id
    _ = actor
    return document_service.get_document_versions(document_id)


@router.get("/{document_id}")
def get_requirement(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_service.get_document_detail(project_id, document_id, actor)


@router.get("/{document_id}/files")
def list_requirement_files(project_id: str, document_id: str, actor=Depends(current_user)) -> list[dict]:
    _ = actor
    return document_service.list_document_files(project_id, document_id)


@router.post("/{document_id}/files")
async def append_requirement_files(
    project_id: str,
    document_id: str,
    files: list[UploadFile] = File(...),
    actor=Depends(current_user),
) -> dict:
    return await document_service.append_document_files(project_id, document_id, files, actor)


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


@file_router.get("/{mapping_id}/original")
def get_requirement_original_file(mapping_id: str, actor=Depends(current_user)) -> dict:
    _ = actor
    return document_service.get_original_file(mapping_id)


@file_router.get("/{mapping_id}/markdown")
def get_requirement_markdown_file(mapping_id: str, actor=Depends(current_user)) -> dict:
    _ = actor
    return document_service.get_converted_markdown(mapping_id)


@file_router.put("/{mapping_id}/markdown")
def update_requirement_markdown_file(
    mapping_id: str,
    payload: SourceMarkdownUpdateIn,
    actor=Depends(current_user),
) -> dict:
    return document_service.update_converted_markdown(
        mapping_id,
        markdown_content=payload.markdown_content,
        change_summary=payload.change_summary,
        actor=actor,
    )
