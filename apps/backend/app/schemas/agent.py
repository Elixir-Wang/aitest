from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SkillOut(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool
    tool_count: int = 0


class AgentOut(BaseModel):
    id: str
    name: str
    description: str
    model: str
    skill_ids: list[str]


class AgentRunIn(BaseModel):
    prompt: str = Field(min_length=1)


class AgentRunOut(BaseModel):
    run_id: str
    agent_id: str
    output: Any
    model: str
    model_provider_id: str | None = None
    provider: str | None = None
    base_url: str | None = None
    skill_ids: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    raw_response_count: int = 0
    item_count: int = 0
    usage: dict[str, Any] | None = None


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
    api_key: str | None = None
    model_status: str | None = None
    updated_at: str | None = None
