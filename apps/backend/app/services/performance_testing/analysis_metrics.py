from __future__ import annotations

import math
import statistics
from collections import Counter
from typing import Any


def build_analysis_metrics(evidence: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic, model-independent facts for the report agent."""
    stats = [dict(item) for item in evidence.get("stats") or [] if isinstance(item, dict)]
    stats.sort(key=lambda item: str(item.get("sampled_at") or ""))
    load_config = dict(
        evidence.get("run", {}).get("load_config")
        or evidence.get("performance_test", {}).get("load_config")
        or {}
    )
    stages = _configured_stages(load_config)
    stage_analysis = _stage_analysis(stats, stages)
    latency = _latency_analysis(stats)
    capacity = _capacity_analysis(stage_analysis, stats)
    failures = _failure_analysis(evidence)
    validity = _validity(evidence, stats, stage_analysis)
    return {
        "test_validity": validity,
        "stage_analysis": stage_analysis,
        "latency_analysis": latency,
        "capacity_analysis": capacity,
        "failure_analysis": failures,
    }


def _configured_stages(load_config: dict[str, Any]) -> list[dict[str, Any]]:
    configured = load_config.get("stages")
    if isinstance(configured, list) and configured:
        return [dict(stage) for stage in sorted(configured, key=lambda item: int(item.get("order", 0)))]
    return [{
        "name": "fixed",
        "target_users": int(load_config.get("users") or 0),
        "hold_seconds": int(load_config.get("measurement_duration_seconds") or 0),
        "record_metrics": True,
    }]


def _stage_analysis(stats: list[dict[str, Any]], stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not stats:
        return []
    result: list[dict[str, Any]] = []
    for stage in stages:
        target = int(stage.get("target_users") or 0)
        tolerance = max(5, math.ceil(target * 0.25)) if target else None
        samples = [
            item for item in stats
            if tolerance is None or abs(int(item.get("user_count") or 0) - target) <= tolerance
        ]
        if not samples:
            continue
        p95 = _median_metric(samples, "p95_response_time_ms")
        rps = _median_metric(samples, "requests_per_second")
        failure = _median_metric(samples, "failure_rate")
        result.append({
            "name": str(stage.get("name") or "未命名阶段"),
            "target_users": target,
            "record_metrics": bool(stage.get("record_metrics", True)),
            "sample_count": len(samples),
            "actual_users": round(_median_metric(samples, "user_count")),
            "requests_per_second": round(rps, 4),
            "p95_response_time_ms": _nullable_median(samples, "p95_response_time_ms"),
            "failure_rate": round(failure, 6),
            "status": _stage_status(p95, failure, len(samples)),
        })
    for previous, current in zip(result, result[1:]):
        previous_p95 = previous.get("p95_response_time_ms")
        current_p95 = current.get("p95_response_time_ms")
        previous_rps = float(previous.get("requests_per_second") or 0)
        current_rps = float(current.get("requests_per_second") or 0)
        latency_jump = bool(previous_p95 and current_p95 and current_p95 >= previous_p95 * 1.75)
        throughput_gain = (current_rps - previous_rps) / previous_rps if previous_rps else 1.0
        if current["status"] == "stable" and latency_jump and throughput_gain < 0.25:
            current["status"] = "degraded"
    return result


def _latency_analysis(stats: list[dict[str, Any]]) -> dict[str, Any]:
    if not stats:
        return {
            "sample_count": 0,
            "sampling_semantics": "cumulative_locust_snapshot",
            "can_claim_direction": False,
            "tail_amplification": None,
        }
    p50 = _last_nonzero(stats, "p50_response_time_ms")
    p99 = _last_nonzero(stats, "p99_response_time_ms")
    return {
        "sample_count": len(stats),
        "sampling_semantics": "cumulative_locust_snapshot",
        "can_claim_direction": False,
        "tail_amplification": round(p99 / p50, 4) if p99 and p50 else None,
    }


def _capacity_analysis(stage_analysis: list[dict[str, Any]], stats: list[dict[str, Any]]) -> dict[str, Any]:
    distinct_loads = {int(item.get("target_users") or 0) for item in stage_analysis}
    if len(distinct_loads) < 2:
        return {
            "observed_stable_capacity": None,
            "knee_point": None,
            "can_claim_stable_capacity": False,
            "reason": "当前为固定单阶段负载，仅能确认已验证负载表现，无法判断系统容量上限或性能拐点。",
            "sample_count": len(stats),
        }
    stable = [item for item in stage_analysis if item["status"] == "stable"]
    degraded = [item for item in stage_analysis if item["status"] == "degraded"]
    if stable:
        best = max(stable, key=lambda item: (item["target_users"], item["requests_per_second"]))
        stable_capacity = {
            "users": best["target_users"],
            "requests_per_second": best["requests_per_second"],
            "p95_response_time_ms": best["p95_response_time_ms"],
        }
    else:
        stable_capacity = None
    knee = None
    if degraded and stable:
        before = max(stable, key=lambda item: item["target_users"])
        after = min(degraded, key=lambda item: item["target_users"])
        if after["target_users"] >= before["target_users"]:
            knee = {
                "between_users": [before["target_users"], after["target_users"]],
                "reason": "稳态阶段之后出现延迟、吞吐或失败率退化",
            }
    return {
        "observed_stable_capacity": stable_capacity,
        "knee_point": knee,
        "can_claim_stable_capacity": bool(stable),
        "reason": "" if stable else "没有足够的稳定阶段证据。",
        "sample_count": len(stats),
    }


def _failure_analysis(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    examples: dict[str, str] = {}
    for item in evidence.get("failures") or []:
        row = dict(item)
        kind = _failure_kind(row)
        counts[kind] += int(row.get("count") or 1)
        examples.setdefault(kind, str(row.get("reason") or ""))
    for item in evidence.get("exceptions") or []:
        row = dict(item)
        kind = _failure_kind(row)
        counts[kind] += int(row.get("count") or 1)
        examples.setdefault(kind, str(row.get("message") or row.get("exception_type") or ""))
    total = sum(counts.values())
    return [
        {
            "kind": kind,
            "count": count,
            "ratio": round(count / total, 6) if total else 0,
            "example": examples.get(kind, ""),
        }
        for kind, count in counts.most_common()
    ]


def _failure_kind(row: dict[str, Any]) -> str:
    status = int(row.get("sample_status_code") or row.get("status_code") or 0)
    text = f"{row.get('reason', '')} {row.get('message', '')} {row.get('exception_type', '')}".lower()
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "connection" in text or "connect" in text:
        return "connection_error"
    if "assert" in text or "jsonpath" in text:
        return "assertion_failure"
    if status == 429 or "rate limit" in text or "too many requests" in text:
        return "rate_limit"
    if 400 <= status < 500:
        return "http_4xx"
    if status >= 500:
        return "http_5xx"
    return "unknown"


def _validity(evidence: dict[str, Any], stats: list[dict[str, Any]], stages: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    summary = dict(evidence.get("summary") or {})
    if int(summary.get("request_count") or 0) <= 0:
        issues.append("measurement_window_contains_no_requests")
    if not stats:
        issues.append("time_series_missing")
    if not any(item.get("p95_response_time_ms") for item in stats):
        issues.append("p95_response_time_missing")
    if len(stats) < 3:
        issues.append("too_few_time_series_samples")
    if not stages:
        issues.append("load_stage_missing")
    run = dict(evidence.get("run") or {})
    if run.get("status") == "stopped":
        issues.append("run_manually_stopped")
    status = "invalid" if "measurement_window_contains_no_requests" in issues else "partial" if issues else "complete"
    return {
        "status": status,
        "issues": issues,
        "sample_count": len(stats),
        "coverage": round(max(0, 1 - len(issues) * 0.1), 2),
        "termination_reason": run.get("termination_reason") or ("manual_stop" if run.get("status") == "stopped" else run.get("status") or "unknown"),
    }


def _stage_status(p95: float | None, failure_rate: float, sample_count: int) -> str:
    if sample_count < 2 or p95 is None:
        return "insufficient_evidence"
    if failure_rate > 0.01:
        return "degraded"
    return "stable"


def _median_metric(items: list[dict[str, Any]], key: str) -> float:
    values = [float(item.get(key) or 0) for item in items]
    return float(statistics.median(values)) if values else 0.0


def _nullable_median(items: list[dict[str, Any]], key: str) -> float | None:
    values = [float(item.get(key) or 0) for item in items if item.get(key) not in (None, "", 0, 0.0)]
    return round(float(statistics.median(values)), 4) if values else None


def _first_nonzero(items: list[dict[str, Any]], key: str) -> float | None:
    for item in items:
        value = float(item.get(key) or 0)
        if value > 0:
            return value
    return None


def _last_nonzero(items: list[dict[str, Any]], key: str) -> float | None:
    for item in reversed(items):
        value = float(item.get(key) or 0)
        if value > 0:
            return value
    return None


__all__ = ["build_analysis_metrics"]
