from app.services.performance_testing.analysis_metrics import build_analysis_metrics


def test_analysis_metrics_identifies_degraded_stage_and_capacity_knee() -> None:
    result = build_analysis_metrics(
        {
            "run": {
                "status": "completed",
            },
            "performance_test": {
                "load_config": {
                    "mode": "stress",
                    "stages": [
                        {"name": "100 users", "target_users": 100, "record_metrics": True},
                        {"name": "200 users", "target_users": 200, "record_metrics": True},
                        {"name": "300 users", "target_users": 300, "record_metrics": True},
                    ],
                }
            },
            "summary": {"request_count": 1000},
            "stats": [
                {"sampled_at": "1", "user_count": 100, "request_count": 100, "requests_per_second": 80, "failure_rate": 0, "p95_response_time_ms": 240},
                {"sampled_at": "2", "user_count": 100, "request_count": 200, "requests_per_second": 82, "failure_rate": 0, "p95_response_time_ms": 250},
                {"sampled_at": "3", "user_count": 200, "request_count": 400, "requests_per_second": 150, "failure_rate": 0.002, "p95_response_time_ms": 310},
                {"sampled_at": "4", "user_count": 200, "request_count": 600, "requests_per_second": 156, "failure_rate": 0.002, "p95_response_time_ms": 320},
                {"sampled_at": "5", "user_count": 300, "request_count": 800, "requests_per_second": 175, "failure_rate": 0.04, "p95_response_time_ms": 900},
                {"sampled_at": "6", "user_count": 300, "request_count": 1000, "requests_per_second": 180, "failure_rate": 0.05, "p95_response_time_ms": 980},
            ],
            "failures": [{"count": 9, "sample_status_code": 504, "reason": "request timeout"}],
            "exceptions": [],
        }
    )

    stages = {item["name"]: item for item in result["stage_analysis"]}
    assert stages["100 users"]["status"] == "stable"
    assert stages["300 users"]["status"] == "degraded"
    assert result["capacity_analysis"]["observed_stable_capacity"]["users"] == 200
    assert result["capacity_analysis"]["knee_point"]["between_users"] == [200, 300]


def test_analysis_metrics_does_not_call_fixed_load_system_capacity() -> None:
    result = build_analysis_metrics(
        {
            "run": {"status": "stopped", "termination_reason": "manual_stop"},
            "performance_test": {"load_config": {"mode": "fixed", "users": 10}},
            "summary": {"request_count": 20},
            "stats": [
                {"sampled_at": "1", "user_count": 10, "requests_per_second": 4, "p95_response_time_ms": 600},
                {"sampled_at": "2", "user_count": 10, "requests_per_second": 4, "p95_response_time_ms": 620},
                {"sampled_at": "3", "user_count": 10, "requests_per_second": 4, "p95_response_time_ms": 610},
            ],
        }
    )

    capacity = result["capacity_analysis"]
    assert capacity["observed_stable_capacity"] is None
    assert "固定单阶段负载" in capacity["reason"]
    assert result["test_validity"]["termination_reason"] == "manual_stop"
    assert "run_manually_stopped" in result["test_validity"]["issues"]


def test_analysis_metrics_marks_short_run_as_partial() -> None:
    result = build_analysis_metrics(
        {
            "summary": {"request_count": 1},
            "stats": [{"sampled_at": "1", "request_count": 1, "p95_response_time_ms": 40}],
            "failures": [],
            "exceptions": [],
        }
    )

    assert result["test_validity"]["status"] == "partial"
    assert "too_few_time_series_samples" in result["test_validity"]["issues"]
