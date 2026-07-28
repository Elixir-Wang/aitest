import pytest

from app.schemas.performance_analysis import PerformanceDiagnosis
from app.services.performance_testing.metric_snapshot_service import build_metric_snapshot, build_report_snapshot


def test_metric_snapshot_fails_when_performance_goal_is_not_met() -> None:
    snapshot = build_metric_snapshot(
        {
            "run": {"id": "perfrun-1", "status": "completed"},
            "summary": {
                "request_count": 1000,
                "failure_count": 20,
                "failure_rate": 0.02,
                "requests_per_second": 80,
                "average_response_time_ms": 220,
                "p50_response_time_ms": 100,
                "p95_response_time_ms": 600,
                "p99_response_time_ms": 900,
            },
            "stats": [
                {"sampled_at": "1", "request_count": 300, "requests_per_second": 70, "p95_response_time_ms": 500},
                {"sampled_at": "2", "request_count": 700, "requests_per_second": 80, "p95_response_time_ms": 550},
                {"sampled_at": "3", "request_count": 1000, "requests_per_second": 82, "p95_response_time_ms": 600},
            ],
            "performance_test": {
                "performance_goal": {
                    "max_fail_ratio": 0.01,
                    "max_average_response_time_ms": 500,
                    "max_p95_response_time_ms": 500,
                    "min_average_rps": 60,
                }
            },
            "missing_evidence": [],
        }
    )

    assert snapshot["verdict"] == "fail"
    assert snapshot["quality"]["status"] == "complete"
    assert {item["metric"]: item["status"] for item in snapshot["objectives"]} == {
        "failure_rate": "failed",
        "average_response_time_ms": "passed",
        "p95_response_time_ms": "failed",
        "requests_per_second": "passed",
    }
    assert snapshot["capacity"]["stable_throughput"] == 81.0


def test_metric_snapshot_does_not_invent_missing_percentile() -> None:
    snapshot = build_metric_snapshot(
        {
            "run": {"id": "perfrun-1", "status": "completed"},
            "summary": {"request_count": 10, "average_response_time_ms": 100},
            "stats": [],
            "performance_test": {"performance_goal": {"max_p95_response_time_ms": 500}},
            "missing_evidence": [],
        }
    )

    assert snapshot["aggregate"]["p95_response_time_ms"] is None
    assert snapshot["verdict"] == "indeterminate"
    assert snapshot["quality"]["status"] == "partial"


def test_manual_stop_is_a_known_run_limit_not_an_unknown_failure() -> None:
    snapshot = build_metric_snapshot(
        {
            "run": {
                "id": "perfrun-1",
                "status": "stopped",
                "termination_reason": "manual_stop",
                "termination_label": "人工停止",
                "load_config": {"measurement_duration_seconds": 60, "users": 10},
                "started_at": "2026-07-28T15:35:33",
                "finished_at": "2026-07-28T15:36:29",
            },
            "summary": {
                "request_count": 232,
                "failure_count": 0,
                "failure_rate": 0,
                "requests_per_second": 4.2,
                "average_response_time_ms": 238.78,
                "p95_response_time_ms": 640,
            },
            "stats": [
                {"sampled_at": "1", "user_count": 10, "request_count": 80, "requests_per_second": 4.1, "p95_response_time_ms": 660},
                {"sampled_at": "2", "user_count": 10, "request_count": 160, "requests_per_second": 4.3, "p95_response_time_ms": 650},
                {"sampled_at": "3", "user_count": 10, "request_count": 232, "requests_per_second": 4.2, "p95_response_time_ms": 640},
            ],
            "performance_test": {
                "load_config": {"mode": "fixed", "users": 10},
                "performance_goal": {
                    "max_fail_ratio": 0,
                    "max_average_response_time_ms": 3000,
                },
            },
            "missing_evidence": [],
        }
    )

    assert snapshot["verdict"] == "conditional_pass"
    assert snapshot["quality"]["termination_reason"] == "manual_stop"
    assert snapshot["quality"]["termination_label"] == "人工停止"
    assert snapshot["quality"]["actual_duration_seconds"] == 56
    assert snapshot["quality"]["configured_duration_seconds"] == 60
    assert snapshot["quality"]["duration_complete"] is False
    assert snapshot["quality"]["issues"] == ["run_manually_stopped"]
    assert snapshot["capacity_analysis"]["observed_stable_capacity"] is None

    diagnosis = PerformanceDiagnosis.model_validate(
        {
            "category": "insufficient_evidence",
            "confidence": 0.9,
            "direct_cause": "固定负载目标已满足",
            "root_cause": "容量上限未评估",
            "evidence": [],
            "proposed_changes": [],
            "missing_evidence": ["capacity_analysis"],
        }
    )
    report = build_report_snapshot(snapshot, diagnosis)
    assert "手动停止" in report["executive_summary"]
    assert "不代表运行异常" in report["executive_summary"]
    assert "实际运行 56 秒，配置时长 60 秒" in report["executive_summary"]
    assert "固定单阶段负载" in report["capacity_summary"]


def test_report_snapshot_reuses_structured_diagnosis() -> None:
    metric_snapshot = {
        "verdict": "fail",
        "aggregate": {"request_count": 10, "failure_rate": 1, "requests_per_second": 2},
        "capacity": {"stable_throughput": None},
        "objectives": [{"evidence_id": "objective:failure_rate"}],
    }
    diagnosis = PerformanceDiagnosis.model_validate(
        {
            "category": "performance_config",
            "confidence": 0.95,
            "direct_cause": "请求全部失败",
            "root_cause": "请求配置缺少必填字段",
            "evidence": [
                {"source": "run", "level": "observed", "title": "失败率", "detail": "failure_rate=1"}
            ],
            "proposed_changes": [],
            "missing_evidence": [],
        }
    )

    report = build_report_snapshot(metric_snapshot, diagnosis)

    assert report["verdict"] == "fail"
    assert report["findings"][0]["evidence_refs"] == ["diagnosis:1"]
    assert report["diagnosis_evidence"][0]["evidence_id"] == "diagnosis:1"


def test_report_snapshot_rejects_unknown_metric_evidence_reference() -> None:
    diagnosis = PerformanceDiagnosis.model_validate(
        {
            "category": "external_service",
            "confidence": 0.6,
            "direct_cause": "尾延迟升高",
            "root_cause": "需要更多服务端证据",
            "evidence": [],
            "proposed_changes": [],
            "missing_evidence": ["service_metrics"],
            "findings": [
                {
                    "id": "finding-1",
                    "severity": "medium",
                    "level": "inferred",
                    "title": "尾延迟升高",
                    "statement": "可能存在外部服务瓶颈",
                    "confidence": 0.6,
                    "evidence_refs": ["metric:unknown"],
                    "alternative_hypotheses": [],
                    "missing_evidence": ["service_metrics"],
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="未知证据"):
        build_report_snapshot({"verdict": "indeterminate", "evidence_index": []}, diagnosis)
