from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RequirementMergeSourceFile(BaseModel):
    mapping_id: str
    original_filename: str
    markdown_content: str
    conversion_status: str
    mapping_status: str


class RequirementMergeBaseVersion(BaseModel):
    id: str
    version_no: int
    markdown_content: str


class RequirementMergeResolvedConflict(BaseModel):
    id: str
    title: str
    resolution: str
    resolution_type: str


class RequirementMergeInput(BaseModel):
    project_id: str
    document_id: str
    document_name: str
    merge_mode: Literal["initial", "incremental", "rebuild"]
    base_version: RequirementMergeBaseVersion | None = None
    source_files: list[RequirementMergeSourceFile]
    resolved_conflicts: list[RequirementMergeResolvedConflict] = Field(default_factory=list)


class RequirementCoverageItem(BaseModel):
    mapping_id: str
    source_heading: str = ""
    source_excerpt: str
    target_module: str = ""
    target_heading: str = ""
    coverage_status: Literal["merged", "duplicate", "conflict", "pending_clarification", "discarded"]
    reason: str


class RequirementMergeConflictOut(BaseModel):
    title: str
    conflict_type: str = "contradiction"
    severity: str = "medium"
    source_refs: list[dict] = Field(default_factory=list)
    fragment_a: str
    fragment_b: str
    agent_suggestion: str = ""


class RequirementMergeOutput(BaseModel):
    status: Literal["merged", "conflict", "preview"]
    markdown_content: str = ""
    markdown_preview: str = ""
    merge_summary: str
    diff_summary: str = ""
    affected_modules: list[str] = Field(default_factory=list)
    source_file_ids: list[str] = Field(default_factory=list)
    coverage_items: list[RequirementCoverageItem] = Field(default_factory=list)
    conflicts: list[RequirementMergeConflictOut] = Field(default_factory=list)

