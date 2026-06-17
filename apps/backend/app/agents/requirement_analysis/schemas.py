from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AuxiliaryRequirementDocument(BaseModel):
    filename: str
    markdown_content: str


class RequirementAnalysisRunInput(BaseModel):
    run_id: str = Field(min_length=1)


class RequirementAnalysisAgentInput(BaseModel):
    requirement_name: str
    primary_filename: str
    primary_markdown_content: str
    auxiliary_documents: list[AuxiliaryRequirementDocument] = Field(default_factory=list)


class RequirementClarificationItem(BaseModel):
    id: str = Field(min_length=1)
    priority: Literal["P0", "P1", "P2", "P3"]
    module: str = Field(min_length=1)
    question: str = Field(min_length=1)
    impact: str = Field(min_length=1)


class RequirementAnalysisAgentOutput(BaseModel):
    status: Literal["completed", "needs_clarification"]
    understanding_markdown: str = Field(min_length=1)
    clarification_markdown: str = Field(min_length=1)
    clarification_items: list[RequirementClarificationItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def status_matches_clarifications(self) -> "RequirementAnalysisAgentOutput":
        expected_status = "needs_clarification" if self.clarification_items else "completed"
        if self.status != expected_status:
            raise ValueError("status 必须由 clarification_items 是否为空决定。")
        return self


class RequirementAnalysisRunOutput(BaseModel):
    status: Literal["completed", "needs_clarification"]
    understanding_markdown: str
    clarification_markdown: str
    clarification_items: list[RequirementClarificationItem]
    artifact_paths: dict[str, str] = Field(default_factory=dict)


__all__ = [
    "AuxiliaryRequirementDocument",
    "RequirementAnalysisAgentInput",
    "RequirementAnalysisAgentOutput",
    "RequirementAnalysisRunInput",
    "RequirementAnalysisRunOutput",
    "RequirementClarificationItem",
]
