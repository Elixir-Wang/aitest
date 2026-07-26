from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PerformanceAnalysisStatus = Literal[
    "collecting",
    "analyzing",
    "waiting_approval",
    "failed",
    "rejected",
]
PerformanceAnalysisCategory = Literal[
    "performance_config",
    "locust_script",
    "platform_code",
    "external_service",
    "insufficient_evidence",
]
EvidenceLevel = Literal["observed", "derived", "inferred"]


class DiagnosisEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=80)
    level: EvidenceLevel
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=4000)
    reference: str = Field(default="", max_length=1000)


class ProposedChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    target_type: Literal["performance_config", "locust_script", "platform_code"]
    target: str = Field(min_length=1, max_length=500)
    before: Any = None
    after: Any = None
    reason: str = Field(min_length=1, max_length=2000)
    risk_level: Literal["low", "medium", "high"]


class PerformanceFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    severity: Literal["critical", "high", "medium", "low"]
    level: EvidenceLevel
    title: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)
    alternative_hypotheses: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class PerformanceRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    priority: Literal["P0", "P1", "P2", "P3"]
    action: str = Field(min_length=1, max_length=2000)
    expected_effect: str = Field(default="", max_length=2000)
    cost: Literal["low", "medium", "high"]
    verification: str = Field(min_length=1, max_length=2000)
    finding_refs: list[str] = Field(default_factory=list)


class PerformanceDiagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: PerformanceAnalysisCategory
    confidence: float = Field(ge=0, le=1)
    direct_cause: str = Field(min_length=1, max_length=4000)
    root_cause: str = Field(min_length=1, max_length=4000)
    evidence: list[DiagnosisEvidence] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    requires_second_approval: bool = False
    can_auto_rerun: bool = False
    findings: list[PerformanceFinding] = Field(default_factory=list)
    recommendations: list[PerformanceRecommendation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_capabilities(self) -> "PerformanceDiagnosis":
        if self.category in {"external_service", "insufficient_evidence"} and self.proposed_changes:
            raise ValueError("外部服务或证据不足时不能提供可应用修改")
        if self.category == "platform_code" and not self.requires_second_approval:
            raise ValueError("平台源码修改必须二次审批")
        if self.category not in {"performance_config", "locust_script"} and self.can_auto_rerun:
            raise ValueError("只有性能配置或 Locust 脚本问题可以自动重新压测")
        if self.category == "insufficient_evidence" and not self.missing_evidence:
            raise ValueError("证据不足时必须说明缺失证据")
        return self


class PerformanceAnalysisOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    run_id: str
    status: PerformanceAnalysisStatus
    legacy_status: str = ""
    analysis_status: Literal["collecting", "analyzing", "completed", "failed"] = "collecting"
    analysis_stage: str = "evidence_collection"
    repair_status: str = "not_applicable"
    analysis_version: int
    category: str = ""
    summary: str = ""
    direct_cause: str = ""
    root_cause: str = ""
    confidence: float = 0
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    proposal: dict[str, Any] = Field(default_factory=dict)
    metric_snapshot: dict[str, Any] = Field(default_factory=dict)
    report_snapshot: dict[str, Any] = Field(default_factory=dict)
    calculator_version: str = ""
    prompt_version: str = ""
    source_fingerprint: str = ""
    audience: str = "engineer"
    model_name: str = ""
    error_message: str = ""
    created_by: str
    created_at: str
    finished_at: str | None = None
    updated_at: str
    available_actions: list[str] = Field(default_factory=list)
    application_status: str = "not_requested"
    applicable_change_ids: list[str] = Field(default_factory=list)
    selected_change_ids: list[str] = Field(default_factory=list)
    preflight: dict[str, Any] = Field(default_factory=dict)
    applied_script_id: str = ""
    applied_run_id: str = ""
    applied_by: str = ""
    applied_at: str | None = None


class PerformanceAnalysisApplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_ids: list[str] = Field(min_length=1)
