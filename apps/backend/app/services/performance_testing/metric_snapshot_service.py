from __future__ import annotations

import hashlib
import json
import re
import statistics
from datetime import datetime
from typing import Any

from app.services.performance_testing.analysis_metrics import build_analysis_metrics
from app.services.performance_testing.diagnosis_validation import require_valid_diagnosis_references


CALCULATOR_VERSION = "performance-metrics-v5"


def build_metric_snapshot(evidence: dict[str, Any]) -> dict[str, Any]:
    run = dict(evidence.get("run") or {})
    performance_test = dict(evidence.get("performance_test") or {})
    script = dict(evidence.get("script") or {})
    endpoint = dict(evidence.get("endpoint") or {})
    artifacts = dict(evidence.get("artifacts") or {})
    stats = [dict(item) for item in evidence.get("stats") or [] if isinstance(item, dict)]
    summary = _summary(evidence.get("summary"), stats)
    quality = _quality(run, summary, stats, evidence.get("missing_evidence") or [])
    test_scope = _test_scope(run, performance_test, endpoint, script, quality)
    endpoint_metrics = _endpoint_metrics(artifacts.get("result_stats"))
    sse_metrics = _sse_metrics(artifacts.get("sse_metrics"), performance_test.get("request_config"))
    objectives = _objectives(
        performance_test.get("performance_goal") or {}, summary, quality["status"], sse_metrics
    )
    verdict = _verdict(objectives, quality["status"])
    series = [_series_sample(item) for item in stats]
    peak_rps = max((float(item.get("requests_per_second") or 0) for item in stats), default=0.0)
    stable_rps = _stable_throughput(stats, run.get("status"))
    snapshot_source = {
        "run": run,
        "summary": summary,
        "stats": series,
        "performance_goal": performance_test.get("performance_goal") or {},
        "test_scope": test_scope,
        "endpoint_metrics": endpoint_metrics,
        "sse_metrics": sse_metrics,
        "sse_config": (performance_test.get("request_config") or {}).get("sse"),
    }
    source_fingerprint = "sha256:" + hashlib.sha256(
        json.dumps(snapshot_source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    analysis_metrics = build_analysis_metrics(evidence)
    evidence_index = _evidence_index(summary, objectives, quality) + _analysis_evidence_index(analysis_metrics)
    return {
        "schema_version": 5,
        "calculator_version": CALCULATOR_VERSION,
        "run_id": str(run.get("id") or ""),
        "source_fingerprint": source_fingerprint,
        "quality": quality,
        "test_scope": test_scope,
        "aggregate": summary,
        "endpoint_metrics": endpoint_metrics,
        "sse_metrics": sse_metrics,
        "capacity": {
            "observed_peak_throughput": round(peak_rps, 4),
            "stable_throughput": stable_rps,
            "knee_point": None,
            "knee_point_reason": "当前版本未在缺少分阶段负载证据时推断性能拐点。",
        },
        "objectives": objectives,
        "verdict": verdict,
        "series": series,
        **analysis_metrics,
        "evidence_index": evidence_index,
    }


def build_report_snapshot(metric_snapshot: dict[str, Any], diagnosis: Any) -> dict[str, Any]:
    require_valid_diagnosis_references(metric_snapshot, diagnosis)
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
    findings = _supported_findings(metric_snapshot, findings)
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
                "finding_refs": [str(findings[0]["id"])] if findings else [],
                "proposed_change_id": change.id,
            }
            for index, change in enumerate(diagnosis.proposed_changes)
        ]
    recommendations = _supported_recommendations(metric_snapshot, findings, recommendations)
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
    warnings: list[str] = []
    if summary["request_count"] <= 0:
        issues.append("measurement_window_contains_no_requests")
    if not stats:
        issues.append("time_series_missing")
    if summary["p95_response_time_ms"] is None:
        issues.append("p95_response_time_missing")
    if summary["p99_response_time_ms"] is not None and summary["request_count"] < 1000:
        warnings.append("p99_sample_size_limited")
    if run.get("status") == "stopped":
        issues.append("run_manually_stopped")
    elif run.get("status") not in {"completed", ""}:
        issues.append(f"run_terminal_status:{run.get('status') or 'unknown'}")
    if summary["request_count"] <= 0:
        status = "invalid"
    elif issues:
        status = "partial"
    else:
        status = "complete"
    actual_duration = _duration_seconds(run.get("started_at"), run.get("finished_at"))
    configured_duration = _configured_duration_seconds(run)
    return {
        "status": status,
        "coverage": round(max(0.0, 1.0 - min(len(issues), 10) * 0.08), 2),
        "issues": issues,
        "warnings": warnings,
        "diagnostic_missing_evidence": [str(item) for item in missing],
        "request_sample_count": summary["request_count"],
        "timeseries_sample_count": len(stats),
        "sample_count": len(stats),
        "termination_reason": run.get("termination_reason") or (
            "manual_stop" if run.get("status") == "stopped" else run.get("status") or "unknown"
        ),
        "termination_label": run.get("termination_label") or (
            "人工停止" if run.get("status") == "stopped" else "正常完成" if run.get("status") == "completed" else "未知"
        ),
        "actual_duration_seconds": actual_duration,
        "configured_duration_seconds": configured_duration,
        "duration_complete": (
            actual_duration is not None
            and configured_duration is not None
            and actual_duration >= configured_duration
        ) if actual_duration is not None and configured_duration is not None else None,
    }


