from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProposedCaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    expected_status_code: int = Field(ge=100, le=599)
    actual_status_code: int = Field(ge=100, le=599)


class RepairProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: Literal["test_script"]
    action: Literal[
        "modify_assertion",
        "modify_request_data",
        "modify_fixture",
        "inspect_interface",
        "confirm_contract",
        "no_change",
    ]
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    proposed_changes: list[str] = Field(default_factory=list)
    case_updates: list[ProposedCaseUpdate] = Field(default_factory=list)
    script_repair_allowed: bool = False


class FailureIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failure_ids: list[str] = Field(min_length=1)
    classification: Literal[
        "test_code_issue",
        "test_data_issue",
        "environment_issue",
        "interface_bug",
        "contract_ambiguity",
        "unknown",
    ]
    confidence: float = Field(ge=0, le=1)
    root_cause: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    repairable: bool


class FailureDiagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    issues: list[FailureIssue] = Field(min_length=1)
    proposal: RepairProposal | None = None


class CaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    changes: dict[str, Any]
    reason: str = Field(min_length=1)


class RepairResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    case_updates: list[CaseUpdate] = Field(default_factory=list)
    changed_source_files: list[str] = Field(default_factory=list)
    unresolved_failure_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
