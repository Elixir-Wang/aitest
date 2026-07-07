"""需求文档元信息端点。

- ``GET /projects/{project_id}/requirements/check-name`` —— 重名校验
- ``GET /projects/{project_id}/requirements/{document_id}/overview`` —— 文档概览
"""

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import current_user
from app.services.document import documents as document_documents

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


@router.get("/check-name")
def check_requirement_name(
    project_id: str,
    name: str = Query(default=""),
    exclude_id: str | None = Query(default=None),
    actor=Depends(current_user),
) -> dict:
    _ = actor
    return document_documents.check_document_name(project_id, name, exclude_id)


@router.get("/{document_id}/overview")
def get_requirement_overview(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_documents.get_document_overview(project_id, document_id, actor)
