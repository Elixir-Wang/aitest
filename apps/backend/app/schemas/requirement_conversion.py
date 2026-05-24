from __future__ import annotations

from pydantic import BaseModel, Field


class RequirementConversionInput(BaseModel):
    filename: str
    file_format: str
    candidate_markdown: str
    candidate_summary: str


class RequirementConversionOutput(BaseModel):
    markdown_content: str = ""
    conversion_summary: str = ""
    quality_score: int = Field(default=100, ge=0, le=100)
    warnings: list[str] = Field(default_factory=list)
