from app.schemas.performance_scenario import QualityGate
from app.services.performance_testing.quality_gate import MeasuredSummary, evaluate_quality_gate, normalized_exit_code


def test_quality_gate_reports_failed_p95() -> None:
    outcome = evaluate_quality_gate(
        QualityGate(max_fail_ratio=0.01, max_p95_response_time_ms=800),
        MeasuredSummary(request_count=500, failure_count=1, average_response_time_ms=200, p95_response_time_ms=900, average_rps=25),
        stop_reason="completed",
    )

    assert outcome.status == "failed"
    assert {result.metric for result in outcome.results if result.status == "failed"} == {"max_p95_response_time_ms"}


def test_quality_gate_marks_zero_request_run_not_evaluated() -> None:
    outcome = evaluate_quality_gate(
        QualityGate(max_fail_ratio=0.01),
        MeasuredSummary(request_count=0, failure_count=0, average_response_time_ms=0, p95_response_time_ms=0, average_rps=0),
        stop_reason="completed",
    )

    assert outcome.status == "not_evaluated"
    assert outcome.results[0].reason == "measurement window contains no requests"


def test_exit_codes_distinguish_gate_failure_and_circuit_breaker() -> None:
    assert normalized_exit_code(stop_reason="completed", quality_status="failed") == 10
    assert normalized_exit_code(stop_reason="circuit_breaker", quality_status="not_evaluated") == 11
