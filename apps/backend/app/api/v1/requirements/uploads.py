from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request

from app.dependencies.auth import current_user
from app.schemas.requirement_upload import RequirementUploadSessionCreateIn
from app.services.document import documents as document_documents
from app.services.document import upload_sessions


router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


@router.get("/upload-config")
def get_requirement_upload_config(project_id: str, actor=Depends(current_user)) -> dict:
    _ = project_id, actor
    return upload_sessions.upload_config()


@router.post("/upload-sessions")
def create_requirement_upload_session(
    project_id: str,
    payload: RequirementUploadSessionCreateIn,
    actor=Depends(current_user),
) -> dict:
    return upload_sessions.create_session(project_id, payload, actor)


@router.get("/upload-sessions/{upload_id}")
def get_requirement_upload_session(project_id: str, upload_id: str, actor=Depends(current_user)) -> dict:
    return upload_sessions.get_session(project_id, upload_id, actor)


@router.delete("/upload-sessions/{upload_id}")
def cancel_requirement_upload_session(project_id: str, upload_id: str, actor=Depends(current_user)) -> dict:
    return upload_sessions.cancel_session(project_id, upload_id, actor)


@router.put("/upload-sessions/{upload_id}/files/{file_id}/parts/{part_number}")
async def upload_requirement_part(
    project_id: str,
    upload_id: str,
    file_id: str,
    part_number: int,
    request: Request,
    x_chunk_sha256: str = Header(default=""),
    actor=Depends(current_user),
) -> dict:
    return await upload_sessions.save_chunk(
        project_id,
        upload_id,
        file_id,
        part_number,
        request.stream(),
        actor,
        expected_sha256=x_chunk_sha256,
    )


@router.post("/upload-sessions/{upload_id}/complete")
async def complete_requirement_upload_session(
    project_id: str,
    upload_id: str,
    background_tasks: BackgroundTasks,
    actor=Depends(current_user),
) -> dict:
    result = await upload_sessions.complete_session(project_id, upload_id, actor)
    upload_mode = result.pop("_upload_mode")
    background_tasks.add_task(
        document_documents.convert_pending_file_mappings,
        [item["id"] for item in result["files"]],
        dict(actor),
        auto_continue=(upload_mode == "new"),
    )
    return result
