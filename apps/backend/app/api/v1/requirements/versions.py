"""需求文档版本管理。

- ``GET /projects/{project_id}/requirements/{document_id}/versions`` —— 版本列表
- ``GET /projects/{project_id}/requirements/{document_id}/versions/{version_id}`` —— 版本详情
- ``PUT /projects/{project_id}/requirements/{document_id}/versions/{version_id}/current`` —— 切换当前版本
"""

from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user
from app.services.document import versions as document_versions

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


@router.get("/{document_id}/versions")
def list_requirement_versions(project_id: str, document_id: str, actor=Depends(current_user)) -> list[dict]:
    _ = project_id
    _ = actor
    return document_versions.get_document_versions(document_id)


@router.get("/{document_id}/versions/{version_id}")
def get_requirement_version_detail(
    project_id: str,
    document_id: str,
    version_id: str,
    actor=Depends(current_user),
) -> dict:
    _ = actor
    return document_versions.get_document_version_detail(project_id, document_id, version_id)


@router.put("/{document_id}/versions/{version_id}/current")
def switch_requirement_current_version(
    project_id: str,
    document_id: str,
    version_id: str,
    actor=Depends(current_user),
) -> dict:
    return document_versions.switch_document_current_version(project_id, document_id, version_id, actor)
