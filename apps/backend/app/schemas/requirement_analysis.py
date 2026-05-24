from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RequirementAnalysisInput(BaseModel):
    project_id: str
    document_id: str
    document_name: str
    version_id: str
    version_no: int
    markdown_content: str


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


class RequirementClarificationQuestion(BaseModel):
    id: str
    module_key: str
    module_name: str
    question: str
    reason: str
    impact: str
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


class RequirementAnalysisOutput(BaseModel):
    status: Literal["completed", "needs_clarification", "blocked"]
    analysis_summary: str
    modules: list[RequirementAnalysisModule] = Field(default_factory=list)
    clarification_questions: list[RequirementClarificationQuestion] = Field(default_factory=list)
    coverage_audit: list[RequirementCoverageAuditItem] = Field(default_factory=list)
    quality_gate: RequirementQualityGate
    next_actions: list[str] = Field(default_factory=list)
