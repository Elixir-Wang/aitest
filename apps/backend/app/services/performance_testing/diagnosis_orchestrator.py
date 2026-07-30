from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.agents.performance_testing.diagnosis.service import PROMPT_VERSION, diagnose_performance
from app.schemas.performance_analysis import (
    DiagnosisAttempt,
    DiagnosisGenerationResult,
    GenerationWarning,
    PerformanceDiagnosis,
)
from app.services.performance_testing.diagnosis_validation import validate_diagnosis_references


DiagnosisCallable = Callable[..., tuple[PerformanceDiagnosis, str]]


def generate_validated_diagnosis(
    evidence: dict[str, Any],
    metric_snapshot: dict[str, Any],
    *,
    diagnose: DiagnosisCallable = diagnose_performance,
) -> DiagnosisGenerationResult:
    analysis_input = {**evidence, "metric_snapshot": metric_snapshot}
    attempts: list[DiagnosisAttempt] = []
    started_at = _now()
    try:
        diagnosis, model_name = diagnose(analysis_input)
    except ValidationError:
        attempts.append(
            _attempt(
                attempt=1,
                attempt_type="primary",
                status="invalid_schema",
                started_at=started_at,
                error_code="AI_DIAGNOSIS_SCHEMA_INVALID",
            )
        )
        return _repair_schema(analysis_input, attempts, diagnose)
    except Exception as exc:
        error_code = _provider_error_code(exc)
        attempts.append(
            _attempt(
                attempt=1,
                attempt_type="primary",
                status="provider_error",
                started_at=started_at,
                error_code=error_code,
            )
        )
        return _fallback(attempts, error_code, _provider_warning(error_code))

    validation = validate_diagnosis_references(metric_snapshot, diagnosis)
    if validation.valid:
        attempts.append(
            _attempt(
                attempt=1,
                attempt_type="primary",
                status="completed",
                started_at=started_at,
                model_name=model_name,
            )
        )
        return DiagnosisGenerationResult(
            diagnosis=diagnosis,
            model_name=model_name,
            generation_mode="ai_primary",
            attempts=attempts,
        )

    attempts.append(
        _attempt(
            attempt=1,
            attempt_type="primary",
            status="invalid_references",
            started_at=started_at,
            model_name=model_name,
            error_code="AI_DIAGNOSIS_INVALID_REFERENCES",
            invalid_evidence_refs=validation.unknown_evidence_refs,
            invalid_finding_refs=validation.unknown_finding_refs,
        )
    )
    return _repair_references(analysis_input, metric_snapshot, diagnosis, attempts, diagnose, model_name)


def _repair_references(
    analysis_input: dict[str, Any],
    metric_snapshot: dict[str, Any],
    diagnosis: PerformanceDiagnosis,
    attempts: list[DiagnosisAttempt],
    diagnose: DiagnosisCallable,
    initial_model_name: str,
) -> DiagnosisGenerationResult:
    validation = validate_diagnosis_references(metric_snapshot, diagnosis)
    repair_context = {
        "previous_diagnosis": diagnosis.model_dump(mode="json"),
        "unknown_evidence_refs": validation.unknown_evidence_refs,
        "unknown_finding_refs": validation.unknown_finding_refs,
    }
    return _run_repair(
        analysis_input,
        metric_snapshot,
        repair_context,
        attempts,
        diagnose,
        initial_model_name,
    )


def _repair_schema(
    analysis_input: dict[str, Any],
    attempts: list[DiagnosisAttempt],
    diagnose: DiagnosisCallable,
) -> DiagnosisGenerationResult:
    return _run_repair(
        analysis_input,
        analysis_input.get("metric_snapshot") or {},
        {
            "previous_diagnosis": {},
            "unknown_evidence_refs": [],
            "unknown_finding_refs": [],
            "schema_error": "PerformanceDiagnosis validation failed",
        },
        attempts,
        diagnose,
        "",
    )


