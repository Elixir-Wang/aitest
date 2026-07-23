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
PROMPT_VERSION = "v2-zh"


def diagnose_performance(
    evidence: dict[str, Any],
    *,
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
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "<performance_analysis_input>\n"
                        f"{json.dumps(evidence, ensure_ascii=False, sort_keys=True)}\n"
                        "</performance_analysis_input>"
                    ),
                }
            ]
        }
    )
    structured = result.get("structured_response") if isinstance(result, dict) else None
    diagnosis = structured if isinstance(structured, PerformanceDiagnosis) else PerformanceDiagnosis.model_validate(structured)
    return diagnosis, str(selection.model)


__all__ = ["CAPABILITY_ID", "PROMPT_VERSION", "diagnose_performance"]
