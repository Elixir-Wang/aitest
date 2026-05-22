from __future__ import annotations

from pydantic import BaseModel, Field


class SkillOut(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool


class AgentOut(BaseModel):
    id: str
    name: str
    description: str
    model: str
    skill_ids: list[str]


class AgentRunIn(BaseModel):
    prompt: str = Field(min_length=1)


class AgentRunOut(BaseModel):
    agent_id: str
    output: str


class AgentModelAssignmentIn(BaseModel):
    model_provider_id: str = Field(min_length=1)


class AgentModelAssignmentOut(BaseModel):
    agent_id: str
    agent_name: str
    agent_description: str
    model_provider_id: str | None = None
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key_mask: str | None = None
    model_status: str | None = None
    updated_at: str | None = None
