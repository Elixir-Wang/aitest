from pydantic import BaseModel, Field

ProjectStatus = str


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    status: ProjectStatus
    created_at: str
    updated_at: str
    available_actions: list[str]


class ProjectCreateIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    status: ProjectStatus = "active"


class ProjectUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    status: ProjectStatus | None = None
