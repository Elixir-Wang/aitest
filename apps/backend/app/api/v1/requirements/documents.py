"""需求文档 CRUD + 文件列表。

- ``GET /projects/{project_id}/requirements`` —— 列出项目内可见需求文档
- ``POST /projects/{project_id}/requirements`` —— 上传需求文档（multipart，含可选 background_tasks）
- ``GET /projects/{project_id}/requirements/{document_id}`` —— 文档详情
- ``GET /projects/{project_id}/requirements/{document_id}/files`` —— 文档下文件列表
- ``PUT /projects/{project_id}/requirements/{document_id}`` —— 更新文档元数据
- ``DELETE /projects/{project_id}/requirements/{document_id}`` —— 删除文档
"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile

from app.dependencies.auth import current_user, require_admin
from app.schemas.document import SourceDocumentUpdateIn
from app.services.document import service as document_service

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


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
    background_tasks.add_task(
        document_service.convert_pending_file_mappings,
        [item["id"] for item in result["files"]],
        dict(actor),
        auto_continue=(mode == "new"),
    )
    return result


@router.get("/{document_id}")
def get_requirement(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_service.get_document_detail(project_id, document_id, actor)


@router.get("/{document_id}/files")
def list_requirement_files(project_id: str, document_id: str, actor=Depends(current_user)) -> list[dict]:
    _ = actor
    return document_service.list_document_files(project_id, document_id)


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