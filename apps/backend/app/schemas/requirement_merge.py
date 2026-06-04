from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class RequirementMergeSourceFile(BaseModel):
    mapping_id: str
    original_filename: str
    markdown_content: str


class RequirementMergeBaseVersion(BaseModel):
    id: str
    version_no: int
    markdown_content: str


class RequirementMergeResolvedConflict(BaseModel):
    id: str
    title: str
    resolution: str
    resolution_type: str


class RequirementSourceBlock(BaseModel):
    block_id: str
    source_code: str
    mapping_id: str
    source_file: str
    original_heading: str
    heading_path: list[str] = Field(default_factory=list)
    markdown: str
    sub_headings: list[str] = Field(default_factory=list)


class SourceOutlineNode(BaseModel):
    node_id: str
    document_code: str
    mapping_id: str
    source_file: str
    level: int
    title: str
    heading_path: list[str] = Field(default_factory=list)
    content_markdown: str
    plain_text: str
    own_body_markdown: str = ""
    own_body_plain_text: str = ""
    sub_headings: list[str] = Field(default_factory=list)
    node_role: str = "content"
    must_assign: bool = True
    children: list["SourceOutlineNode"] = Field(default_factory=list)


class SourceOutlineDocument(BaseModel):
    document_code: str
    mapping_id: str
    source_file: str
    nodes: list[SourceOutlineNode] = Field(default_factory=list)


class TargetOutlineSection(BaseModel):
    section_id: str
    parent_id: str = ""
    level: int
    title: str
    reason: str = ""
    source_node_ids: list[str] = Field(default_factory=list)
    children: list["TargetOutlineSection"] = Field(default_factory=list)


class OutlineAssignment(BaseModel):
    source_node_id: str
    target_section_id: str = ""
    assignment_type: Literal[
        "primary",
        "reference",
        "appendix",
        "discarded_non_requirement",
        "pending_clarification",
    ]
    reason: str


class OutlineSectionBlock(BaseModel):
    type: Literal[
        "paragraph",
        "bullet_list",
        "table",
        "source_node_ref",
        "pending_clarification_ref",
        "conflict_ref",
    ]
    content: str = ""
    items: list[str] = Field(default_factory=list)
    source_node_id: str = ""
    conflict_id: str = ""


class OutlineSectionDecision(BaseModel):
    section_id: str
    source_node_id: str
    status: Literal[
        "merged",
        "duplicate",
        "conflict",
        "pending_clarification",
        "discarded",
    ]
    target_heading: str = ""
    covered_by_source_node_id: str = ""
    conflict_id: str = ""
    reason: str


class OutlineMergeConflict(BaseModel):
    conflict_id: str
    title: str
    conflict_type: str = "contradiction"
    severity: str = "medium"
    source_node_ids: list[str] = Field(default_factory=list)
    fragment_a: str = ""
    fragment_b: str = ""
    agent_suggestion: str = ""


class OutlineSectionMergeResult(BaseModel):
    section_id: str
    blocks: list[OutlineSectionBlock] = Field(default_factory=list)
    decisions: list[OutlineSectionDecision] = Field(default_factory=list)
    conflicts: list[OutlineMergeConflict] = Field(default_factory=list)


class OutlineMergeArtifacts(BaseModel):
    source_documents: list[SourceOutlineDocument] = Field(default_factory=list)
    target_outline: list[TargetOutlineSection] = Field(default_factory=list)
    assignments: list[OutlineAssignment] = Field(default_factory=list)
    section_results: list[OutlineSectionMergeResult] = Field(default_factory=list)
    quality_result: Literal["passed", "warning", "failed", "blocked"] = "failed"
    quality_issues: list[str] = Field(default_factory=list)
    stage_errors: list[str] = Field(default_factory=list)


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
    fragment_id: str = ""
    block_id: str = ""
    business_module: str
    semantic_key: str
    fragment_role: str = ""
    block_role: str = ""
    summary: str
    confidence: float = 0

    def model_post_init(self, __context) -> None:
        if not self.fragment_id and self.block_id:
            self.fragment_id = self.block_id
        if not self.block_id and self.fragment_id:
            self.block_id = self.fragment_id
        if not self.fragment_role and self.block_role:
            self.fragment_role = self.block_role
        if not self.block_role and self.fragment_role:
            self.block_role = self.fragment_role


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

    @field_validator(
        "fragment_id",
        "coverage_status",
        "target_module",
        "target_heading",
        "covered_by_fragment_id",
        "related_conflict_key",
        "related_clarification_key",
        "reason",
        mode="before",
    )
    @classmethod
    def _none_to_empty_string(cls, value):
        return "" if value is None else value


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


class RequirementSectionBlockRaw(BaseModel):
    type: str = ""
    content: Any = ""
    items: Any = Field(default_factory=list)
    fragment_id: Any = ""


class RequirementSectionMergeOutputRaw(BaseModel):
    section_key: str = ""
    blocks: list[RequirementSectionBlockRaw] = Field(default_factory=list)
    covered_fragment_ids: list[Any] = Field(default_factory=list)


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
    source_block_id: str = ""
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
