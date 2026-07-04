"""document 版本管理：版本列表、版本详情、切换当前版本。"""
from __future__ import annotations

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import document_repo
from app.services import operation_log_service

from ._common import read_version_markdown
from ._constants import DOCUMENT_VERSIONED_STATUS
from .serdes import serialize_version


def get_document_versions(document_id: str) -> list[dict]:
    with connect() as db:
        rows = document_repo.find_versions_by_document(db, document_id)
        return [
            {
                "id": row["id"],
                "version_no": row["version_no"],
                "file_path": row["file_path"],
                "source_action": row["source_action"],
                "change_summary": row["change_summary"],
                "diff_summary": row["diff_summary"],
                "created_by": row["created_by"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def get_document_version_detail(project_id: str, document_id: str, version_id: str) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        version = document_repo.find_version(db, version_id)
        if not version or version["document_id"] != document_id:
            raise api_error(404, "DOCUMENT_VERSION_NOT_FOUND", "需求版本不存在。")

        markdown_content = read_version_markdown(version)
        return {
            **serialize_version(version),
            "markdown_content": markdown_content,
            "is_current": document["current_version_id"] == version_id,
        }


def switch_document_current_version(project_id: str, document_id: str, version_id: str, actor) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        version = document_repo.find_version(db, version_id)
        if not version or version["document_id"] != document_id:
            raise api_error(404, "DOCUMENT_VERSION_NOT_FOUND", "需求版本不存在。")
        if version["source_action"] not in {"requirement_analysis", "requirement_analysis_finalize"}:
            raise api_error(409, "DOCUMENT_VERSION_NOT_FINAL_REQUIREMENT", "只能切换最终需求版本。")

        markdown_content = read_version_markdown(version)
        previous_version_id = document["current_version_id"]
        document_repo.update_current_version(db, document_id, version_id, DOCUMENT_VERSIONED_STATUS)

    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="switch_final_requirement_version",
        object_type="requirement",
        object_id=document_id,
        object_name=document["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"切换最终需求版本：{document['name']} -> v{version['version_no']}",
        before={"current_version_id": previous_version_id},
        after={"current_version_id": version_id, "version_no": version["version_no"]},
    )
    return {
        "document": {
            "id": document_id,
            "current_version_id": version_id,
        },
        "version": serialize_version(version),
        "markdown_content": markdown_content,
    }