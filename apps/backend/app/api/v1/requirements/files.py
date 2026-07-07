"""需求文档下文件操作。

- ``POST /projects/{project_id}/requirements/{document_id}/files`` —— 追加源文件（multipart）
- ``PUT /projects/{project_id}/requirements/{document_id}/files/{mapping_id}/primary`` —— 设置主文件
"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from app.dependencies.auth import current_user
from app.services.document import documents as document_documents

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


@router.post("/{document_id}/files")
async def append_requirement_files(
    project_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    actor=Depends(current_user),
) -> dict:
    result = await document_documents.append_document_files(project_id, document_id, files, actor)
    background_tasks.add_task(
        document_documents.convert_pending_file_mappings,
        [item["id"] for item in result["files"]],
        dict(actor),
        auto_continue=False,
    )
    return result


@router.put("/{document_id}/files/{mapping_id}/primary")
def set_primary_requirement_file(
    project_id: str,
    document_id: str,
    mapping_id: str,
    actor=Depends(current_user),
) -> dict:
    return document_documents.set_primary_requirement_file(project_id, document_id, mapping_id, actor)
