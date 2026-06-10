from typing import Literal

from pydantic import BaseModel, Field

from app.agents.knowledge_chat.schemas import (
    KnowledgeConversationHistoryMessage,
    KnowledgeExplorationInput,
    KnowledgeQueryInput,
    KnowledgeQueryOutput,
    KnowledgeSourceDocumentInput,
    KnowledgeSourceRef,
)


class KnowledgeQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=12000)
    include_requirements: bool = True
    include_explorations: bool = True
    conversation_id: str | None = None


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
