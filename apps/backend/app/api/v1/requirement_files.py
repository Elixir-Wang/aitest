"""需求文档源文件（已上传到 requirement document 的 mapping）下载/转换/删除接口。

URL 前缀沿用历史设计：``/requirement-files/{mapping_id}/...``。
``mapping_id`` 是 ``source_document_file_mappings`` 表的全局唯一主键，
因此这类端点不需要在路径上挂 project_id / document_id，前端拿到 ``file.id`` 后即可直接拼接。
"""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.dependencies.auth import current_user
from app.schemas.document import SourceMarkdownUpdateIn
from app.services.document import service as document_service

router = APIRouter(prefix="/requirement-files", tags=["requirement-files"])


@router.get("/{mapping_id}/original")
def get_requirement_original_file(mapping_id: str, actor=Depends(current_user)) -> dict:
    _ = actor
    return document_service.get_original_file(mapping_id)


@router.get("/{mapping_id}/original/content")
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


@router.get("/{mapping_id}/markdown")
def get_requirement_markdown_file(mapping_id: str, actor=Depends(current_user)) -> dict:
    _ = actor
    return document_service.get_converted_markdown(mapping_id)


@router.post("/{mapping_id}/convert")
async def convert_requirement_file(mapping_id: str, actor=Depends(current_user)) -> dict:
    _ = actor
    return await document_service.convert_source_file_mapping(mapping_id)


@router.delete("/{mapping_id}")
def delete_requirement_file(mapping_id: str, actor=Depends(current_user)) -> dict:
    return document_service.delete_source_file(mapping_id, actor)


@router.put("/{mapping_id}/markdown")
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