def _duration_seconds(started_at: Any, finished_at: Any) -> int | None:
    if not started_at or not finished_at:
        return None
    try:
        start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        finish = datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
        return max(0, round((finish - start).total_seconds()))
    except (TypeError, ValueError):
        return None


def _configured_duration_seconds(run: dict[str, Any]) -> int | None:
    load_config = run.get("load_config") if isinstance(run.get("load_config"), dict) else {}
    value = load_config.get("measurement_duration_seconds")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _test_scope(
    run: dict[str, Any],
    performance_test: dict[str, Any],
    endpoint: dict[str, Any],
    script: dict[str, Any],
    quality: dict[str, Any],
) -> dict[str, Any]:
    run_load = run.get("load_config") if isinstance(run.get("load_config"), dict) else {}
    test_load = performance_test.get("load_config") if isinstance(performance_test.get("load_config"), dict) else {}
    load = {**test_load, **run_load}
    stages = load.get("stages") if isinstance(load.get("stages"), list) else []
    method, path = _request_identity(performance_test, endpoint, script)
    return {
        "test_name": str(performance_test.get("name") or ""),
        "environment_name": str(performance_test.get("environment_name") or ""),
        "load_mode": str(load.get("mode") or ""),
        "users": _optional_int(load.get("users")),
        "spawn_rate": _optional_float(load.get("spawn_rate")),
        "duration_seconds": _optional_int(load.get("measurement_duration_seconds")),
        "actual_duration_seconds": quality.get("actual_duration_seconds"),
        "warmup_seconds": None,
        "wait_time_min_seconds": _optional_float(load.get("wait_time_min_seconds")),
        "wait_time_max_seconds": _optional_float(load.get("wait_time_max_seconds")),
        "stage_count": len(stages),
        "endpoint_method": method,
        "endpoint_path": path,
    }


def _request_identity(
    performance_test: dict[str, Any], endpoint: dict[str, Any], script: dict[str, Any]
) -> tuple[str, str]:
    plan = script.get("plan") if isinstance(script.get("plan"), dict) else {}
    request = plan.get("request") if isinstance(plan.get("request"), dict) else {}
    method = str(
        endpoint.get("method")
        or performance_test.get("endpoint_method")
        or request.get("method")
        or ""
    ).upper()
    path = str(
        endpoint.get("path")
        or performance_test.get("endpoint_path")
        or request.get("path")
        or ""
    )
    return method, path


