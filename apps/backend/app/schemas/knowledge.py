from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeSourceDocumentInput(BaseModel):
    document_id: str
    document_name: str
    version_id: str
    version_no: int
    markdown_content: str


class KnowledgeExplorationInput(BaseModel):
    exploration_run_id: str
    title: str
    status: str
    result_summary: str = ""
    modules: list[dict] = Field(default_factory=list)


class KnowledgeQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=12000)
    include_requirements: bool = True
    include_explorations: bool = True
    conversation_id: str | None = None


class KnowledgeConversationHistoryMessage(BaseModel):
    role: Literal["assistant", "user"]
    content: str


class KnowledgeQueryInput(BaseModel):
    project_id: str
    project_name: str
    question: str
    conversation_history: list[KnowledgeConversationHistoryMessage] = Field(default_factory=list)
    source_documents: list[KnowledgeSourceDocumentInput] = Field(default_factory=list)
    explorations: list[KnowledgeExplorationInput] = Field(default_factory=list)


class KnowledgeSourceRef(BaseModel):
    source_type: Literal["requirement", "exploration", "manual"]
    source_id: str
    source_title: str
    location: str = ""
    excerpt: str = ""


class KnowledgeQueryOutput(BaseModel):
    answer: str
    source_refs: list[KnowledgeSourceRef] = Field(default_factory=list)
    used_requirement_versions: list[str] = Field(default_factory=list)
    used_exploration_runs: list[str] = Field(default_factory=list)


class KnowledgeConversation(BaseModel):
    id: str
    project_id: str
    title: str
    created_by: str
    created_at: str
    updated_at: str


class KnowledgeConversationMessage(BaseModel):
    id: str
    conversation_id: str
    role: Literal["assistant", "user"]
    content: str
    source_refs: list[KnowledgeSourceRef] = Field(default_factory=list)
    used_requirement_versions: list[str] = Field(default_factory=list)
    used_exploration_runs: list[str] = Field(default_factory=list)
    created_at: str


class KnowledgeConversationDetail(BaseModel):
    conversation: KnowledgeConversation
    messages: list[KnowledgeConversationMessage] = Field(default_factory=list)
