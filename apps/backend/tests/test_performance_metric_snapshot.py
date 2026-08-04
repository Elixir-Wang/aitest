import pytest

from app.schemas.performance_analysis import PerformanceDiagnosis
from app.services.performance_testing.diagnosis_validation import (
    DiagnosisReferenceError,
    validate_diagnosis_references,
)
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


def test_metric_snapshot_evaluates_sse_percentile_goals_from_independent_summary() -> None:
    snapshot = build_metric_snapshot(
        {
            "run": {"id": "perfrun-sse", "status": "completed"},
            "summary": {
                "request_count": 20,
                "failure_count": 0,
                "failure_rate": 0,
                "requests_per_second": 2,
                "average_response_time_ms": 2000,
            },
            "stats": [{"sampled_at": "1", "request_count": 20, "requests_per_second": 2}],
            "performance_test": {
                "performance_goal": {
                    "sse_metric_goals": [
                        {"metric_id": "first_answer", "percentile": "p95", "target_ms": 2500},
                        {"metric_id": "first_answer", "percentile": "p99", "target_ms": 3000},
                    ]
                }
            },
            "artifacts": {
                "sse_metrics": {
                    "schema_version": "v1",
                    "attempt_count": 20,
                    "checksum": "sha256:test",
                    "metrics": [
                        {
                            "metric_id": "first_answer",
                            "attempt_count": 20,
                            "matched_count": 19,
                            "missing_count": 1,
                            "failure_count": 0,
                            "p95_ms": 2400,
                            "p99_ms": 3200,
                        }
                    ],
                }
            },
            "missing_evidence": [],
        }
    )

    assert snapshot["sse_metrics"]["metrics"][0]["metric_id"] == "first_answer"
    assert {item["metric"]: item["status"] for item in snapshot["objectives"]} == {
        "sse:first_answer:p95_ms": "passed",
        "sse:first_answer:p99_ms": "failed",
    }
    assert snapshot["verdict"] == "fail"


def test_metric_snapshot_marks_sse_goal_not_evaluated_without_matches() -> None:
    snapshot = build_metric_snapshot(
        {
            "run": {"id": "perfrun-sse", "status": "completed"},
            "summary": {"request_count": 3, "failure_count": 0, "failure_rate": 0},
            "stats": [],
            "performance_test": {
                "performance_goal": {
                    "sse_metric_goals": [
                        {"metric_id": "first_tool_call", "percentile": "p95", "target_ms": 5000}
                    ]
                }
            },
            "artifacts": {
                "sse_metrics": {
                    "attempt_count": 3,
                    "metrics": [
                        {"metric_id": "first_tool_call", "matched_count": 0, "p95_ms": None}
                    ],
                }
            },
            "missing_evidence": [],
        }
    )

    assert snapshot["objectives"][0]["status"] == "not_evaluated"
    assert snapshot["objectives"][0]["actual"] is None
    assert snapshot["verdict"] == "indeterminate"


def test_metric_snapshot_exposes_test_scope_and_single_endpoint_metrics() -> None:
    snapshot = build_metric_snapshot(
        {
            "run": {
                "id": "perfrun-1",
                "status": "completed",
                "load_config": {
                    "mode": "fixed",
                    "users": 10,
                    "spawn_rate": 2,
                    "measurement_duration_seconds": 60,
                    "wait_time_min_seconds": 1,
                    "wait_time_max_seconds": 3,
                },
            },
            "summary": {
                "request_count": 250,
                "failure_count": 0,
                "failure_rate": 0,
                "requests_per_second": 4.27,
                "average_response_time_ms": 211.75,
                "p50_response_time_ms": 160,
                "p95_response_time_ms": 490,
                "p99_response_time_ms": 920,
            },
            "stats": [
                {
                    "sampled_at": "1",
                    "request_count": 250,
                    "requests_per_second": 4.27,
                    "p50_response_time_ms": 160,
                    "p95_response_time_ms": 490,
                    "p99_response_time_ms": 920,
                }
            ],
            "performance_test": {
                "name": "订单查询性能测试",
                "target_type": "endpoint",
                "environment_name": "staging",
                "endpoint_method": "GET",
                "endpoint_path": "/api/orders/{id}",
                "performance_goal": {"max_fail_ratio": 0.01},
            },
            "endpoint": {"method": "GET", "path": "/api/orders/{id}"},
            "artifacts": {
                "result_stats": [
                    {
                        "Type": "GET",
                        "Name": "GET /api/orders/{id}",
                        "Request Count": "250",
                        "Failure Count": "0",
                        "Average Response Time": "211.75",
                        "Requests/s": "4.27",
                        "50%": "160",
                        "95%": "490",
                        "99%": "920",
                    },
                    {"Type": "", "Name": "Aggregated", "Request Count": "250"},
                ]
            },
            "missing_evidence": [],
        }
    )

    assert snapshot["calculator_version"] == "performance-metrics-v5"
    assert snapshot["test_scope"] == {
        "test_name": "订单查询性能测试",
        "environment_name": "staging",
        "load_mode": "fixed",
        "users": 10,
        "spawn_rate": 2.0,
        "duration_seconds": 60,
        "actual_duration_seconds": None,
        "warmup_seconds": None,
        "wait_time_min_seconds": 1.0,
        "wait_time_max_seconds": 3.0,
        "stage_count": 0,
        "endpoint_method": "GET",
        "endpoint_path": "/api/orders/{id}",
    }
    assert snapshot["endpoint_metrics"] == [
        {
            "method": "GET",
            "name": "/api/orders/{id}",
            "request_share": 1.0,
            "request_count": 250,
            "failure_count": 0,
            "failure_rate": 0.0,
            "requests_per_second": 4.27,
            "average_response_time_ms": 211.75,
            "p50_response_time_ms": 160.0,
            "p95_response_time_ms": 490.0,
            "p99_response_time_ms": 920.0,
        }
    ]
    assert snapshot["series"][0]["p50_response_time_ms"] == 160.0
    assert snapshot["quality"]["status"] == "complete"
    assert snapshot["quality"]["request_sample_count"] == 250
    assert snapshot["quality"]["timeseries_sample_count"] == 1
    assert "p99_sample_size_limited" in snapshot["quality"]["warnings"]
    assert snapshot["verdict"] == "pass"
    assert snapshot["latency_analysis"] == {
        "sample_count": 1,
        "sampling_semantics": "cumulative_locust_snapshot",
        "can_claim_direction": False,
        "tail_amplification": 5.75,
    }


