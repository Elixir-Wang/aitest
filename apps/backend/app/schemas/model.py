from __future__ import annotations

from pydantic import BaseModel, Field

Status = str


class ModelProviderOut(BaseModel):
    id: str
    provider: str
    model: str
    base_url: str
    api_key_env: str = ""
    api_key_mask: str
    description: str
    status: Status
    created_by: str
    created_at: str
    updated_at: str
    available_actions: list[str]


class ModelProviderIn(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_key: str = ""
    api_key_env: str = ""
    description: str = ""
    status: Status = "enabled"
