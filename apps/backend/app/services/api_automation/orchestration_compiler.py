"""Compile an AI semantic plan into a deterministic, validated scenario plan."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.agents.api_automation.orchestration.schemas import (
    ScenarioBinding,
    ScenarioExtractor,
    ScenarioPlanInput,
    ScenarioPlanResult,
    StatusCodeAssertion,
)
from app.services.api_automation.orchestration_asset_analysis import dependency_candidates, request_slots, response_slots


COMPILER_VERSION = 2
_SUCCESS_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}


def compile_plan(plan: ScenarioPlanResult, endpoints: list[dict[str, Any]], environment: dict[str, Any]) -> ScenarioPlanResult:
    """Normalize only evidence-backed defaults; ambiguity remains an unresolved item."""
    compiled = ScenarioPlanResult.model_validate(deepcopy(plan.model_dump()))
    endpoint_by_id = {str(endpoint["id"]): endpoint for endpoint in endpoints}
    nodes = [node.model_copy(deep=True) for node in compiled.nodes]
    unresolved = list(compiled.unresolved_items)
    warnings = list(compiled.warnings)
    inputs = {item.name: item for item in compiled.inputs}
    edges = {(edge.source, edge.target, edge.condition) for edge in compiled.edges}

    environment_keys = {str(item.get("key")): item for item in environment.get("variables", [])}
    for index, node in enumerate(nodes):
        endpoint = endpoint_by_id.get(str(node.endpoint_id or ""))
        if not endpoint or node.type not in {"api_request", "poll"}:
            continue
        if not node.name:
            node.name = str(endpoint.get("summary") or f"{endpoint.get('method', '')} {endpoint.get('path', '')}").strip()
        if node.type == "api_request" and not node.assertions:
            status = _first_success_status(endpoint)
            if status:
                node.assertions = [StatusCodeAssertion(type="status_code", expected=status)]
                warnings.append(f"步骤 {node.id} 已由编译器补充 {status} 状态码断言。")
        node.bindings = _normalize_and_dedupe_bindings(node.bindings, endpoint)
        node.extractors = _calibrate_extractors(node.extractors, endpoint)
        bound_targets = {(binding.target.location, binding.target.path) for binding in node.bindings}
        for target in request_slots(endpoint):
            key = (target.location, target.path)
            if key in bound_targets or not target.required or target.sensitive:
                continue
            candidates = []
            for prior in nodes[:index]:
                source_endpoint = endpoint_by_id.get(str(prior.endpoint_id or ""))
                if source_endpoint:
                    candidates.extend((prior, item) for item in dependency_candidates(source_endpoint, endpoint) if _candidate_target(item) == key)
            candidates.sort(key=lambda item: -float(item[1]["score"]))
            if candidates and float(candidates[0][1]["score"]) >= 0.9 and (len(candidates) == 1 or candidates[0][1]["score"] > candidates[1][1]["score"]):
                source_node, candidate = candidates[0]
                output = candidate["output"]
                variable = _variable_name(output["name"], source_node.id)
                if not any(extractor.name == variable for extractor in source_node.extractors):
                    if output["location"] == "sse_event_json":
                        # Event names are not inferable from a schema: leave it unresolved instead.
                        unresolved.append(f"步骤 {source_node.id} 的 SSE 输出 {output['path']} 缺少 event 名称。")
                        continue
                    source_node.extractors.append(
                        ScenarioExtractor(name=variable, source=output["location"], path=output["path"], value_type=output["value_type"])
                    )
                node.bindings.append(
                    ScenarioBinding.model_validate(
                        {"target": {"location": target.location, "path": target.path}, "source": {"type": "step_output", "step_id": source_node.id, "variable": variable}}
                    )
                )
                edges.add((source_node.id, node.id, "success"))
                bound_targets.add(key)
            elif target.name in environment_keys:
                node.bindings.append(
                    ScenarioBinding.model_validate(
                        {"target": {"location": target.location, "path": target.path}, "source": {"type": "environment", "key": target.name}}
                    )
                )
                bound_targets.add(key)
            else:
                input_name = _variable_name(target.name, node.id)
                inputs.setdefault(input_name, ScenarioPlanInput(name=input_name, label=target.name, value_type=target.value_type, required=True, description=f"步骤 {node.id} 的必填参数 {target.path}"))
                node.bindings.append(
                    ScenarioBinding.model_validate(
                        {"target": {"location": target.location, "path": target.path}, "source": {"type": "user_input", "name": input_name}}
                    )
                )
                unresolved.append(f"步骤 {node.id} 的必填参数 {target.path} 需要用户输入。")
                bound_targets.add(key)

    return ScenarioPlanResult.model_validate(
        {
            "schema_version": 2,
            "graph_version": 1,
            "scenario_name": compiled.scenario_name,
            "description": compiled.description,
            "inputs": [item.model_dump(exclude_none=True) for item in sorted(inputs.values(), key=lambda item: item.name)],
            "nodes": [node.model_dump(exclude_none=True) for node in nodes],
            "edges": [{"source": source, "target": target, "condition": condition} for source, target, condition in sorted(edges)],
            "assumptions": compiled.assumptions,
            "warnings": _unique(warnings),
            "unresolved_items": _unique(unresolved),
            "confidence": compiled.confidence,
        }
    )


def _candidate_target(candidate: dict[str, Any]) -> tuple[str, str]:
    target = candidate["target"]
    return str(target["location"]), str(target["path"])


def _normalize_and_dedupe_bindings(bindings: list[ScenarioBinding], endpoint: dict[str, Any]) -> list[ScenarioBinding]:
    normalized: dict[tuple[str, str], ScenarioBinding] = {}
    for binding in bindings:
        target = _normalize_target(binding.target, endpoint)
        candidate = binding.model_copy(update={"target": target})
        key = (target.location, target.path)
        previous = normalized.get(key)
        if previous is None or _binding_priority(candidate) > _binding_priority(previous):
            normalized[key] = candidate
    return list(normalized.values())


def _normalize_target(target, endpoint: dict[str, Any]):
    slots = request_slots(endpoint)
    matching = [slot for slot in slots if slot.path == target.path]
    if not matching:
        return target
    if any(slot.location == target.location for slot in matching):
        return target
    aliases = {"form": "multipart", "multipart": "form"}
    alias = aliases.get(target.location)
    if alias and any(slot.location == alias for slot in matching):
        return target.model_copy(update={"location": alias})
    return target


def _binding_priority(binding: ScenarioBinding) -> int:
    source_type = binding.source.type
    return {
        "secret": 40,
        "step_output": 30,
        "environment": 20,
        "scenario": 15,
        "generated": 12,
        "user_input": 10,
        "literal": 5,
    }.get(source_type, 0)


def _calibrate_extractors(extractors: list[ScenarioExtractor], endpoint: dict[str, Any]) -> list[ScenarioExtractor]:
    slots = response_slots(endpoint)
    calibrated: list[ScenarioExtractor] = []
    for extractor in extractors:
        candidates = [
            slot
            for slot in slots
            if slot.name == extractor.name
            and slot.location == extractor.source
            and (extractor.value_type == "any" or slot.value_type in {extractor.value_type, "any"})
        ]
        if len(candidates) == 1 and candidates[0].location != "sse_event_json":
            slot = candidates[0]
            extractor = extractor.model_copy(update={"path": slot.path, "value_type": slot.value_type})
        calibrated.append(extractor)
    return calibrated


def _first_success_status(endpoint: dict[str, Any]) -> int | None:
    for status in endpoint.get("responses", {}) or {}:
        value = str(status)
        if value.isdigit() and int(value) in range(200, 300):
            return int(value)
    return 200 if str(endpoint.get("method", "")).upper() in _SUCCESS_METHODS else None


def _variable_name(name: str, step_id: str) -> str:
    normalized = "".join(char if char.isalnum() or char == "_" else "_" for char in name.lower()).strip("_")
    return normalized or f"value_{step_id.replace('-', '_')}"


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
