"""公司知识库（"global knowledge vault"）管理接口。

URL 前缀沿用历史设计 ``/global-knowledge``（见 spec ``2026-06-13-company-knowledge-vault-redesign-spec.md``），
前端展示名为"公司知识库"，OpenAPI tag 与之一致。
"""

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.dependencies.auth import current_user
from app.schemas.global_knowledge import (
    GlobalKnowledgeBaseCreateIn,
    GlobalKnowledgeBaseUpdateIn,
    GlobalKnowledgeFolderCreateIn,
)
from app.services.knowledge import global_service as global_knowledge_service

router = APIRouter(prefix="/global-knowledge", tags=["company-knowledge-bases"])


@router.get("/bases")
def list_company_knowledge_bases(
    keyword: str = Query(default=""),
    actor=Depends(current_user),
) -> dict:
    return global_knowledge_service.list_bases(actor=actor, keyword=keyword)


@router.post("/bases")
def create_company_knowledge_base(
    payload: GlobalKnowledgeBaseCreateIn,
    actor=Depends(current_user),
) -> dict:
    return global_knowledge_service.create_base(
        name=payload.name,
        description=payload.description,
        actor=actor,
    )


@router.patch("/bases/{base_id}")
def update_company_knowledge_base(
    base_id: str,
    payload: GlobalKnowledgeBaseUpdateIn,
    actor=Depends(current_user),
) -> dict:
    return global_knowledge_service.update_base(
        base_id,
        name=payload.name,
        description=payload.description,
        actor=actor,
    )


@router.get("/bases/{base_id}/tree")
def get_company_knowledge_base_tree(base_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.get_base_tree(base_id, actor)


@router.delete("/bases/{base_id}")
def delete_company_knowledge_base(base_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.delete_base(base_id, actor)


@router.post("/bases/{base_id}/folders")
def create_company_knowledge_folder(
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
async def upload_company_knowledge_folder_files(
    base_id: str,
    folder_id: str,
    files: list[UploadFile] = File(...),
    actor=Depends(current_user),
) -> dict:
    return await global_knowledge_service.upload_files_to_folder(base_id, folder_id, files, actor)


@router.get("/bases/{base_id}/files/{file_id}")
def get_company_knowledge_vault_file(base_id: str, file_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.get_vault_file(base_id, file_id, actor)


@router.delete("/bases/{base_id}/files/{file_id}")
def delete_company_knowledge_vault_file(base_id: str, file_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.delete_vault_file(base_id, file_id, actor)


@router.delete("/bases/{base_id}/folders/{folder_id}")
def delete_company_knowledge_folder(base_id: str, folder_id: str, actor=Depends(current_user)) -> dict:
    return global_knowledge_service.delete_folder(base_id, folder_id, actor)