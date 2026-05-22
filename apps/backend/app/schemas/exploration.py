from __future__ import annotations

from pydantic import BaseModel, Field


class ExplorationRunOut(BaseModel):
    id: str
    project_id: str
    project_name: str
    environment_id: str
    environment_name: str
    title: str
    status: str
    scope: str
    forbidden_paths: str
    login_strategy: str
    description: str
    created_at: str
    updated_at: str
    available_actions: list[str]


class ExplorationRunCreateIn(BaseModel):
    project_id: str | None = None
    environment_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    scope: str = ""
    forbidden_paths: str = ""
    login_strategy: str = "reuse_state"
    description: str = ""
