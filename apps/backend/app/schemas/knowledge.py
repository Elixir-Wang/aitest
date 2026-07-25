from typing import Literal

from pydantic import BaseModel, Field

from app.agents.knowledge.schemas import (
    KnowledgeQueryInput,
    KnowledgeQueryOutput,
    KnowledgeSourceDocumentInput,
)


class KnowledgeQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=12000)
    include_requirements: bool = True
    include_company_knowledge: bool = True
    show_thinking: bool = False
    conversation_id: str | None = None


class KnowledgeSearchSourceSetting(BaseModel):
    source_type: str
    enabled: bool


class KnowledgeSearchSettingsUpdate(BaseModel):
    sources: list[KnowledgeSearchSourceSetting]


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
    created_at: str


class KnowledgeConversationDetail(BaseModel):
    conversation: KnowledgeConversation
    messages: list[KnowledgeConversationMessage] = Field(default_factory=list)