def _run_repair(
    analysis_input: dict[str, Any],
    metric_snapshot: dict[str, Any],
    repair_context: dict[str, Any],
    attempts: list[DiagnosisAttempt],
    diagnose: DiagnosisCallable,
    initial_model_name: str,
) -> DiagnosisGenerationResult:
    started_at = _now()
    try:
        diagnosis, model_name = diagnose(analysis_input, repair_context=repair_context)
    except ValidationError:
        attempts.append(
            _attempt(
                attempt=2,
                attempt_type="semantic_repair",
                status="invalid_schema",
                started_at=started_at,
                model_name=initial_model_name,
                error_code="AI_DIAGNOSIS_SCHEMA_INVALID",
            )
        )
        return _fallback(
            attempts,
            "AI_DIAGNOSIS_SCHEMA_INVALID",
            "AI 深度诊断未通过结构校验，当前展示基础性能报告。",
            initial_model_name,
        )
    except Exception as exc:
        error_code = _provider_error_code(exc)
        attempts.append(
            _attempt(
                attempt=2,
                attempt_type="semantic_repair",
                status="provider_error",
                started_at=started_at,
                model_name=initial_model_name,
                error_code=error_code,
            )
        )
        return _fallback(attempts, error_code, _provider_warning(error_code), initial_model_name)

    validation = validate_diagnosis_references(metric_snapshot, diagnosis)
    if validation.valid:
        attempts.append(
            _attempt(
                attempt=2,
                attempt_type="semantic_repair",
                status="completed",
                started_at=started_at,
                model_name=model_name,
            )
        )
        return DiagnosisGenerationResult(
            diagnosis=diagnosis,
            model_name=model_name,
            generation_mode="ai_repaired",
            attempts=attempts,
        )

    attempts.append(
        _attempt(
            attempt=2,
            attempt_type="semantic_repair",
            status="invalid_references",
            started_at=started_at,
            model_name=model_name,
            error_code="AI_DIAGNOSIS_INVALID_REFERENCES",
            invalid_evidence_refs=validation.unknown_evidence_refs,
            invalid_finding_refs=validation.unknown_finding_refs,
        )
    )
    return _fallback(
        attempts,
        "AI_DIAGNOSIS_INVALID_REFERENCES",
        "AI 深度诊断未通过证据引用校验，当前展示基础性能报告。",
        model_name,
    )


def _attempt(
    *,
    attempt: int,
    attempt_type: str,
    status: str,
    started_at: str,
    model_name: str = "",
    error_code: str = "",
    invalid_evidence_refs: list[str] | None = None,
    invalid_finding_refs: list[str] | None = None,
) -> DiagnosisAttempt:
    return DiagnosisAttempt(
        attempt=attempt,
        attempt_type=attempt_type,
        status=status,
        model_name=model_name,
        prompt_version=PROMPT_VERSION,
        error_code=error_code,
        invalid_evidence_refs=invalid_evidence_refs or [],
        invalid_finding_refs=invalid_finding_refs or [],
        started_at=started_at,
        finished_at=_now(),
    )


def _fallback(
    attempts: list[DiagnosisAttempt],
    error_code: str,
    message: str,
    model_name: str = "",
) -> DiagnosisGenerationResult:
    return DiagnosisGenerationResult(
        generation_mode="deterministic_fallback",
        model_name=model_name,
        attempts=attempts,
        warnings=[GenerationWarning(code=error_code, message=message)],
    )


def _provider_error_code(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    text = f"{type(exc).__name__} {exc}".lower()
    if status_code == 429 or "ratelimit" in text or "rate_limit" in text or "rate limit" in text:
        return "AI_PROVIDER_RATE_LIMITED"
    if "timeout" in text or "timed out" in text:
        return "AI_PROVIDER_TIMEOUT"
    if "api key" in text or "model configuration" in text or "模型配置" in text:
        return "AI_MODEL_CONFIGURATION_INVALID"
    return "AI_PROVIDER_UNAVAILABLE"


def _provider_warning(error_code: str) -> str:
    messages = {
        "AI_PROVIDER_RATE_LIMITED": "AI 模型接口触发频率限制，当前展示基础性能报告。",
        "AI_PROVIDER_TIMEOUT": "AI 模型接口请求超时，当前展示基础性能报告。",
        "AI_MODEL_CONFIGURATION_INVALID": "AI 模型配置不可用，当前展示基础性能报告。",
    }
    return messages.get(error_code, "AI 深度诊断暂不可用，当前展示基础性能报告。")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["generate_validated_diagnosis"]