def _endpoint_metrics(raw_rows: Any) -> list[dict[str, Any]]:
    rows = [dict(item) for item in raw_rows or [] if isinstance(item, dict)]
    endpoint_rows = [
        row
        for row in rows
        if str(row.get("Name") or "").strip()
        and str(row.get("Name") or "").strip().lower() != "aggregated"
    ]
    total_requests = sum(_csv_int(row, "Request Count") for row in endpoint_rows)
    if not endpoint_rows or total_requests <= 0:
        return []

    result = []
    for row in endpoint_rows:
        request_count = _csv_int(row, "Request Count")
        failure_count = _csv_int(row, "Failure Count")
        method = str(row.get("Type") or "").upper()
        name = _normalized_endpoint_name(method, row.get("Name"))
        result.append(
            {
                "method": method,
                "name": name,
                "request_share": round(request_count / total_requests, 6),
                "request_count": request_count,
                "failure_count": failure_count,
                "failure_rate": failure_count / request_count if request_count else 0.0,
                "requests_per_second": _csv_float(row, "Requests/s"),
                "average_response_time_ms": _csv_float(row, "Average Response Time"),
                "p50_response_time_ms": _csv_optional_float(row, "50%"),
                "p95_response_time_ms": _csv_optional_float(row, "95%"),
                "p99_response_time_ms": _csv_optional_float(row, "99%"),
            }
        )
    return sorted(
        result,
        key=lambda item: (
            item["failure_count"] == 0,
            -(item["p95_response_time_ms"] or 0),
            item["name"],
        ),
    )


def _normalized_endpoint_name(method: str, raw_name: Any) -> str:
    name = str(raw_name or "").strip()
    if method and name.upper().startswith(f"{method} "):
        return name[len(method) :].strip()
    return name


