from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.dependencies.auth import current_user
from app.schemas.global_knowledge import GlobalKnowledgeBaseCreateIn, GlobalKnowledgeFolderCreateIn, GlobalKnowledgeListQuery, GlobalKnowledgeUpdateIn
from app.services.knowledge import global_service as global_knowledge_service

router = APIRouter(prefix="/global-knowledge", tags=["global-knowledge"])


@router.get("/bases")
def list_global_knowledge_bases(
    keyword: str = Query(default=""),
    actor=Depends(current_user),
) -> dict:
    return global_knowledge_service.list_bases(actor=actor, keyword=keyword)


@router.post("/bases")
def create_global_knowledge_base(
    payload: GlobalKnowledgeBaseCreateIn,
    actor=Depends(current_user),
) -> dict:
    return global_knowledge_service.create_base(
        name=payload.name,
        description=payload.description,
        actor=actor,
    )


@router.get("/bases/{base_id}/tree")
def get_global_knowledge_base_tree(base_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.get_base_tree(base_id, actor)


@router.delete("/bases/{base_id}")
def delete_global_knowledge_base(base_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.delete_base(base_id, actor)


@router.post("/bases/{base_id}/folders")
def create_global_knowledge_folder(
    base_id: str,
    payload: GlobalKnowledgeFolderCreateIn,
    actor=Depends(current_user),
) -> dict:
    return global_knowledge_service.create_folder(
        base_id,
        parent_id=payload.parent_id,
        name=payload.name,
        actor=actor,
    )


@router.post("/bases/{base_id}/folders/{folder_id}/files")
async def upload_global_knowledge_folder_files(
    base_id: str,
    folder_id: str,
    files: list[UploadFile] = File(...),
    actor=Depends(current_user),
) -> dict:
    return await global_knowledge_service.upload_files_to_folder(base_id, folder_id, files, actor)


@router.get("/bases/{base_id}/files/{file_id}")
def get_global_knowledge_vault_file(base_id: str, file_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.get_vault_file(base_id, file_id, actor)


@router.delete("/bases/{base_id}/files/{file_id}")
def delete_global_knowledge_vault_file(base_id: str, file_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.delete_vault_file(base_id, file_id, actor)


@router.delete("/bases/{base_id}/folders/{folder_id}")
def delete_global_knowledge_folder(base_id: str, folder_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.delete_folder(base_id, folder_id, actor)


@router.get("/documents")
def list_global_knowledge_documents(
    keyword: str = Query(default=""),
    knowledge_type: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    actor=Depends(current_user),
) -> dict:
    return global_knowledge_service.list_documents(
        GlobalKnowledgeListQuery(
            keyword=keyword,
            knowledge_type=knowledge_type,
            status=status,
            page=page,
            page_size=page_size,
        ),
        actor,
    )


@router.post("/documents")
async def upload_global_knowledge_document(
    name: str = Form(...),
    knowledge_type: str = Form(...),
    version: str = Form(default=""),
    scope: str = Form(default="全部项目"),
    source_note: str = Form(default=""),
    description: str = Form(default=""),
    project_id: str = Form(default=""),
    files: list[UploadFile] = File(...),
    actor=Depends(current_user),
) -> dict:
    return await global_knowledge_service.upload_document(
        name=name,
        knowledge_type=knowledge_type,
        version=version,
        scope=scope,
        source_note=source_note,
        description=description,
        project_id=project_id,
        files=files,
        actor=actor,
    )


@router.get("/documents/{document_id}")
def get_global_knowledge_document(document_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.get_document(document_id, actor)


@router.patch("/documents/{document_id}")
def update_global_knowledge_document(
    document_id: str,
    payload: GlobalKnowledgeUpdateIn,
    actor=Depends(current_user),
) -> dict:
    return global_knowledge_service.update_document(document_id, payload, actor)


@router.post("/documents/{document_id}/versions")
async def create_global_knowledge_version(
    document_id: str,
    version: str = Form(default=""),
    source_note: str = Form(default=""),
    change_summary: str = Form(default=""),
    files: list[UploadFile] = File(...),
    actor=Depends(current_user),
) -> dict:
    return await global_knowledge_service.create_version(
        document_id,
        version=version,
        source_note=source_note,
        change_summary=change_summary,
        files=files,
        actor=actor,
    )


@router.post("/documents/{document_id}/archive")
def archive_global_knowledge_document(document_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.archive_document(document_id, actor)
