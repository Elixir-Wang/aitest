from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DiagnosisValidationResult:
    unknown_evidence_refs: list[str]
    unknown_finding_refs: list[str]

    @property
    def valid(self) -> bool:
        return not self.unknown_evidence_refs and not self.unknown_finding_refs


class DiagnosisReferenceError(ValueError):
    def __init__(self, validation: DiagnosisValidationResult):
        self.validation = validation
        messages: list[str] = []
        if validation.unknown_evidence_refs:
            messages.append(f"性能诊断引用了未知证据：{', '.join(validation.unknown_evidence_refs)}")
        if validation.unknown_finding_refs:
            messages.append(f"性能建议引用了未知 finding：{', '.join(validation.unknown_finding_refs)}")
        super().__init__("；".join(messages))


def validate_diagnosis_references(
    metric_snapshot: dict[str, Any],
    diagnosis: Any,
) -> DiagnosisValidationResult:
    evidence_ids = {
        str(item.get("evidence_id"))
        for item in metric_snapshot.get("evidence_index", [])
        if isinstance(item, dict) and item.get("evidence_id")
    }
    finding_ids = {str(item.id) for item in diagnosis.findings}
    unknown_evidence_refs = sorted(
        {
            str(reference)
            for finding in diagnosis.findings
            for reference in finding.evidence_refs
            if str(reference) not in evidence_ids
        }
    )
    unknown_finding_refs = sorted(
        {
            str(reference)
            for recommendation in diagnosis.recommendations
            for reference in recommendation.finding_refs
            if str(reference) not in finding_ids
        }
    )
    return DiagnosisValidationResult(
        unknown_evidence_refs=unknown_evidence_refs,
        unknown_finding_refs=unknown_finding_refs,
    )


def require_valid_diagnosis_references(metric_snapshot: dict[str, Any], diagnosis: Any) -> None:
    validation = validate_diagnosis_references(metric_snapshot, diagnosis)
    if not validation.valid:
        raise DiagnosisReferenceError(validation)


__all__ = [
    "DiagnosisReferenceError",
    "DiagnosisValidationResult",
    "require_valid_diagnosis_references",
    "validate_diagnosis_references",
]
