from __future__ import annotations

import json
import re
import shlex
from typing import Any
from urllib.parse import urlsplit

from app.agents.api_automation.orchestration.schemas import PlannerProposal
from app.services.api_automation.orchestration_asset_analysis import normalize_request_target, request_slots


_CURL_START = re.compile(r"(?im)^\s*curl\b")
_DATA_FLAGS = {"--data", "--data-raw", "--data-binary", "-d"}
_FORM_FLAGS = {"--form", "-F"}
_HEADER_FLAGS = {"--header", "-H"}


def extract_request_examples(
    goal: str,
    endpoints: list[dict[str, Any]],
) -> dict[str, dict[tuple[str, str], dict[str, Any]]]:
    endpoint_by_path = {str(endpoint.get("path") or ""): endpoint for endpoint in endpoints}
    examples: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    starts = [match.start() for match in _CURL_START.finditer(goal)]
    for index, start in enumerate(starts):
        command = goal[start : starts[index + 1] if index + 1 < len(starts) else len(goal)]
        parsed = _parse_curl(command)
        endpoint = endpoint_by_path.get(urlsplit(parsed["url"]).path)
        if not endpoint:
            continue
        endpoint_id = str(endpoint.get("id") or "")
        target_sources = examples.setdefault(endpoint_id, {})
        parameter_names = {
            (str(parameter.get("in") or ""), str(parameter.get("name") or ""))
            for parameter in endpoint.get("parameters") or []
        }
        for name, value in parsed["headers"].items():
            if ("header", name) in parameter_names and value and value != "[REDACTED]":
                target_sources[("header", f"/{_escape_pointer(name)}")] = _literal(value)
        for name, value in parsed["form"].items():
            location, path = normalize_request_target(endpoint, "multipart", f"/{_escape_pointer(name)}")
            slot = next(
                (slot for slot in request_slots(endpoint) if (slot.location, slot.path) == (location, path)),
                None,
            )
            parsed_value = _decode_json(value) if slot and slot.nested_schema else _strip_wrapping_quotes(value)
            target_sources[(location, path)] = _source_for_value(parsed_value)
        body = _decode_json(parsed["data"])
        if isinstance(body, dict):
            for name, value in body.items():
                location, path = normalize_request_target(endpoint, "json_body", f"/{_escape_pointer(name)}")
                target_sources[(location, path)] = _source_for_value(value)
    return {endpoint_id: values for endpoint_id, values in examples.items() if values}


def apply_request_examples(
    proposal: PlannerProposal,
    examples: dict[str, dict[tuple[str, str], dict[str, Any]]],
    endpoints: list[dict[str, Any]],
) -> PlannerProposal:
    endpoint_by_id = {str(endpoint.get("id") or ""): endpoint for endpoint in endpoints}
    payload = proposal.model_dump(exclude_none=True)
    for step in payload.get("steps", []):
        endpoint = endpoint_by_id.get(str(step.get("endpoint_id") or ""))
        explicit = examples.get(str(step.get("endpoint_id") or ""), {})
        if not endpoint or not explicit:
            continue
        slots = {(slot.location, slot.path): slot for slot in request_slots(endpoint)}
        fields = step.get("fields") or []
        normalized_fields: dict[tuple[str, str], dict[str, Any]] = {}
        for field in fields:
            target = field.get("target") or {}
            key = normalize_request_target(endpoint, str(target.get("location") or ""), str(target.get("path") or ""))
            field["target"] = {"location": key[0], "path": key[1]}
            normalized_fields[key] = field
        for key, source in explicit.items():
            if source.get("type") == "object":
                normalized_fields = {
                    target: field
                    for target, field in normalized_fields.items()
                    if target == key or not (target[0] == key[0] and target[1].startswith(f"{key[1]}/"))
                }
            field = normalized_fields.get(key)
            if field and (field.get("proposal") or {}).get("type") in {
                "step_output",
                "environment",
                "secret",
                "scenario",
            }:
                continue
            slot = slots.get(key)
            normalized_fields[key] = {
                "target": {"location": key[0], "path": key[1]},
                "display_name": slot.name if slot else key[1].rsplit("/", 1)[-1],
                "required": slot.required if slot else True,
                "value_type": slot.value_type if slot else "any",
                "sensitive": slot.sensitive if slot else False,
                "proposal": source,
            }
        step["fields"] = list(normalized_fields.values())
    return PlannerProposal.model_validate(payload)


def public_request_examples(
    examples: dict[str, dict[tuple[str, str], dict[str, Any]]],
) -> list[dict[str, Any]]:
    return [
        {
            "endpoint_id": endpoint_id,
            "fields": [
                {"target": {"location": location, "path": path}, "source": source}
                for (location, path), source in fields.items()
            ],
        }
        for endpoint_id, fields in examples.items()
    ]


def _parse_curl(command: str) -> dict[str, Any]:
    tokens = shlex.split(re.sub(r"\\\s*\r?\n", " ", command), posix=True)
    result: dict[str, Any] = {"url": "", "headers": {}, "form": {}, "data": ""}
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in _HEADER_FLAGS | _FORM_FLAGS | _DATA_FLAGS | {"--url"} and index + 1 < len(tokens):
            value = tokens[index + 1]
            index += 2
            if token in _HEADER_FLAGS:
                name, separator, header_value = value.partition(":")
                if separator:
                    result["headers"][name.strip()] = header_value.strip()
            elif token in _FORM_FLAGS:
                name, separator, form_value = value.partition("=")
                if separator:
                    result["form"][name.strip()] = _strip_wrapping_quotes(form_value)
            elif token in _DATA_FLAGS:
                result["data"] = value
            else:
                result["url"] = value
            continue
        if token.startswith("http://") or token.startswith("https://"):
            result["url"] = token
        index += 1
    return result


def _decode_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    candidate = _strip_wrapping_quotes(value)
    for _ in range(3):
        try:
            return json.loads(candidate)
        except (TypeError, ValueError):
            unescaped = candidate.replace(r'\"', '"')
            if unescaped == candidate:
                break
            candidate = unescaped
    return candidate


def _source_for_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {name: _source_for_value(child) for name, child in value.items()},
        }
    return _literal(value)


def _literal(value: Any) -> dict[str, Any]:
    return {"type": "literal", "value": value}


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")
