from __future__ import annotations

from dataclasses import dataclass

from app.schemas.performance_scenario import QualityGate


@dataclass(frozen=True)
class MeasuredSummary:
    request_count: int
    failure_count: int
    average_response_time_ms: float
    p95_response_time_ms: float
    average_rps: float

    @property
    def failure_ratio(self) -> float:
        return self.failure_count / self.request_count if self.request_count else 0.0


@dataclass(frozen=True)
class GateResult:
    metric: str
    operator: str
    threshold: float | int
    actual: float | int | None
    status: str
    reason: str = ""


@dataclass(frozen=True)
class QualityGateOutcome:
    status: str
    results: list[GateResult]


def evaluate_quality_gate(gate: QualityGate, summary: MeasuredSummary, *, stop_reason: str) -> QualityGateOutcome:
    rules = [
        ("max_fail_ratio", "<=", gate.max_fail_ratio, summary.failure_ratio),
        ("max_average_response_time_ms", "<=", gate.max_average_response_time_ms, summary.average_response_time_ms),
        ("max_p95_response_time_ms", "<=", gate.max_p95_response_time_ms, summary.p95_response_time_ms),
        ("min_average_rps", ">=", gate.min_average_rps, summary.average_rps),
        ("min_request_count", ">=", gate.min_request_count, summary.request_count),
    ]
    configured = [(metric, operator, threshold, actual) for metric, operator, threshold, actual in rules if threshold is not None]
    if not configured:
        return QualityGateOutcome("not_configured", [])
    if stop_reason != "completed" or not summary.request_count:
        reason = "measurement window contains no requests" if not summary.request_count else f"run stopped: {stop_reason}"
        return QualityGateOutcome("not_evaluated", [GateResult(metric, operator, threshold, None, "not_evaluated", reason) for metric, operator, threshold, _ in configured])
    results = [
        GateResult(metric, operator, threshold, actual, "passed" if (actual <= threshold if operator == "<=" else actual >= threshold) else "failed")
        for metric, operator, threshold, actual in configured
    ]
    return QualityGateOutcome("failed" if any(result.status == "failed" for result in results) else "passed", results)


def normalized_exit_code(*, stop_reason: str, quality_status: str) -> int:
    if stop_reason == "circuit_breaker":
        return 11
    if stop_reason in {"engine_error", "validation_error", "timeout"}:
        return 12
    if stop_reason == "manual_stop":
        return 13
    return 10 if quality_status == "failed" else 0
