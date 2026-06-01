from pydantic import BaseModel, Field


class ProjectEnvironmentOut(BaseModel):
    id: str
    project_id: str
    project_name: str
    name: str
    site_url: str
    username: str
    password_mask: str
    login_strategy: str
    description: str
    created_at: str
    updated_at: str
    available_actions: list[str]


class ProjectEnvironmentCreateIn(BaseModel):
    project_id: str | None = None
    name: str = Field(min_length=1)
    site_url: str = Field(min_length=1)
    username: str = ""
    password: str = ""
    login_strategy: str = "reuse_state"
    description: str = ""


class ProjectEnvironmentUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    site_url: str | None = Field(default=None, min_length=1)
    username: str | None = None
    password: str | None = None
    login_strategy: str | None = None
    description: str | None = None
