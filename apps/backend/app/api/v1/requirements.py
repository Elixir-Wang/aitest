from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from app.dependencies.auth import current_user, require_admin
from app.schemas.document import (
    RequirementAnalysisFinalizeIn,
    RequirementClarificationAnswerIn,
    SourceDocumentUpdateIn,
    SourceMarkdownUpdateIn,
)
from app.services.document import service as document_service

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])
global_router = APIRouter(prefix="/requirements", tags=["requirements"])
file_router = APIRouter(prefix="/requirement-files", tags=["requirements"])


@global_router.get("")
def list_visible_requirements(actor=Depends(current_user)) -> list[dict]:
    return document_service.list_visible_documents(actor)


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


@router.get("/{document_id}/versions/{version_id}")
def get_requirement_version_detail(
    project_id: str,
    document_id: str,
    version_id: str,
    actor=Depends(current_user),
) -> dict:
    _ = actor
    return document_service.get_document_version_detail(project_id, document_id, version_id)


@router.put("/{document_id}/versions/{version_id}/current")
def switch_requirement_current_version(
    project_id: str,
    document_id: str,
    version_id: str,
    actor=Depends(current_user),
) -> dict:
    return document_service.switch_document_current_version(project_id, document_id, version_id, actor)


@router.get("/{document_id}/overview")
def get_requirement_overview(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_service.get_document_overview(project_id, document_id, actor)


@router.post("/{document_id}/analysis")
async def analyze_requirement(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return await document_service.analyze_document_requirement(project_id, document_id, actor)


@router.post("/{document_id}/review")
def review_requirement(
    project_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    actor=Depends(current_user),
) -> dict:
    task = document_service.start_requirement_review_run(project_id, document_id, actor)
    background_tasks.add_task(document_service.execute_requirement_review_run, task["source_id"], dict(actor))
    return task


@router.post("/{document_id}/analysis-runs/{run_id}/stop")
def stop_requirement_analysis_run(
    project_id: str,
    document_id: str,
    run_id: str,
    actor=Depends(current_user),
) -> dict:
    return document_service.stop_requirement_analysis_run(project_id, document_id, run_id, actor)


@router.get("/{document_id}/analysis-runs")
def list_requirement_analysis_runs(project_id: str, document_id: str, actor=Depends(current_user)) -> list[dict]:
    return document_service.list_requirement_analysis_runs(project_id, document_id, actor)


@router.get("/{document_id}/analysis")
def get_requirement_analysis(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_service.get_latest_requirement_analysis(project_id, document_id, actor)


@router.post("/{document_id}/analysis/finalize")
def finalize_requirement_analysis(
    project_id: str,
    document_id: str,
    payload: RequirementAnalysisFinalizeIn,
    actor=Depends(current_user),
) -> dict:
    return document_service.finalize_requirement_analysis(project_id, document_id, payload, actor)


@router.get("/{document_id}/analysis/{analysis_id}/clarification-answers")
def list_requirement_clarification_answers(
    project_id: str,
    document_id: str,
    analysis_id: str,
    actor=Depends(current_user),
) -> dict:
    return document_service.list_requirement_clarification_answers(project_id, document_id, analysis_id, actor)


@router.post("/{document_id}/analysis/{analysis_id}/clarification-answers")
def save_requirement_clarification_answer(
    project_id: str,
    document_id: str,
    analysis_id: str,
    payload: RequirementClarificationAnswerIn,
    actor=Depends(current_user),
) -> dict:
    return document_service.save_requirement_clarification_answer(project_id, document_id, analysis_id, payload, actor)


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


@router.put("/{document_id}")
def update_requirement(
    project_id: str,
    document_id: str,
    payload: SourceDocumentUpdateIn,
    actor=Depends(require_admin),
) -> dict:
    return document_service.update_document(project_id, document_id, payload, actor)


@router.put("/{document_id}/files/{mapping_id}/primary")
def set_primary_requirement_file(
    project_id: str,
    document_id: str,
    mapping_id: str,
    actor=Depends(current_user),
) -> dict:
    return document_service.set_primary_requirement_file(project_id, document_id, mapping_id, actor)


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
