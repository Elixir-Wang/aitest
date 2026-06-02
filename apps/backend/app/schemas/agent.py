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


