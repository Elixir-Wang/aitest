from pydantic import BaseModel, Field


class ProjectVersionSummaryOut(BaseModel):
    id: str
    version: str
    name: str
    is_default: bool


class ProjectVersionOut(ProjectVersionSummaryOut):
    project_id: str
    description: str
    planned_release_at: str | None
    requirement_count: int
    created_by: str
    created_at: str
    updated_at: str


class ProjectVersionCreateIn(BaseModel):
    version: str = Field(min_length=5, max_length=40)
    name: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=1000)
    planned_release_at: str | None = None
    set_as_default: bool = True


class ProjectVersionUpdateIn(BaseModel):
    name: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=1000)
    planned_release_at: str | None = None
