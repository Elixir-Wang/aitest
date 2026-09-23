from __future__ import annotations

from typing import Any


BLOCKING_SEVERITIES = {"critical", "high"}


def build_failure_signals(
    evidence: dict[str, Any],
    *,
    objectives: list[dict[str, Any]],
    endpoint_metrics: list[dict[str, Any]],
    protocol_metrics: dict[str, Any],
    quality: dict[str, Any],
) -> list[dict[str, Any]]:
    """Normalize every observed failure domain into one AI/report contract."""
    signals: list[dict[str, Any]] = []

    for index, objective in enumerate(objectives):
        observed_breach = _objective_breached(objective)
        if objective.get("status") != "failed" and not observed_breach:
            continue
        evaluated = objective.get("status") == "failed"
        signals.append(
            _signal(
                signal_id=f"objective:{index + 1}",
                scope="objective",
                kind="objective_failed",
                severity="high" if evaluated else "medium",
                title=("性能目标未通过" if evaluated else "观测值越过目标但数据无效")
                + f"：{objective.get('metric') or 'unknown'}",
                attempts=1,
                failures=1,
                expected={"operator": objective.get("operator"), "target": objective.get("target")},
                actual=objective.get("actual"),
                source_evidence_ids=[str(objective.get("evidence_id") or "")],
            )
        )

    for index, endpoint in enumerate(endpoint_metrics):
        failures = int(endpoint.get("failure_count") or 0)
        attempts = int(endpoint.get("request_count") or 0)
        if failures <= 0:
            continue
        signals.append(
            _signal(
                signal_id=f"request:{index + 1}",
                scope="request",
                kind="request_failed",
                severity="critical" if attempts and failures == attempts else "high",
                title=f"请求失败：{endpoint.get('method') or ''} {endpoint.get('name') or ''}".strip(),
                attempts=attempts,
                failures=failures,
                actual={"failure_rate": failures / attempts if attempts else None},
            )
        )

    protocol_attempts = int(protocol_metrics.get("attempt_count") or 0)
    for index, metric in enumerate(protocol_metrics.get("metrics") or []):
        if not isinstance(metric, dict):
            continue
        attempts = int(metric.get("attempt_count") or protocol_attempts)
        matched = int(metric.get("matched_count") or 0)
        missing = int(metric.get("missing_count") or 0)
        failed = int(metric.get("failure_count") or 0)
        unsuccessful = max(failed, missing, max(0, attempts - matched))
        if attempts <= 0 or unsuccessful <= 0:
            continue
        signals.append(
            _signal(
                signal_id=f"protocol_metric:{index + 1}",
                scope="protocol_metric",
                kind="metric_unmatched" if missing else "metric_failed",
                severity="critical" if unsuccessful == attempts else "high",
                title=f"协议业务指标未成功：{metric.get('name') or metric.get('metric_id') or 'unknown'}",
                attempts=attempts,
                failures=unsuccessful,
                expected={"matched_count": attempts},
                actual={
                    "matched_count": matched,
                    "missing_count": missing,
                    "failure_count": failed,
                },
            )
        )

    for index, failure in enumerate(evidence.get("failures") or []):
        if not isinstance(failure, dict):
            continue
        count = int(failure.get("count") or 1)
        signals.append(
            _signal(
                signal_id=f"failure_detail:{index + 1}",
                scope="request",
                kind="request_failure_detail",
                severity="high",
                title=str(failure.get("reason") or "请求失败明细"),
                attempts=count,
                failures=count,
                actual={
                    "method": failure.get("method"),
                    "request_name": failure.get("request_name"),
                    "status_code": failure.get("sample_status_code"),
                },
            )
        )

    for index, exception in enumerate(evidence.get("exceptions") or []):
        if not isinstance(exception, dict):
            continue
        count = int(exception.get("count") or 1)
        signals.append(
            _signal(
                signal_id=f"exception:{index + 1}",
                scope="runtime",
                kind="runtime_exception",
                severity="high",
                title=str(exception.get("message") or exception.get("exception_type") or "运行异常"),
                attempts=count,
                failures=count,
                actual=exception,
            )
        )

    for issue in quality.get("issues") or []:
        issue = str(issue)
        if issue == "run_manually_stopped":
            continue
        signals.append(
            _signal(
                signal_id=f"quality:{len(signals) + 1}",
                scope="data_quality",
                kind="data_quality_invalid" if quality.get("status") == "invalid" else "data_quality_limited",
                severity="critical" if quality.get("status") == "invalid" else "medium",
                title=f"分析数据质量问题：{issue}",
                attempts=1,
                failures=1,
                actual={"issue": issue},
                source_evidence_ids=["quality:summary"],
            )
        )
    return signals


def _objective_breached(objective: dict[str, Any]) -> bool:
    actual = objective.get("actual")
    target = objective.get("target")
    if actual is None or target is None:
        return False
    try:
        return float(actual) > float(target) if objective.get("operator") == "lte" else float(actual) < float(target)
    except (TypeError, ValueError):
        return False


def blocking_signal_ids(snapshot: dict[str, Any]) -> set[str]:
    return {
        str(item.get("evidence_id"))
        for item in snapshot.get("failure_signals") or []
        if isinstance(item, dict) and item.get("severity") in BLOCKING_SEVERITIES and item.get("evidence_id")
    }


def _signal(
    *,
    signal_id: str,
    scope: str,
    kind: str,
    severity: str,
    title: str,
    attempts: int,
    failures: int,
    expected: Any = None,
    actual: Any = None,
    source_evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "evidence_id": f"signal:{signal_id}",
        "scope": scope,
        "kind": kind,
        "severity": severity,
        "title": title,
        "attempt_count": attempts,
        "failure_count": failures,
        "failure_rate": failures / attempts if attempts else None,
        "expected": expected,
        "actual": actual,
        "source_evidence_ids": [item for item in source_evidence_ids or [] if item],
    }


__all__ = ["blocking_signal_ids", "build_failure_signals"]
