"""跨子模块共享的小型 helper。

约定：仅放 _无副作用_、_无业务依赖_ 的纯函数或路径工具，被 2 个及以上子模块调用。
具体业务 helper（如澄清项匹配、序列化）放业务子模块内，避免 _common 退化成大杂烩。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.exceptions import api_error
from app.core.storage import project_requirement_dir, resolve_stored_path


def version_markdown_path(project_id: str, document_id: str, version_no: int) -> Path:
    return project_requirement_dir(project_id, document_id) / "versions" / f"v{version_no}.md"


def read_version_markdown(version) -> str:
    markdown_path = resolve_stored_path(version["file_path"]) or Path(version["file_path"])
    if not markdown_path.exists():
        raise api_error(404, "DOCUMENT_VERSION_FILE_NOT_FOUND", "需求版本文件不存在。")
    return markdown_path.read_text(encoding="utf-8")


def content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()