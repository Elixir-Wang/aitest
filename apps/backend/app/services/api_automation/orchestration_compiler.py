"""Compile an AI semantic plan into a deterministic, validated scenario plan."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.agents.api_automation.orchestration.schemas import (
    GeneratedValueSource,
    ScenarioBinding,
    ScenarioExtractor,
    ScenarioPlanInput,
    ScenarioPlanResult,
    SecretValueSource,
    StatusCodeAssertion,
)
from app.schemas.api_automation import ApiScenarioAiReviewPlan
from app.services.api_automation.orchestration_asset_analysis import dependency_candidates, request_slots, response_slots


COMPILER_VERSION = 2
_SUCCESS_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}


def compile_plan(
    plan: ScenarioPlanResult,
    endpoints: list[dict[str, Any]],
    environment: dict[str, Any],
    *,
    require_cleanup: bool = False,
) -> ScenarioPlanResult:
    """Normalize only evidence-backed defaults; ambiguity remains an unresolved item."""
    compiled = ScenarioPlanResult.model_validate(deepcopy(plan.model_dump()))
    endpoint_by_id = {str(endpoint["id"]): endpoint for endpoint in endpoints}
    nodes = [node.model_copy(deep=True) for node in compiled.nodes]
    # Diagnostics are compiler-owned. Model-authored warnings can be based on
    # metadata it was not given and must not become executable-plan truth.
    unresolved: list[str] = []
    warnings: list[str] = []
    inputs = {item.name: item for item in compiled.inputs}
    edges = {(edge.source, edge.target, edge.condition) for edge in compiled.edges}

    environment_keys = {str(item.get("key")): item for item in environment.get("variables", [])}
    environment_secret_keys = {str(item.get("key")) for item in environment.get("secrets", [])}
    for index, node in enumerate(nodes):
        endpoint = endpoint_by_id.get(str(node.endpoint_id or ""))
        if not endpoint or node.type != "api_request":
            continue
        if not node.name:
            node.name = str(endpoint.get("summary") or f"{endpoint.get('method', '')} {endpoint.get('path', '')}").strip()
        if node.type == "api_request" and not node.assertions:
            status = _first_success_status(endpoint)
            if status:
                node.assertions = [StatusCodeAssertion(type="status_code", expected=status)]
                warnings.append(f"步骤 {node.id} 已由编译器补充 {status} 状态码断言。")
        node.bindings = _normalize_and_dedupe_bindings(node.bindings, endpoint)
        node.bindings = _apply_asset_values(node.bindings, endpoint)
        node.extractors = _calibrate_extractors(node.extractors, endpoint)
        slot_by_target = {(slot.location, slot.path): slot for slot in request_slots(endpoint)}
        bound_targets = {(binding.target.location, binding.target.path) for binding in node.bindings}
        for target in request_slots(endpoint):
            key = (target.location, target.path)
            if target.sensitive or target.name not in environment_keys:
                continue
            environment_binding = ScenarioBinding.model_validate(
                {"target": {"location": target.location, "path": target.path}, "source": {"type": "environment", "key": target.name}}
            )
            node.bindings = [binding for binding in node.bindings if (binding.target.location, binding.target.path) != key]
            node.bindings.append(environment_binding)
            bound_targets.add(key)
        for binding in node.bindings:
            if binding.source.type != "user_input":
                continue
            slot = slot_by_target.get((binding.target.location, binding.target.path))
            detail = "需要运行时输入"
            if slot and slot.examples:
                detail += f"，接口示例：{slot.examples[0]}"
            if slot and slot.nested_schema:
                detail += "；字段格式由接口的嵌套 JSON Schema 定义"
            warnings.append(f"步骤 {node.id} 的 {binding.target.location} {binding.target.path} {detail}。")
        for target in request_slots(endpoint):
            key = (target.location, target.path)
            if key in bound_targets or not target.required:
                continue
            if target.sensitive:
                if target.name in environment_secret_keys:
                    node.bindings.append(
                        ScenarioBinding.model_validate(
                            {"target": {"location": target.location, "path": target.path}, "source": {"type": "secret", "key": target.name}}
                        )
                    )
                    bound_targets.add(key)
                else:
                    unresolved.append(f"步骤 {node.id} 的敏感必填参数 {target.path} 缺少环境密钥。")
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
            elif target.has_default or len(target.enum) == 1:
                bound_targets.add(key)
            else:
                node.bindings.append(
                    ScenarioBinding.model_validate(
                        {"target": {"location": target.location, "path": target.path}, "source": _mock_value_source(target).model_dump(exclude_none=True)}
                    )
                )
                warnings.append(f"步骤 {node.id} 的必填参数 {target.path} 已填充 mock 数据。")
                bound_targets.add(key)

    if require_cleanup and any(
        node.type == "api_request"
        and str((endpoint_by_id.get(str(node.endpoint_id)) or {}).get("method", "")).upper() in {"POST", "PUT", "PATCH", "DELETE"}
        for node in nodes
    ) and not any(node.phase == "cleanup" for node in nodes):
        unresolved.append("主流程包含写操作，但未提供 cleanup 步骤。")

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


def compile_review_plan(
    review: ApiScenarioAiReviewPlan,
    endpoints: list[dict[str, Any]],
    environment: dict[str, Any],
    *,
    require_cleanup: bool = False,
) -> ScenarioPlanResult:
    nodes = []
    edges = set()
    for step in sorted(review.steps, key=lambda item: item.order):
        bindings = []
        for group in step.field_groups:
            for field in group.fields:
                if field.resolved is None:
                    continue
                bindings.append(
                    ScenarioBinding.model_validate(
                        {
                            "target": {"location": group.location, "path": field.path},
                            "source": field.resolved.model_dump(exclude_none=True),
                            "required": field.required,
                        }
                    )
                )
                if field.resolved.type == "step_output":
                    edges.add((field.resolved.step_id, step.step_id, "success"))
        for dependency in step.depends_on:
            edges.add((dependency, step.step_id, "success"))
        nodes.append(
            {
                "id": step.step_id,
                "type": "api_request",
                "endpoint_id": step.endpoint_id,
                "phase": step.phase,
                "name": step.name,
                "bindings": [binding.model_dump(exclude_none=True) for binding in bindings],
                "extractors": [extractor.model_dump(exclude_none=True) for extractor in step.extractors],
                "assertions": [assertion.model_dump(exclude_none=True) for assertion in step.assertions],
                "on_failure": step.on_failure,
                "enabled": step.enabled,
            }
        )
    semantic_plan = ScenarioPlanResult.model_validate(
        {
            "scenario_name": review.scenario_name,
            "description": review.description,
            "nodes": nodes,
            "edges": [
                {"source": source, "target": target, "condition": condition}
                for source, target, condition in sorted(edges)
            ],
        }
    )
    return compile_plan(semantic_plan, endpoints, environment, require_cleanup=require_cleanup)


def _candidate_target(candidate: dict[str, Any]) -> tuple[str, str]:
    target = candidate["target"]
    return str(target["location"]), str(target["path"])


def _mock_value_source(target) -> LiteralValueSource | GeneratedValueSource:
    name = target.name.lower()
    if target.examples:
        return LiteralValueSource(type="literal", value=target.examples[0])
    if target.value_type == "boolean":
        return LiteralValueSource(type="literal", value=True)
    if target.value_type == "integer":
        return LiteralValueSource(type="literal", value=1)
    if target.value_type == "number":
        return LiteralValueSource(type="literal", value=1.0)
    if target.value_type == "array":
        return LiteralValueSource(type="literal", value=[])
    if target.value_type == "object":
        return LiteralValueSource(type="literal", value={})
    if "email" in name:
        return LiteralValueSource(type="literal", value="mock@example.test")
    if any(token in name for token in ("time", "date", "timestamp")):
        return GeneratedValueSource(type="generated", generator="timestamp_iso")
    if name == "id" or name.endswith("_id") or "uuid" in name:
        return GeneratedValueSource(type="generated", generator="uuid4")
    return LiteralValueSource(type="literal", value=f"mock_{_variable_name(target.name, 'value')}")


def _normalize_and_dedupe_bindings(bindings: list[ScenarioBinding], endpoint: dict[str, Any]) -> list[ScenarioBinding]:
    normalized: dict[tuple[str, str], ScenarioBinding] = {}
    for binding in bindings:
        target = _normalize_target(binding.target, endpoint)
        candidate = _normalize_binding_transform(binding.model_copy(update={"target": target}))
        candidate = _normalize_fixed_enum_binding(candidate, endpoint)
        key = (target.location, target.path)
        previous = normalized.get(key)
        if previous is None or _binding_priority(candidate) > _binding_priority(previous):
            normalized[key] = candidate
    return list(normalized.values())


def _normalize_binding_transform(binding: ScenarioBinding) -> ScenarioBinding:
    if binding.transform != "json_encode" or binding.source.type != "literal":
        return binding
    value = binding.source.value
    if not isinstance(value, str):
        return binding
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return binding
    if not isinstance(decoded, (dict, list)):
        return binding
    payload = binding.model_dump(exclude_none=True)
    payload["source"]["value"] = decoded
    return ScenarioBinding.model_validate(payload)


def _normalize_fixed_enum_binding(binding: ScenarioBinding, endpoint: dict[str, Any]) -> ScenarioBinding:
    schema = _target_schema(endpoint, binding.target.location, binding.target.path)
    enum_values = schema.get("enum") if isinstance(schema, dict) else None
    if not isinstance(enum_values, list) or len(enum_values) != 1:
        return binding
    payload = binding.model_dump(exclude_none=True)
    payload["source"] = {"type": "literal", "value": enum_values[0]}
    return ScenarioBinding.model_validate(payload)


def _target_schema(endpoint: dict[str, Any], location: str, path: str) -> dict[str, Any] | None:
    if location in {"path", "query", "header", "cookie"}:
        name = path.removeprefix("/").replace("~1", "/").replace("~0", "~")
        for parameter in endpoint.get("parameters") or []:
            if parameter.get("in") == location and str(parameter.get("name") or "") == name:
                schema = parameter.get("schema")
                return schema if isinstance(schema, dict) else parameter
        return None
    request_body = endpoint.get("request_body") or {}
    content = request_body.get("content") if isinstance(request_body, dict) else {}
    media_type = {
        "json_body": "application/json",
        "form": "application/x-www-form-urlencoded",
        "multipart": "multipart/form-data",
    }.get(location)
    schema = (content or {}).get(media_type, {}).get("schema") if media_type else request_body.get("schema")
    if not isinstance(schema, dict):
        return None
    current = schema
    for part in [item.replace("~1", "/").replace("~0", "~") for item in path.split("/") if item]:
        properties = current.get("properties") if isinstance(current, dict) else None
        if not isinstance(properties, dict) or part not in properties:
            return None
        current = properties[part]
        if isinstance(current, dict) and isinstance(current.get("x-json-schema"), dict):
            current = current["x-json-schema"]
    return current if isinstance(current, dict) else None


def _apply_asset_values(bindings: list[ScenarioBinding], endpoint: dict[str, Any]) -> list[ScenarioBinding]:
    slots = {(slot.location, slot.path): slot for slot in request_slots(endpoint)}
    normalized: list[ScenarioBinding] = []
    for binding in bindings:
        slot = slots.get((binding.target.location, binding.target.path))
        source = binding.source
        if slot and not slot.sensitive and len(slot.enum) == 1 and source.type in {"user_input", "literal"}:
            continue
        if slot and not slot.sensitive and slot.has_default and source.type in {"user_input", "literal"}:
            continue
        normalized.append(binding.model_copy(update={"source": source}))
    return normalized


def _normalize_target(target, endpoint: dict[str, Any]):
    slots = request_slots(endpoint)
    matching = [slot for slot in slots if slot.path == target.path]
    if not matching:
        return target
    if any(slot.location == target.location for slot in matching):
        return target
    body_locations = {"json_body", "form", "multipart"}
    matching_body_locations = {slot.location for slot in matching if slot.location in body_locations}
    if target.location in body_locations and len(matching_body_locations) == 1:
        return target.model_copy(update={"location": matching_body_locations.pop()})
    aliases = {"form": "multipart", "multipart": "form"}
    alias = aliases.get(target.location)
    if alias and any(slot.location == alias for slot in matching):
        return target.model_copy(update={"location": alias})
    # Older plans used `form` for JSON bodies. Canonicalize this only when the
    # asset has exactly one matching path and no form/multipart slot exists.
    if target.location == "form" and len(matching) == 1 and matching[0].location == "json_body":
        return target.model_copy(update={"location": "json_body"})
    return target


def _binding_priority(binding: ScenarioBinding) -> int:
    source_type = binding.source.type
    return {
        "secret": 40,
        "step_output": 30,
        "environment": 20,
        "scenario": 15,
        "generated": 12,
        "object": 10,
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
