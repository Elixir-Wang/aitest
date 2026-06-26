from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeSourceDocumentInput(BaseModel):
    project_id: str
    project_name: str
    document_id: str
    document_name: str
    version_id: str
    version_no: int
    markdown_content: str


class KnowledgeConversationHistoryMessage(BaseModel):
    role: Literal["assistant", "user"]
    content: str


class KnowledgeQueryInput(BaseModel):
    project_id: str
    project_name: str
    question: str
    conversation_history: list[KnowledgeConversationHistoryMessage] = Field(default_factory=list)
    source_documents: list[KnowledgeSourceDocumentInput] = Field(default_factory=list)


class KnowledgeSourceRef(BaseModel):
    source_type: Literal["requirement", "manual"]
    source_id: str
    source_title: str
    project_id: str | None = None
    project_name: str | None = None
    location: str = ""
    excerpt: str = ""


class KnowledgeQueryOutput(BaseModel):
    answer: str
    source_refs: list[KnowledgeSourceRef] = Field(default_factory=list)
    used_requirement_versions: list[str] = Field(default_factory=list)
    knowledge_queried: bool = False


__all__ = [
    "KnowledgeConversationHistoryMessage",
    "KnowledgeQueryInput",
    "KnowledgeQueryOutput",
    "KnowledgeSourceDocumentInput",
    "KnowledgeSourceRef",
]
