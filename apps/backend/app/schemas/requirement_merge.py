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


class RequirementSourceFragment(BaseModel):
    fragment_id: str
    mapping_id: str
    source_filename: str
    heading_path: list[str] = Field(default_factory=list)
    fragment_type: Literal[
        "requirement",
        "constraint",
        "interface",
        "state_flow",
        "acceptance",
        "background",
        "attachment",
        "non_requirement",
    ] = "requirement"
    content_hash: str
    text: str
    markdown_block: str


class RequirementFragmentDecision(BaseModel):
    fragment_id: str
    mapping_id: str
    coverage_status: Literal["merged", "duplicate", "conflict", "pending_clarification", "discarded"]
    target_module: str = ""
    target_heading: str = ""
    merged_requirement_key: str = ""
    related_conflict_key: str = ""
    related_clarification_key: str = ""
    reason: str


class RequirementMergeAuditOutput(BaseModel):
    status: Literal["ready_for_draft", "conflict", "failed"]
    merge_summary: str
    affected_modules: list[str] = Field(default_factory=list)
    fragment_decisions: list[RequirementFragmentDecision] = Field(default_factory=list)
    conflicts: list[dict] = Field(default_factory=list)
    clarification_items: list[dict] = Field(default_factory=list)


class RequirementFragmentClassification(BaseModel):
    fragment_id: str
    business_module: str
    semantic_key: str
    fragment_role: str
    summary: str
    confidence: float = 0


class RequirementFragmentClassificationBatch(BaseModel):
    classifications: list[RequirementFragmentClassification] = Field(default_factory=list)


class RequirementFragmentCluster(BaseModel):
    cluster_id: str
    business_module: str
    semantic_key: str
    fragment_role: str
    fragment_ids: list[str]


class RequirementClusterDecisionItem(BaseModel):
    fragment_id: str
    coverage_status: Literal["merged", "duplicate", "conflict", "pending_clarification", "discarded"]
    target_module: str = ""
    target_heading: str = ""
    covered_by_fragment_id: str = ""
    related_conflict_key: str = ""
    related_clarification_key: str = ""
    reason: str


class RequirementClusterDecision(BaseModel):
    cluster_id: str
    decision: Literal["merge", "duplicate", "conflict", "pending_clarification", "discard"]
    canonical_meaning: str = ""
    fragment_decisions: list[RequirementClusterDecisionItem] = Field(default_factory=list)
    conflicts: list[dict] = Field(default_factory=list)
    clarification_items: list[dict] = Field(default_factory=list)


class RequirementClusterDecisionItemRaw(BaseModel):
    fragment_id: str = ""
    coverage_status: str = ""
    target_module: str = ""
    target_heading: str = ""
    covered_by_fragment_id: str = ""
    related_conflict_key: str = ""
    related_clarification_key: str = ""
    reason: str = ""


class RequirementClusterDecisionRaw(BaseModel):
    cluster_id: str = ""
    decision: str = ""
    canonical_meaning: str = ""
    fragment_decisions: list[RequirementClusterDecisionItemRaw] = Field(default_factory=list)
    conflicts: list[dict] = Field(default_factory=list)
    clarification_items: list[dict] = Field(default_factory=list)


class RequirementSectionBlock(BaseModel):
    type: Literal["paragraph", "bullet_list", "table", "source_block_ref", "pending_clarification_ref"]
    content: str = ""
    items: list[str] = Field(default_factory=list)
    fragment_id: str = ""


class RequirementSectionMergeOutput(BaseModel):
    section_key: str
    blocks: list[RequirementSectionBlock] = Field(default_factory=list)
    covered_fragment_ids: list[str] = Field(default_factory=list)


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
