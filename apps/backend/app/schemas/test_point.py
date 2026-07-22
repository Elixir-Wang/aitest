from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TestPointUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    module: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=40)
    priority: Literal["P0", "P1", "P2", "P3"] | None = None
    description: str | None = None
    preconditions: list[str] | None = None
    verification_points: list[str] | None = None
    source_refs: list[str] | None = None
    notes: str | None = None

    @field_validator("title", "module", "category", "description", "notes", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class TestPointMarkdownUpdateIn(BaseModel):
    markdown_content: str = Field(min_length=1)


class TestPointRequirementObligationOut(BaseModel):
    obligation_key: str
    source_section: str
    statement: str


class TestPointOut(BaseModel):
    id: str
    project_id: str
    document_id: str
    requirement_version_id: str
    generation_run_id: str
    title: str
    module: str
    category: str
    priority: str
    description: str
    preconditions: list[str]
    verification_points: list[str]
    source_refs: list[str]
    requirement_obligations: list[TestPointRequirementObligationOut]
    notes: str
    created_at: str
    updated_at: str


class TestPointGenerationRunOut(BaseModel):
    id: str
    task_id: str
    requirement_version_id: str
    status: str
    input_snapshot: dict
    error_message: str
    created_at: str
    finished_at: str | None = None


class TestPointCoverageSummaryOut(BaseModel):
    status: Literal["pending", "complete", "incomplete", "invalid"]
    obligation_count: int
    covered_obligation_count: int
    missing_obligations: list[TestPointRequirementObligationOut]
    unsupported_assumptions: list[str]
    supplement_round: int


class TestPointOverviewOut(BaseModel):
    requirement_version_id: str | None
    requirement_version_no: int | None
    run: TestPointGenerationRunOut | None
    points: list[TestPointOut]
    markdown_content: str
    coverage_summary: TestPointCoverageSummaryOut
