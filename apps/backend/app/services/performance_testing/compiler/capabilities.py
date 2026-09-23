from dataclasses import dataclass

from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan


@dataclass(frozen=True)
class ScriptCapabilities:
    target_type: str
    uses_sse: bool
    uses_bindings: bool
    uses_extractors: bool
    uses_conditions: bool
    uses_assignments: bool
    uses_wait_steps: bool
    uses_data_rows: bool
    uses_dynamic_values: bool
    uses_load_shape: bool
    uses_circuit_breaker: bool


def analyze_capabilities(plan: LocustScriptPlan) -> ScriptCapabilities:
    requests = []
    step_types: set[str] = set()
    bindings = False
    extractors = False
    for step in plan.steps:
        step_types.add(step.step_type)
        bindings = bindings or bool(step.bindings)
        extractors = extractors or bool(step.extractors)
        if step.request is not None:
            requests.append(step.request)
    if plan.request is not None:
        requests.append(plan.request)
    raw_plan = plan.model_dump(mode="json")
    return ScriptCapabilities(
        target_type=plan.target_type,
        uses_sse=any(request.transport == "sse" for request in requests),
        uses_bindings=bindings,
        uses_extractors=extractors,
        uses_conditions="condition" in step_types,
        uses_assignments="assign" in step_types,
        uses_wait_steps="wait" in step_types,
        uses_data_rows=bool(plan.data.json_rows),
        uses_dynamic_values=any(
            (isinstance(value, str) and "${" in value)
            or (isinstance(value, dict) and value.get("type") == "generated")
            for value in _walk_values(raw_plan)
        ),
        uses_load_shape=plan.load.mode != "fixed",
        uses_circuit_breaker=bool(plan.circuit_breaker.get("enabled")) and plan.load.mode != "fixed",
    )


def _walk_values(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_values(item)
    else:
        yield value
