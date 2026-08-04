from __future__ import annotations

from copy import deepcopy


def repair_business_step_mapping(plan: dict, case_data: dict) -> dict | None:
    source_steps = {
        str(step.get("id", "")): str(step.get("action", ""))
        for step in case_data.get("steps", [])
        if isinstance(step, dict) and step.get("id")
    }
    if not source_steps:
        return None

    repaired = deepcopy(plan)
    repaired_steps = []
    for step in plan.get("steps", []):
        if not isinstance(step, dict):
            return None
        source_step_id = str(step.get("source_step_id", "")).strip()
        business_step_id = _resolve_business_step_id(source_step_id, source_steps)
        if business_step_id is None:
            return None
        next_step = dict(step)
        next_step["business_step_id"] = business_step_id
        next_step["title"] = source_steps[business_step_id]
        repaired_steps.append(next_step)

    repaired["schema_version"] = "v2"
    repaired["steps"] = repaired_steps
    return repaired


def _resolve_business_step_id(source_step_id: str, source_steps: dict[str, str]) -> str | None:
    if source_step_id in source_steps:
        return source_step_id
    candidates = [
        step_id
        for step_id in source_steps
        if source_step_id.startswith(f"{step_id}-")
    ]
    return candidates[0] if len(candidates) == 1 else None


__all__ = ["repair_business_step_mapping"]
