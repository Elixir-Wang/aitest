from typing import Literal

from pydantic import BaseModel, Field


class HandledClarification(BaseModel):
    question_id: str
    priority: Literal["P0", "P1", "P2", "P3"]
    question: str = ""
    answer_markdown: str
    insertion_anchor: str = ""
    module_name: str = ""
    module_key: str = ""
    source_excerpt: str = ""
    impact: str = ""


class RequirementFinalizationInput(BaseModel):
    document_name: str
    standard_markdown: str
    preliminary_markdown: str
    handled_clarifications: list[HandledClarification] = Field(default_factory=list)


class RequirementFinalizationOutput(BaseModel):
    final_requirement_markdown: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)
    unresolved_notes: list[str] = Field(default_factory=list)
    merge_notes: list[str] = Field(default_factory=list)


__all__ = [
    "HandledClarification",
    "RequirementFinalizationInput",
    "RequirementFinalizationOutput",
]