def _csv_int(row: dict[str, Any], key: str) -> int:
    try:
        return int(float(row.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def _csv_float(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _csv_optional_float(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _objectives(
    goal: dict[str, Any],
    summary: dict[str, Any],
    quality_status: str,
    sse_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
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
    metrics_by_id = {
        str(metric.get("metric_id") or ""): metric
        for metric in sse_metrics.get("metrics") or []
        if isinstance(metric, dict)
    }
    for definition in goal.get("sse_metric_goals") or []:
        if not isinstance(definition, dict):
            continue
        metric_id = str(definition.get("metric_id") or "")
        percentile = str(definition.get("percentile") or "")
        metric = metrics_by_id.get(metric_id) or {}
        actual = metric.get(f"{percentile}_ms") if int(metric.get("matched_count") or 0) > 0 else None
        target = float(definition.get("target_ms") or 0)
        if quality_status == "invalid" or actual is None:
            status = "not_evaluated"
        else:
            status = "passed" if float(actual) <= target else "failed"
        results.append(
            {
                "evidence_id": f"objective:sse:{metric_id}:{percentile}",
                "metric": f"sse:{metric_id}:{percentile}_ms",
                "operator": "lte",
                "target": target,
                "actual": actual,
                "status": status,
            }
        )
    return results


def _sse_metrics(raw: Any, request_config: Any = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"schema_version": "v1", "attempt_count": 0, "truncated": False, "metrics": []}
    configured_names = {
        str(metric.get("id") or ""): str(metric.get("name") or metric.get("id") or "")
        for metric in ((request_config or {}).get("sse") or {}).get("metrics") or []
        if isinstance(metric, dict)
    }
    metrics = [
        {**dict(item), "name": configured_names.get(str(item.get("metric_id") or ""), str(item.get("metric_id") or ""))}
        for item in raw.get("metrics") or []
        if isinstance(item, dict)
    ]
    return {
        "schema_version": str(raw.get("schema_version") or "v1"),
        "attempt_count": int(raw.get("attempt_count") or 0),
        "truncated": bool(raw.get("truncated")),
        "checksum": str(raw.get("checksum") or ""),
        "parse_error_count": int(raw.get("parse_error_count") or 0),
        "timeout_count": int(raw.get("timeout_count") or 0),
        "end_rule_not_matched_count": int(raw.get("end_rule_not_matched_count") or 0),
        "failure_reasons": dict(raw.get("failure_reasons") or {}),
        "metrics": metrics,
    }


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
        "p50_response_time_ms": _optional_percentile(item, "p50_response_time_ms"),
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


def _analysis_evidence_index(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    result = [
        {
            "evidence_id": "validity:summary",
            "kind": "test_validity",
            "value": analysis.get("test_validity", {}),
        },
        {
            "evidence_id": "capacity:summary",
            "kind": "capacity",
            "value": analysis.get("capacity_analysis", {}),
        },
        {
            "evidence_id": "latency:summary",
            "kind": "latency",
            "value": analysis.get("latency_analysis", {}),
        },
    ]
    result.extend(
        {
            "evidence_id": f"stage:{index + 1}",
            "kind": "load_stage",
            "value": stage,
        }
        for index, stage in enumerate(analysis.get("stage_analysis", []))
    )
    result.extend(
        {
            "evidence_id": f"failure:{item.get('kind', index + 1)}",
            "kind": "failure_class",
            "value": item,
        }
        for index, item in enumerate(analysis.get("failure_analysis", []))
    )
    return result


def _executive_summary(snapshot: dict[str, Any]) -> str:
    labels = {"pass": "通过", "conditional_pass": "有条件通过", "fail": "不通过", "indeterminate": "无法判断"}
    aggregate = snapshot.get("aggregate") or {}
    summary = (
        f"本次压测结论为{labels.get(snapshot.get('verdict'), '无法判断')}。"
        f"共执行 {aggregate.get('request_count', 0)} 次请求，失败率 "
        f"{float(aggregate.get('failure_rate') or 0) * 100:.2f}%，观测吞吐 "
        f"{float(aggregate.get('requests_per_second') or 0):.2f} RPS。"
    )
    quality = snapshot.get("quality") or {}
    if quality.get("termination_reason") == "manual_stop":
        summary += "本次运行由测试人员手动停止，指标反映实际运行窗口内的表现，不代表运行异常。"
    actual = quality.get("actual_duration_seconds")
    configured = quality.get("configured_duration_seconds")
    if actual is not None and configured is not None:
        summary += f"实际运行 {actual} 秒，配置时长 {configured} 秒。"
    return summary


def _capacity_summary(snapshot: dict[str, Any]) -> str:
    analysis = snapshot.get("capacity_analysis") or {}
    observed = analysis.get("observed_stable_capacity")
    if observed:
        text = (
            f"观测到的稳定容量约为 {int(observed.get('users') or 0)} 并发、"
            f"{float(observed.get('requests_per_second') or 0):.2f} RPS。"
        )
        knee = analysis.get("knee_point") or {}
        if knee.get("between_users"):
            text += f"性能拐点区间约为 {knee['between_users'][0]} ~ {knee['between_users'][1]} 并发。"
        return text
    if analysis.get("reason"):
        return str(analysis["reason"])
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


def _supported_findings(metric_snapshot: dict[str, Any], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    verdict = str(metric_snapshot.get("verdict") or "")
    latency_analysis = metric_snapshot.get("latency_analysis") or {}
    direction_limited = (
        latency_analysis.get("can_claim_direction") is False
        or latency_analysis.get("sampling_semantics") == "cumulative_locust_snapshot"
    )
    result = []
    for finding in findings:
        text = f"{finding.get('title', '')} {finding.get('statement', '')}"
        if verdict in {"pass", "conditional_pass"} and _is_redundant_pass_finding(text):
            continue
        if direction_limited and re.search(r"P(?:50|95|99)|延迟|响应时间", text, re.IGNORECASE) and re.search(
            r"下降|上升|改善|恶化|收敛|稳定趋势|持续变好|持续变差",
            text,
        ):
            continue
        normalized = {
            **finding,
            "missing_evidence": [
                item
                for item in finding.get("missing_evidence", [])
                if not _is_server_resource_evidence(str(item))
            ],
        }
        if _should_demote_capacity_boundary(metric_snapshot, normalized):
            normalized["severity"] = "low"
        normalized = _humanize_capacity_boundary_finding(metric_snapshot, normalized)
        result.append(normalized)
    return result


def _supported_recommendations(
    metric_snapshot: dict[str, Any], findings: list[dict[str, Any]], recommendations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    finding_ids = {str(item.get("id") or "") for item in findings}
    result = []
    for recommendation in recommendations:
        text = " ".join(
            str(recommendation.get(key) or "")
            for key in ("action", "expected_effect", "verification")
        )
        refs = [str(item) for item in recommendation.get("finding_refs", [])]
        if _is_server_resource_evidence(text):
            continue
        if not refs or any(ref not in finding_ids for ref in refs):
            continue
        normalized = dict(recommendation)
        referenced_findings = [item for item in findings if str(item.get("id") or "") in refs]
        if referenced_findings and all(
            _should_demote_capacity_boundary(metric_snapshot, finding) for finding in referenced_findings
        ):
            normalized["priority"] = "P2"
            normalized = _humanize_capacity_boundary_recommendation(normalized)
        result.append(normalized)
    return result


def _is_redundant_pass_finding(text: str) -> bool:
    pass_summary = re.search(
        r"(?:目标|指标|验收|测试有效性|performance).*?(?:通过|满足|达成|合格|passed)"
        r"|(?:全部|均).*?(?:通过|满足|达成|合格|passed)",
        text,
        re.IGNORECASE,
    )
    material_concern = re.search(
        r"无法|不足|限制|风险|异常|缺少|不能|未评估|未配置|仅(?:验证|覆盖)|不代表",
        text,
        re.IGNORECASE,
    )
    return bool(pass_summary and not material_concern)


def _should_demote_capacity_boundary(metric_snapshot: dict[str, Any], finding: dict[str, Any]) -> bool:
    if str(metric_snapshot.get("verdict") or "") not in {"pass", "conditional_pass"}:
        return False
    if any(item.get("metric") == "requests_per_second" for item in metric_snapshot.get("objectives", [])):
        return False
    evidence_refs = {str(item) for item in finding.get("evidence_refs", [])}
    text = f"{finding.get('title', '')} {finding.get('statement', '')}"
    capacity_boundary = "capacity:summary" in evidence_refs or bool(
        re.search(r"容量上限|容量拐点|性能拐点|固定(?:单阶段)?负载|阶梯加压", text, re.IGNORECASE)
    )
    return capacity_boundary and not _has_performance_failure_signal(text)


def _has_performance_failure_signal(text: str) -> bool:
    if re.search(r"请求失败|失败请求|失败率(?:上升|恶化|超标|非零)|退化|恶化|超时|错误|目标未通过", text, re.IGNORECASE):
        return True
    return any(
        float(match.group(1)) > 0
        for match in re.finditer(r"失败率\s*(?:为|=|：|:|>|≥)?\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
    )


def _humanize_capacity_boundary_finding(
    metric_snapshot: dict[str, Any], finding: dict[str, Any]
) -> dict[str, Any]:
    statement = str(finding.get("statement") or "")
    if not _should_demote_capacity_boundary(metric_snapshot, finding) or not re.search(
        r"load\.mode|stages|capacity_analysis|can_claim_stable_capacity|knee_point|\b(?:false|null)\b",
        statement,
        re.IGNORECASE,
    ):
        return finding
    users = (metric_snapshot.get("test_scope") or {}).get("users")
    load_scope = f"{int(users)} 用户固定负载" if isinstance(users, (int, float)) and users > 0 else "当前固定负载"
    return {
        **finding,
        "statement": (
            f"本次仅验证了 {load_scope}下的表现。由于未进行分阶段加压，当前结果不能用于判断"
            "系统容量上限或性能拐点，也不能据此宣称已获得稳定容量。"
        ),
    }


def _humanize_capacity_boundary_recommendation(recommendation: dict[str, Any]) -> dict[str, Any]:
    internal_fields = re.compile(
        r"load\.mode|stages|capacity_analysis|can_claim_stable_capacity|knee_point|\b(?:true|false|null)\b",
        re.IGNORECASE,
    )
    normalized = dict(recommendation)
    if internal_fields.search(str(normalized.get("action") or "")):
        normalized["action"] = "补充分阶段阶梯加压复测。"
    if internal_fields.search(str(normalized.get("expected_effect") or "")):
        normalized["expected_effect"] = "识别容量拐点，或明确当前配置下已验证的最大稳定负载。"
    verification = str(normalized.get("verification") or "")
    if internal_fields.search(verification) or re.search(r"拐点.*非空", verification, re.IGNORECASE):
        normalized["verification"] = (
            "复测后报告应给出容量拐点，或明确当前配置下已验证的最大稳定负载，"
            "并展示各级 P95、P99、失败率与吞吐量随负载变化的曲线。"
        )
    return normalized


def _is_server_resource_evidence(value: str) -> bool:
    return bool(
        re.search(
            r"服务端资源|server.resource|CPU|内存|数据库连接|连接池|调用链|resource_correlation",
            value,
            re.IGNORECASE,
        )
    )


__all__ = ["CALCULATOR_VERSION", "build_metric_snapshot", "build_report_snapshot"]
