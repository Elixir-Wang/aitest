from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeSourceDocumentInput(BaseModel):
    source_type: Literal["requirement", "exploration", "test_case", "api_information", "company_knowledge"] = "requirement"
    source_id: str = ""
    source_title: str = ""
    project_id: str = ""
    project_name: str = ""
    document_id: str = ""
    document_name: str = ""
    version_id: str = ""
    version_no: int | None = None
    base_id: str = ""
    base_name: str = ""
    folder_path: str = ""
    file_id: str = ""
    file_name: str = ""
    file_extension: str = "md"
    markdown_content: str


class KnowledgeQueryInput(BaseModel):
    project_id: str
    project_name: str
    question: str
    source_documents: list[KnowledgeSourceDocumentInput] = Field(default_factory=list)


class KnowledgeQueryOutput(BaseModel):
    answer: str
    used_requirement_versions: list[str] = Field(default_factory=list)
    used_company_knowledge_files: list[str] = Field(default_factory=list)
    knowledge_queried: bool = False


__all__ = [
    "KnowledgeQueryInput",
    "KnowledgeQueryOutput",
    "KnowledgeSourceDocumentInput",
]
