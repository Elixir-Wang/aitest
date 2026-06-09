from typing import Literal

from pydantic import BaseModel, Field


class RequirementAnalysisInput(BaseModel):
    project_id: str
    document_id: str
    document_name: str
    primary_mapping_id: str = ""
    primary_filename: str = ""
    primary_markdown_content: str = ""


class RequirementAnalysisModule(BaseModel):
    module_key: str
    module_name: str
    summary: str
    business_objects: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    state_flows: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class RequirementEvidenceReference(BaseModel):
    mapping_id: str
    filename: str
    excerpt: str
    section_hint: str = ""


class RequirementClarificationOption(BaseModel):
    id: str
    label: str
    answer_markdown: str
    rationale: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"


class RequirementClarificationQuestion(BaseModel):
    id: str
    module_key: str
    module_name: str
    question: str = Field(
        description=(
            "直接面向人工确认的问题。必须把需要确认的字段直接问出来；"
            "不要拆出“当前缺口”“缺失说明”等额外字段或解释段。"
        )
    )
    impact: str = Field(description="不确认会造成的下游设计、开发、测试、日志或状态处理影响。")
    dimension: Literal[
        "boundary_value",
        "exception_path",
        "state_flow",
        "permission",
        "data_dependency",
        "message",
        "validation_rule",
        "concurrency",
        "time_related",
        "data_consistency",
        "scope",
        "other",
    ]
    severity: Literal["blocker", "major", "minor"] = "major"
    source_excerpt: str = ""
    recommended_options: list[RequirementClarificationOption] = Field(default_factory=list, max_length=2)


class RequirementAppliedSupplement(BaseModel):
    id: str
    source_question_id: str
    module_key: str
    module_name: str
    insertion_anchor: str
    inserted_markdown: str
    evidence: RequirementEvidenceReference
    reason: str
    confidence: Literal["high", "medium"]


class RequirementUnresolvedFinding(BaseModel):
    id: str
    module_key: str
    module_name: str
    issue_type: Literal[
        "missing_answer",
        "conflict",
        "out_of_scope",
        "weak_evidence",
        "source_unclear",
        "other",
    ]
    question: str = Field(
        description=(
            "直接面向人工确认的问题。必须把需要确认的字段直接问出来；"
            "不要拆出“当前缺口”“缺失说明”等额外字段或解释段。"
        )
    )
    impact: str = Field(description="不确认会造成的下游设计、开发、测试、日志或状态处理影响。")
    severity: Literal["blocker", "major", "minor"] = "major"
    primary_excerpt: str = ""
    evidence: list[RequirementEvidenceReference] = Field(default_factory=list)
    recommended_options: list[RequirementClarificationOption] = Field(default_factory=list, max_length=2)


class RequirementCoverageAuditItem(BaseModel):
    module_key: str
    module_name: str
    source_excerpt: str
    analysis_status: Literal[
        "analyzed",
        "pending_clarification",
        "not_testable",
        "missing_detail",
    ]
    reason: str


class RequirementQualityGate(BaseModel):
    result: Literal["passed", "warning", "blocked"]
    testability_score: int = Field(ge=0, le=100)
    blocking_issues: list[str] = Field(default_factory=list)
    warning_issues: list[str] = Field(default_factory=list)
    passed_checks: list[str] = Field(default_factory=list)


class RequirementMaturityAssessment(BaseModel):
    level: Literal["RA0", "RA1", "RA2", "RA3", "RA4", "RA5"]
    label: str
    reason: str
    evidence: list[str] = Field(default_factory=list)


class RequirementGapItem(BaseModel):
    category: Literal[
        "problem_statement",
        "stakeholder",
        "scope",
        "business_rule",
        "acceptance_criteria",
        "data",
        "permission",
        "integration",
        "non_functional",
        "constraint",
        "other",
    ]
    description: str
    impact: str
    severity: Literal["blocker", "major", "minor"] = "major"


class RequirementAssumptionItem(BaseModel):
    description: str
    validation_needed: str
    risk: str


class RequirementAnalysisOutput(BaseModel):
    status: Literal["completed", "needs_clarification", "blocked"]
    analysis_summary: str
    preliminary_requirement_markdown: str = ""
    applied_supplements: list[RequirementAppliedSupplement] = Field(default_factory=list)
    maturity_assessment: RequirementMaturityAssessment | None = None
    key_gaps: list[RequirementGapItem] = Field(default_factory=list)
    assumptions: list[RequirementAssumptionItem] = Field(default_factory=list)
    modules: list[RequirementAnalysisModule] = Field(default_factory=list)
    clarification_questions: list[RequirementClarificationQuestion | RequirementUnresolvedFinding] = Field(default_factory=list)
    conflicts: list[RequirementUnresolvedFinding] = Field(default_factory=list)
    coverage_audit: list[RequirementCoverageAuditItem] = Field(default_factory=list)
    quality_gate: RequirementQualityGate
    next_actions: list[str] = Field(default_factory=list)


__all__ = [
    "RequirementAnalysisInput",
    "RequirementAnalysisModule",
    "RequirementAnalysisOutput",
    "RequirementAppliedSupplement",
    "RequirementAssumptionItem",
    "RequirementClarificationOption",
    "RequirementClarificationQuestion",
    "RequirementCoverageAuditItem",
    "RequirementEvidenceReference",
    "RequirementGapItem",
    "RequirementMaturityAssessment",
    "RequirementQualityGate",
    "RequirementUnresolvedFinding",
]
