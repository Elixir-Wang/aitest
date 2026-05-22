from __future__ import annotations

from pydantic import BaseModel, Field


class SourceDocumentVersionOut(BaseModel):
    id: str
    version_no: int
    file_path: str
    source_action: str
    change_summary: str
    diff_summary: str
    created_by: str
    created_at: str


class SourceDocumentOut(BaseModel):
    id: str
    project_id: str
    name: str
    document_type: str
    file_count: int
    current_version_id: str | None
    status: str
    created_by: str
    created_at: str
    updated_at: str
    current_version: SourceDocumentVersionOut | None = None
    available_actions: list[str]


class SourceDocumentUploadIn(BaseModel):
    mode: str = "new"
    document_name: str = ""
    existing_document_id: str = ""


class SourceDocumentUpdateIn(BaseModel):
    name: str = Field(min_length=1)
    markdown_content: str = ""
    change_summary: str = ""


class SourceMarkdownUpdateIn(BaseModel):
    markdown_content: str = ""
    change_summary: str = ""
