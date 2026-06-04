from typing import Literal

from pydantic import BaseModel, Field


class RequirementMergeSourceBlockIndex(BaseModel):
    id: str
    title: str
    children: list[str] = Field(default_factory=list)


class RequirementMergeOutlineInput(BaseModel):
    document_name: str
    source_blocks: list[RequirementMergeSourceBlockIndex]


class RequirementMergeOutlineModule(BaseModel):
    id: str
    title: str
    reason: str = ""


class RequirementMergePlacement(BaseModel):
    source_id: str
    target_id: str
    reason: str = ""


class RequirementMergeOutlineOutput(BaseModel):
    outline: list[RequirementMergeOutlineModule] = Field(default_factory=list)
    placements: list[RequirementMergePlacement] = Field(default_factory=list)


class RequirementMergeSectionSourceBlock(BaseModel):
    id: str
    title: str
    children: list[str] = Field(default_factory=list)
    markdown: str


class RequirementMergeSectionInput(BaseModel):
    module_id: str
    module_title: str
    source_blocks: list[RequirementMergeSectionSourceBlock]


class RequirementMergeSectionContent(BaseModel):
    title: str
    content: list[str] = Field(default_factory=list)


class RequirementMergeSectionCoverage(BaseModel):
    source_id: str
    status: Literal["merged", "duplicate", "conflict", "pending_clarification", "discarded"] = "merged"
    reason: str = ""


class RequirementMergeSectionConflict(BaseModel):
    conflict_id: str = ""
    title: str
    conflict_type: str = "contradiction"
    severity: str = "medium"
    source_ids: list[str] = Field(default_factory=list)
    fragment_a: str = ""
    fragment_b: str = ""
    agent_suggestion: str = ""


class RequirementMergeSectionOutput(BaseModel):
    module_id: str
    title: str = ""
    sections: list[RequirementMergeSectionContent] = Field(default_factory=list)
    coverage: list[RequirementMergeSectionCoverage] = Field(default_factory=list)
    conflicts: list[RequirementMergeSectionConflict] = Field(default_factory=list)