def test_metric_snapshot_uses_script_plan_for_scope_but_not_endpoint_metrics() -> None:
    snapshot = build_metric_snapshot(
        {
            "run": {"id": "perfrun-1", "status": "completed"},
            "summary": {"request_count": 20, "p95_response_time_ms": 200},
            "stats": [{"sampled_at": "1", "request_count": 20, "p95_response_time_ms": 200}],
            "performance_test": {"target_type": "endpoint"},
            "script": {
                "plan": {
                    "request": {
                        "method": "POST",
                        "path": "/openapi/v1/agent/analysis/",
                    }
                }
            },
            "missing_evidence": ["result_stats.csv"],
        }
    )

    assert snapshot["test_scope"]["endpoint_method"] == "POST"
    assert snapshot["test_scope"]["endpoint_path"] == "/openapi/v1/agent/analysis/"
    assert snapshot["endpoint_metrics"] == []


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


def test_report_snapshot_adds_safe_next_step_when_evidence_is_insufficient() -> None:
    diagnosis = PerformanceDiagnosis.model_validate(
        {
            "category": "insufficient_evidence",
            "confidence": 0.7,
            "direct_cause": "SSE 请求持续返回业务错误",
            "root_cause": "缺少业务错误码说明，无法确认脚本或被测服务根因",
            "evidence": [],
            "proposed_changes": [],
            "missing_evidence": ["业务错误码说明", "原始 SSE 响应"],
            "requires_second_approval": False,
            "can_auto_rerun": False,
            "recommendations": [],
        }
    )

    report = build_report_snapshot(
        {"verdict": "fail", "objectives": [], "evidence_index": []},
        diagnosis,
    )

    assert len(report["recommendations"]) == 1
    recommendation = report["recommendations"][0]
    assert recommendation["priority"] == "P0"
    assert "缺失证据" in recommendation["action"]
    assert "不要改写压测断言" in recommendation["action"]
    assert recommendation["finding_refs"] == ["finding-1"]


