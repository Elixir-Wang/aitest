from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from app.dependencies.auth import current_user, require_admin
from app.schemas.document import ConflictResolutionIn, RequirementMergeRequestIn, SourceDocumentUpdateIn, SourceMarkdownUpdateIn
from app.services import document_service

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])
file_router = APIRouter(prefix="/requirement-files", tags=["requirements"])


@router.get("")
def list_requirements(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return document_service.list_documents(project_id, actor)


@router.post("")
async def upload_requirements(
    project_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    mode: str = Form(default="new"),
    document_name: str = Form(default=""),
    existing_document_id: str = Form(default=""),
    actor=Depends(current_user),
) -> dict:
    result = await document_service.upload_documents(
        project_id,
        files,
        actor,
        mode=mode,
        document_name=document_name,
        existing_document_id=existing_document_id,
    )
    background_tasks.add_task(document_service.convert_pending_file_mappings, [item["id"] for item in result["files"]])
    return result


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


@router.get("/{document_id}/overview")
def get_requirement_overview(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_service.get_document_overview(project_id, document_id, actor)


@router.post("/{document_id}/analysis")
async def analyze_requirement(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return await document_service.analyze_document_requirement(project_id, document_id, actor)


@router.get("/{document_id}/analysis")
def get_requirement_analysis(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_service.get_latest_requirement_analysis(project_id, document_id, actor)


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
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    actor=Depends(current_user),
) -> dict:
    result = await document_service.append_document_files(project_id, document_id, files, actor)
    background_tasks.add_task(document_service.convert_pending_file_mappings, [item["id"] for item in result["files"]])
    return result


@router.post("/{document_id}/merge")
async def merge_requirement(
    project_id: str,
    document_id: str,
    payload: RequirementMergeRequestIn | None = Body(default=None),
    actor=Depends(current_user),
) -> dict:
    return await document_service.merge_document_markdown(
        project_id,
        document_id,
        actor,
        confirm_preview_id=payload.confirm_preview_id if payload else "",
        force_rebuild=payload.force_rebuild if payload else False,
    )


@router.get("/{document_id}/conflicts")
def list_requirement_conflicts(project_id: str, document_id: str, actor=Depends(current_user)) -> list[dict]:
    return document_service.list_document_conflicts(project_id, document_id, actor)


@router.put("/{document_id}/conflicts/{conflict_id}")
def resolve_requirement_conflict(
    project_id: str,
    document_id: str,
    conflict_id: str,
    payload: ConflictResolutionIn,
    actor=Depends(current_user),
) -> dict:
    return document_service.resolve_document_conflict(
        project_id,
        document_id,
        conflict_id,
        resolution=payload.resolution,
        resolution_type=payload.resolution_type,
        actor=actor,
    )


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
    return document_service.delete_document(project_id, document_id, actor)


@file_router.get("/{mapping_id}/original")
def get_requirement_original_file(mapping_id: str, actor=Depends(current_user)) -> dict:
    _ = actor
    return document_service.get_original_file(mapping_id)


@file_router.get("/{mapping_id}/original/content")
def get_requirement_original_file_content(mapping_id: str, actor=Depends(current_user)) -> FileResponse:
    _ = actor
    original_file = document_service.get_original_file(mapping_id)
    if original_file["content_type"] == "text":
        path = original_file["content_path"]
        media_type = "text/plain; charset=utf-8"
    else:
        path = original_file["download_path"]
        file_format = original_file["file_format"].lower()
        media_type = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "doc": "application/msword",
        }.get(file_format, "application/octet-stream")
    return FileResponse(Path(path), media_type=media_type, filename=original_file["original_filename"])


@file_router.get("/{mapping_id}/markdown")
def get_requirement_markdown_file(mapping_id: str, actor=Depends(current_user)) -> dict:
    _ = actor
    return document_service.get_converted_markdown(mapping_id)


@file_router.post("/{mapping_id}/convert")
async def convert_requirement_file(mapping_id: str, actor=Depends(current_user)) -> dict:
    _ = actor
    return await document_service.convert_source_file_mapping(mapping_id)


@file_router.delete("/{mapping_id}")
def delete_requirement_file(mapping_id: str, actor=Depends(current_user)) -> dict:
    return document_service.delete_source_file(mapping_id, actor)


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
