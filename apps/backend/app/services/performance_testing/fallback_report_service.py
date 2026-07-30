from __future__ import annotations

from typing import Any

from app.schemas.performance_analysis import GenerationWarning


def build_fallback_report_snapshot(
    metric_snapshot: dict[str, Any],
    *,
    warnings: list[GenerationWarning | dict[str, Any]],
) -> dict[str, Any]:
    aggregate = metric_snapshot.get("aggregate") if isinstance(metric_snapshot.get("aggregate"), dict) else {}
    verdict = str(metric_snapshot.get("verdict") or "indeterminate")
    warning_payload = [
        warning.model_dump(mode="json") if isinstance(warning, GenerationWarning) else dict(warning)
        for warning in warnings
    ]
    return {
        "schema_version": 1,
        "verdict": verdict,
        "verdict_reasons": [
            str(item.get("evidence_id"))
            for item in metric_snapshot.get("objectives", [])
            if isinstance(item, dict) and item.get("evidence_id")
        ],
        "executive_summary": _executive_summary(verdict, aggregate),
        "capacity_summary": _capacity_summary(metric_snapshot),
        "findings": [],
        "recommendations": [],
        "diagnosis_evidence": [],
        "generation_mode": "deterministic_fallback",
        "ai_analysis_available": False,
        "generation_warnings": warning_payload,
        "aggregate": aggregate,
        "quality": metric_snapshot.get("quality") or {},
        "objectives": metric_snapshot.get("objectives") or [],
        "series": metric_snapshot.get("series") or [],
        "stage_analysis": metric_snapshot.get("stage_analysis") or [],
        "failure_analysis": metric_snapshot.get("failure_analysis") or [],
        "latency_analysis": metric_snapshot.get("latency_analysis") or {},
        "capacity_analysis": metric_snapshot.get("capacity_analysis") or {},
    }


def _executive_summary(verdict: str, aggregate: dict[str, Any]) -> str:
    request_count = int(aggregate.get("request_count") or 0)
    failure_count = int(aggregate.get("failure_count") or 0)
    failure_rate = float(aggregate.get("failure_rate") or 0)
    result = "已配置的性能目标通过" if verdict == "pass" else "存在未通过或无法判定的性能目标"
    return (
        f"本次压测共执行 {request_count} 个请求，失败 {failure_count} 个，失败率为 {failure_rate:.2%}。"
        f"{result}。当前展示确定性基础报告，不提供未经证实的 AI 根因和自动修复建议。"
    )


def _capacity_summary(metric_snapshot: dict[str, Any]) -> str:
    analysis = metric_snapshot.get("capacity_analysis")
    if isinstance(analysis, dict) and analysis.get("reason"):
        return str(analysis["reason"])
    stable = (metric_snapshot.get("capacity") or {}).get("stable_throughput")
    if stable is None:
        return "当前证据不足以判断系统容量上限或性能拐点。"
    return f"当前运行观测到的稳定吞吐参考为 {float(stable):.2f} RPS。"


__all__ = ["build_fallback_report_snapshot"]