def test_report_snapshot_filters_cumulative_trend_and_resource_recommendations() -> None:
    metric_snapshot = {
        "verdict": "pass",
        "test_scope": {"users": 10},
        "latency_analysis": {
            "sampling_semantics": "cumulative_locust_snapshot",
            "can_claim_direction": False,
        },
        "evidence_index": [
            {"evidence_id": "latency:summary"},
            {"evidence_id": "capacity:summary"},
        ],
        "objectives": [],
    }
    diagnosis = PerformanceDiagnosis.model_validate(
        {
            "category": "external_service",
            "confidence": 0.8,
            "direct_cause": "当前证据不足",
            "root_cause": "需要保持同口径复测",
            "evidence": [],
            "proposed_changes": [],
            "missing_evidence": ["service_metrics"],
            "findings": [
                {
                    "id": "trend",
                    "severity": "low",
                    "level": "observed",
                    "title": "延迟下降",
                    "statement": "P95 从 800ms 下降到 400ms，呈稳定下降趋势",
                    "confidence": 0.8,
                    "evidence_refs": ["latency:summary"],
                    "missing_evidence": ["服务端资源指标"],
                },
                {
                    "id": "capacity",
                    "severity": "low",
                    "level": "observed",
                    "title": "容量未评估",
                    "statement": (
                        "本次为固定单阶段负载（10 用户、60 秒），性能目标（平均响应时间 ≤3000ms、失败率 ≤0.0%）"
                        "全部通过；但 capacity_analysis.can_claim_stable_capacity=false，knee_point=null，"
                        "未触达容量上限，无法据此声称稳定容量或系统上限。"
                    ),
                    "confidence": 0.9,
                    "evidence_refs": ["capacity:summary"],
                },
            ],
            "recommendations": [
                {
                    "id": "resource",
                    "priority": "P3",
                    "action": "采集服务端 CPU 和数据库连接池",
                    "expected_effect": "定位瓶颈",
                    "cost": "medium",
                    "verification": "比较资源利用率",
                    "finding_refs": ["capacity"],
                },
                {
                    "id": "load",
                    "priority": "P1",
                    "action": "补充阶梯负载复测",
                    "expected_effect": "确认已验证负载上界",
                    "cost": "medium",
                    "verification": (
                        "复测后在同口径下获得：1) can_claim_stable_capacity=true；"
                        "2) knee_point（并发用户或 RPS）被识别；"
                        "3) 各级 p95/p99 与失败率随负载变化的可量化曲线。"
                    ),
                    "finding_refs": ["capacity"],
                },
            ],
        }
    )

    report = build_report_snapshot(metric_snapshot, diagnosis)

    assert [item["id"] for item in report["findings"]] == ["capacity"]
    assert [item["id"] for item in report["recommendations"]] == ["load"]
    assert report["findings"][0]["severity"] == "low"
    assert report["findings"][0]["statement"] == (
        "本次仅验证了 10 用户固定负载下的表现。由于未进行分阶段加压，当前结果不能用于判断"
        "系统容量上限或性能拐点，也不能据此宣称已获得稳定容量。"
    )
    assert "can_claim_stable_capacity" not in report["findings"][0]["statement"]
    assert report["recommendations"][0]["priority"] == "P2"
    assert report["recommendations"][0]["verification"] == (
        "复测后报告应给出容量拐点，或明确当前配置下已验证的最大稳定负载，"
        "并展示各级 P95、P99、失败率与吞吐量随负载变化的曲线。"
    )


def test_report_snapshot_filters_redundant_all_objectives_achieved_finding() -> None:
    metric_snapshot = {
        "verdict": "pass",
        "aggregate": {"request_count": 254, "failure_rate": 0, "requests_per_second": 4.31},
        "objectives": [
            {"evidence_id": "objective:failure_rate", "metric": "failure_rate", "status": "passed"},
            {
                "evidence_id": "objective:average_response_time_ms",
                "metric": "average_response_time_ms",
                "status": "passed",
            },
        ],
        "evidence_index": [
            {"evidence_id": "metric:request_count"},
            {"evidence_id": "metric:failure_rate"},
            {"evidence_id": "objective:failure_rate"},
            {"evidence_id": "objective:average_response_time_ms"},
        ],
    }
    diagnosis = PerformanceDiagnosis.model_validate(
        {
            "category": "performance_config",
            "confidence": 0.95,
            "direct_cause": "目标已满足",
            "root_cause": "当前负载范围内没有异常",
            "evidence": [],
            "proposed_changes": [],
            "missing_evidence": [],
            "findings": [
                {
                    "id": "all-objectives-passed",
                    "severity": "low",
                    "level": "observed",
                    "title": "10 用户固定负载下性能目标全部达成",
                    "statement": "两项性能目标（平均响应、失败率）均 passed。",
                    "confidence": 0.99,
                    "evidence_refs": [
                        "metric:request_count",
                        "metric:failure_rate",
                        "objective:failure_rate",
                        "objective:average_response_time_ms",
                    ],
                }
            ],
        }
    )

    report = build_report_snapshot(metric_snapshot, diagnosis)

    assert report["findings"] == []


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

    with pytest.raises(DiagnosisReferenceError, match="未知证据"):
        build_report_snapshot({"verdict": "indeterminate", "evidence_index": []}, diagnosis)


def test_diagnosis_reference_validation_collects_all_unknown_refs_without_mutation() -> None:
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
                    "evidence_refs": ["metric:unknown", "evidence_index:failure_analysis"],
                    "alternative_hypotheses": [],
                    "missing_evidence": ["service_metrics"],
                }
            ],
            "recommendations": [
                {
                    "id": "recommendation-1",
                    "priority": "P2",
                    "action": "补充服务端指标",
                    "expected_effect": "确认尾延迟来源",
                    "cost": "medium",
                    "verification": "对齐同一时间窗口指标",
                    "finding_refs": ["finding-missing"],
                }
            ],
        }
    )
    before = diagnosis.model_dump(mode="json")

    result = validate_diagnosis_references(
        {
            "evidence_index": [
                {"evidence_id": "metric:p95_response_time_ms"},
                {"evidence_id": "latency:summary"},
            ]
        },
        diagnosis,
    )

    assert result.valid is False
    assert result.unknown_evidence_refs == ["evidence_index:failure_analysis", "metric:unknown"]
    assert result.unknown_finding_refs == ["finding-missing"]
    assert diagnosis.model_dump(mode="json") == before
