import json
from collections.abc import Callable
from typing import Any

from app.agents.model_selection import (
    build_agent_model,
    resolve_model_selection,
    thinking_disabled_extra_body,
)
from app.agents.performance_testing.diagnosis.agent import performance_diagnosis_agent
from app.schemas.performance_analysis import PerformanceDiagnosis


CAPABILITY_ID = "performance_report_analysis"
PROMPT_VERSION = "v3-evidence-contract"

_ANALYSIS_SECTION_KEYS = (
    "test_validity",
    "stage_analysis",
    "capacity_analysis",
    "latency_analysis",
    "failure_analysis",
    "baseline_comparison",
    "resource_correlation",
)


def diagnose_performance(
    evidence: dict[str, Any],
    *,
    repair_context: dict[str, Any] | None = None,
    selection_resolver: Callable[[str], Any] = resolve_model_selection,
    model_builder: Callable[[Any], Any] = build_agent_model,
    agent_factory: Callable[[Any], Any] = performance_diagnosis_agent,
) -> tuple[PerformanceDiagnosis, str]:
    selection = selection_resolver(CAPABILITY_ID)
    model = model_builder(
        selection,
        extra_body=thinking_disabled_extra_body(selection),
    )
    agent = agent_factory(model)
    input_payload = {**evidence, "evidence_contract": _evidence_contract(evidence)}
    content = _prompt_content(input_payload, repair_context)
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": content,
                }
            ]
        }
    )
    structured = result.get("structured_response") if isinstance(result, dict) else None
    diagnosis = structured if isinstance(structured, PerformanceDiagnosis) else PerformanceDiagnosis.model_validate(structured)
    return diagnosis, str(selection.model)


def _evidence_contract(evidence: dict[str, Any]) -> dict[str, Any]:
    metric_snapshot = evidence.get("metric_snapshot") if isinstance(evidence.get("metric_snapshot"), dict) else {}
    allowed_evidence_ids = sorted(
        {
            str(item.get("evidence_id"))
            for item in metric_snapshot.get("evidence_index", [])
            if isinstance(item, dict) and item.get("evidence_id")
        }
    )
    empty_sections = [
        key
        for key in _ANALYSIS_SECTION_KEYS
        if key in metric_snapshot and metric_snapshot.get(key) in (None, [], {})
    ]
    return {
        "allowed_evidence_ids": allowed_evidence_ids,
        "empty_sections": empty_sections,
        "reference_rules": [
            "evidence_refs 只能逐字引用 allowed_evidence_ids",
            "字段名称和 JSON 路径不是 evidence_id",
            "empty_sections 中的字段不可作为证据引用",
            "没有合法证据时减少 finding 或补充 missing_evidence",
        ],
    }


def _prompt_content(input_payload: dict[str, Any], repair_context: dict[str, Any] | None) -> str:
    if repair_context is None:
        return (
            "<performance_analysis_input>\n"
            f"{json.dumps(input_payload, ensure_ascii=False, sort_keys=True)}\n"
            "</performance_analysis_input>"
        )
    repair_payload = {
        "input": input_payload,
        "previous_diagnosis": repair_context.get("previous_diagnosis") or {},
        "unknown_evidence_refs": repair_context.get("unknown_evidence_refs") or [],
        "unknown_finding_refs": repair_context.get("unknown_finding_refs") or [],
        "instructions": [
            "返回完整 PerformanceDiagnosis",
            "只修正非法引用及受其影响的结论",
            "不得修改确定性指标和 verdict",
            "不得增加输入中不存在的证据",
            "没有合法证据时删除对应 finding 或补充 missing_evidence",
        ],
    }
    return (
        "<performance_analysis_repair>\n"
        f"{json.dumps(repair_payload, ensure_ascii=False, sort_keys=True)}\n"
        "</performance_analysis_repair>"
    )


__all__ = ["CAPABILITY_ID", "PROMPT_VERSION", "diagnose_performance"]
