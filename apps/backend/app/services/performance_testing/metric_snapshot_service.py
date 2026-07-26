from __future__ import annotations

import hashlib
import json
import statistics
from typing import Any


CALCULATOR_VERSION = "performance-metrics-v1"


def build_metric_snapshot(evidence: dict[str, Any]) -> dict[str, Any]:
    run = dict(evidence.get("run") or {})
    performance_test = dict(evidence.get("performance_test") or {})
    stats = [dict(item) for item in evidence.get("stats") or [] if isinstance(item, dict)]
    summary = _summary(evidence.get("summary"), stats)
    quality = _quality(run, summary, stats, evidence.get("missing_evidence") or [])
    objectives = _objectives(performance_test.get("performance_goal") or {}, summary, quality["status"])
    verdict = _verdict(objectives, quality["status"])
    series = [_series_sample(item) for item in stats]
    peak_rps = max((float(item.get("requests_per_second") or 0) for item in stats), default=0.0)
    stable_rps = _stable_throughput(stats, run.get("status"))
    snapshot_source = {
        "run": run,
        "summary": summary,
        "stats": series,
        "performance_goal": performance_test.get("performance_goal") or {},
    }
    source_fingerprint = "sha256:" + hashlib.sha256(
        json.dumps(snapshot_source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    evidence_index = _evidence_index(summary, objectives, quality)
    return {
        "schema_version": 1,
        "calculator_version": CALCULATOR_VERSION,
        "run_id": str(run.get("id") or ""),
        "source_fingerprint": source_fingerprint,
        "quality": quality,
        "aggregate": summary,
        "capacity": {
            "observed_peak_throughput": round(peak_rps, 4),
            "stable_throughput": stable_rps,
            "knee_point": None,
            "knee_point_reason": "当前版本未在缺少分阶段负载证据时推断性能拐点。",
        },
        "objectives": objectives,
        "verdict": verdict,
        "series": series,
        "evidence_index": evidence_index,
    }


def build_report_snapshot(metric_snapshot: dict[str, Any], diagnosis: Any) -> dict[str, Any]:
    _validate_structured_diagnosis(metric_snapshot, diagnosis)
    evidence = [item.model_dump(mode="json") for item in diagnosis.evidence]
    evidence_ids = [f"diagnosis:{index + 1}" for index in range(len(evidence))]
    findings = [item.model_dump(mode="json") for item in diagnosis.findings]
    if not findings and diagnosis.direct_cause:
        findings = [
            {
                "id": "finding-1",
                "severity": _severity(metric_snapshot.get("verdict")),
                "level": "inferred" if diagnosis.confidence < 0.9 else "derived",
                "title": diagnosis.direct_cause[:200],
                "statement": diagnosis.root_cause or diagnosis.direct_cause,
                "confidence": diagnosis.confidence,
                "evidence_refs": evidence_ids,
                "alternative_hypotheses": [],
                "missing_evidence": list(diagnosis.missing_evidence),
            }
        ]
    recommendations = [item.model_dump(mode="json") for item in diagnosis.recommendations]
    if not recommendations:
        recommendations = [
            {
                "id": f"recommendation-{index + 1}",
                "priority": "P1" if change.risk_level == "low" else "P2",
                "action": change.reason,
                "expected_effect": f"调整 {change.target} 后复测并比较同口径指标。",
                "cost": change.risk_level,
                "verification": "应用前执行单请求预检，复测后比较目标判定和关键延迟指标。",
                "finding_refs": ["finding-1"] if findings else [],
                "proposed_change_id": change.id,
            }
            for index, change in enumerate(diagnosis.proposed_changes)
        ]
    return {
        "schema_version": 1,
        "verdict": metric_snapshot.get("verdict", "indeterminate"),
        "verdict_reasons": [item["evidence_id"] for item in metric_snapshot.get("objectives", [])],
        "executive_summary": _executive_summary(metric_snapshot),
        "capacity_summary": _capacity_summary(metric_snapshot),
        "findings": findings,
        "recommendations": recommendations,
        "diagnosis_evidence": [
            {"evidence_id": evidence_ids[index], **item} for index, item in enumerate(evidence)
        ],
    }


def _summary(raw_summary: Any, stats: list[dict[str, Any]]) -> dict[str, Any]:
    raw = dict(raw_summary) if isinstance(raw_summary, dict) else {}
    latest = max(stats, key=lambda item: int(item.get("request_count") or 0), default={})
    merged = {**latest, **raw}
    request_count = int(merged.get("request_count") or 0)
    failure_count = int(merged.get("failure_count") or 0)
    return {
        "request_count": request_count,
        "failure_count": failure_count,
        "failure_rate": float(merged.get("failure_rate") or (failure_count / request_count if request_count else 0)),
        "requests_per_second": float(merged.get("requests_per_second") or 0),
        "average_response_time_ms": float(merged.get("average_response_time_ms") or 0),
        "p50_response_time_ms": _optional_percentile(merged, "p50_response_time_ms"),
        "p95_response_time_ms": _optional_percentile(merged, "p95_response_time_ms"),
        "p99_response_time_ms": _optional_percentile(merged, "p99_response_time_ms"),
    }


def _optional_percentile(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if value in (None, "", 0, 0.0):
        return None
    return float(value)


def _quality(run: dict[str, Any], summary: dict[str, Any], stats: list[dict[str, Any]], missing: list[Any]) -> dict[str, Any]:
    issues: list[str] = []
    if summary["request_count"] <= 0:
        issues.append("measurement_window_contains_no_requests")
    if not stats:
        issues.append("time_series_missing")
    if summary["p95_response_time_ms"] is None:
        issues.append("p95_response_time_missing")
    if run.get("status") != "completed":
        issues.append(f"run_terminal_status:{run.get('status') or 'unknown'}")
    if summary["request_count"] <= 0:
        status = "invalid"
    elif issues:
        status = "partial"
    else:
        status = "complete"
    return {
        "status": status,
        "coverage": round(max(0.0, 1.0 - min(len(issues), 10) * 0.08), 2),
        "issues": issues,
        "diagnostic_missing_evidence": [str(item) for item in missing],
        "sample_count": len(stats),
    }


def _objectives(goal: dict[str, Any], summary: dict[str, Any], quality_status: str) -> list[dict[str, Any]]:
    definitions = [
        ("max_fail_ratio", "failure_rate", "lte"),
        ("max_average_response_time_ms", "average_response_time_ms", "lte"),
        ("max_p95_response_time_ms", "p95_response_time_ms", "lte"),
        ("min_average_rps", "requests_per_second", "gte"),
    ]
    results = []
    for goal_key, metric, operator in definitions:
        target = goal.get(goal_key)
        if target is None:
            continue
        actual = summary.get(metric)
        if quality_status == "invalid" or actual is None:
            status = "not_evaluated"
        else:
            passed = actual <= float(target) if operator == "lte" else actual >= float(target)
            status = "passed" if passed else "failed"
        results.append(
            {
                "evidence_id": f"objective:{metric}",
                "metric": metric,
                "operator": operator,
                "target": float(target),
                "actual": actual,
                "status": status,
            }
        )
    return results


def _verdict(objectives: list[dict[str, Any]], quality_status: str) -> str:
    if quality_status == "invalid" or not objectives or any(item["status"] == "not_evaluated" for item in objectives):
        return "indeterminate"
    if any(item["status"] == "failed" for item in objectives):
        return "fail"
    return "pass" if quality_status == "complete" else "conditional_pass"


def _stable_throughput(stats: list[dict[str, Any]], run_status: Any) -> float | None:
    values = [float(item.get("requests_per_second") or 0) for item in stats if float(item.get("requests_per_second") or 0) > 0]
    if run_status != "completed" or len(values) < 3:
        return None
    tail = values[max(0, len(values) // 2) :]
    return round(float(statistics.median(tail)), 4)


def _series_sample(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "sampled_at": str(item.get("sampled_at") or ""),
        "user_count": int(item.get("user_count") or 0),
        "request_count": int(item.get("request_count") or 0),
        "requests_per_second": float(item.get("requests_per_second") or 0),
        "failure_rate": float(item.get("failure_rate") or 0),
        "average_response_time_ms": float(item.get("average_response_time_ms") or 0),
        "p95_response_time_ms": _optional_percentile(item, "p95_response_time_ms"),
        "p99_response_time_ms": _optional_percentile(item, "p99_response_time_ms"),
    }


def _evidence_index(summary: dict[str, Any], objectives: list[dict[str, Any]], quality: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = [
        {"evidence_id": f"metric:{key}", "kind": "metric", "value": value}
        for key, value in summary.items()
    ]
    return metrics + [dict(item) for item in objectives] + [
        {"evidence_id": "quality:summary", "kind": "quality", "value": quality}
    ]


def _executive_summary(snapshot: dict[str, Any]) -> str:
    labels = {"pass": "通过", "conditional_pass": "有条件通过", "fail": "不通过", "indeterminate": "无法判断"}
    aggregate = snapshot.get("aggregate") or {}
    return (
        f"本次压测结论为{labels.get(snapshot.get('verdict'), '无法判断')}。"
        f"共执行 {aggregate.get('request_count', 0)} 次请求，失败率 "
        f"{float(aggregate.get('failure_rate') or 0) * 100:.2f}%，观测吞吐 "
        f"{float(aggregate.get('requests_per_second') or 0):.2f} RPS。"
    )


def _capacity_summary(snapshot: dict[str, Any]) -> str:
    capacity = snapshot.get("capacity") or {}
    stable = capacity.get("stable_throughput")
    if stable is None:
        return "当前采样或运行状态不足以给出稳定容量结论，报告仅展示观测峰值吞吐。"
    return f"当前运行后半段吞吐中位数为 {float(stable):.2f} RPS，可作为本次运行的稳定吞吐参考。"


def _severity(verdict: Any) -> str:
    if verdict == "fail":
        return "high"
    if verdict in {"conditional_pass", "indeterminate"}:
        return "medium"
    return "low"


def _validate_structured_diagnosis(metric_snapshot: dict[str, Any], diagnosis: Any) -> None:
    evidence_ids = {
        str(item.get("evidence_id"))
        for item in metric_snapshot.get("evidence_index", [])
        if isinstance(item, dict) and item.get("evidence_id")
    }
    finding_ids = {item.id for item in diagnosis.findings}
    for finding in diagnosis.findings:
        unknown = sorted(set(finding.evidence_refs) - evidence_ids)
        if unknown:
            raise ValueError(f"性能诊断引用了未知证据：{', '.join(unknown)}")
    for recommendation in diagnosis.recommendations:
        unknown = sorted(set(recommendation.finding_refs) - finding_ids)
        if unknown:
            raise ValueError(f"性能建议引用了未知 finding：{', '.join(unknown)}")


__all__ = ["CALCULATOR_VERSION", "build_metric_snapshot", "build_report_snapshot"]
