"""Deterministic, value-free API asset analysis for scenario orchestration."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable


_SENSITIVE_KEY_RE = re.compile(r"(?:authorization|cookie|token|secret|password|api[_-]?key|key)$", re.IGNORECASE)
_SUCCESS_STATUS_RE = re.compile(r"^2(?:\d\d|XX)$")
MODEL_SUMMARY_SLOT_LIMIT = 24


@dataclass(frozen=True)
class AssetSlot:
    name: str
    location: str
    path: str
    value_type: str = "any"
    required: bool = False
    sensitive: bool = False
    response_status: str = ""
    content_type: str = ""
    default_value: Any = None
    has_default: bool = False
    enum: tuple[Any, ...] = ()
    examples: tuple[Any, ...] = ()
    nested_schema: dict[str, Any] | None = None
    event_name: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "location": self.location,
            "path": self.path,
            "value_type": self.value_type,
            "required": self.required,
            "sensitive": self.sensitive,
            "response_status": self.response_status,
            "content_type": self.content_type,
            "has_default": self.has_default and not self.sensitive,
            "default_value": self.default_value if self.has_default and not self.sensitive else None,
            "enum": list(self.enum) if not self.sensitive else [],
            "examples": list(self.examples) if not self.sensitive else [],
            "nested_schema": self.nested_schema if self.nested_schema and not self.sensitive else None,
            "event_name": self.event_name,
        }


def endpoint_fingerprint(endpoints: Iterable[dict[str, Any]]) -> str:
    projection = [
        {
            "id": endpoint.get("id"),
            "method": endpoint.get("method"),
            "path": endpoint.get("path"),
            "parameters": endpoint.get("parameters", []),
            "request_body": endpoint.get("request_body", {}),
            "responses": endpoint.get("responses", {}),
            "updated_at": endpoint.get("updated_at", ""),
        }
        for endpoint in sorted(endpoints, key=lambda item: str(item.get("id", "")))
    ]
    return hashlib.sha256(json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def endpoint_summary(endpoint: dict[str, Any]) -> dict[str, Any]:
    """Small model-safe summary. Detailed schemas stay in compiler-owned analysis."""
    request = request_slots(endpoint)
    response = response_slots(endpoint)
    return {
        "id": endpoint.get("id", ""),
        "method": endpoint.get("method", ""),
        "path": endpoint.get("path", ""),
        "summary": str(endpoint.get("summary", ""))[:300],
        "description": str(endpoint.get("description", ""))[:500],
        "tags": list(endpoint.get("tags", []))[:20],
        "request_slot_count": len(request),
        "response_slot_count": len(response),
        "request_slots": [_model_slot_summary(slot) for slot in request[:MODEL_SUMMARY_SLOT_LIMIT]],
        "response_slots": [_model_slot_summary(slot) for slot in response[:MODEL_SUMMARY_SLOT_LIMIT]],
    }


def _model_slot_summary(slot: AssetSlot) -> dict[str, Any]:
    """Bounded slot projection for the model; compiler still receives full schemas."""
    return {
        "name": slot.name,
        "location": slot.location,
        "path": slot.path,
        "value_type": slot.value_type,
        "required": slot.required,
        "sensitive": slot.sensitive,
        "response_status": slot.response_status,
        "content_type": slot.content_type,
        "has_default": slot.has_default and not slot.sensitive,
        "default_value": _bounded_model_value(slot.default_value) if slot.has_default and not slot.sensitive else None,
        "enum": [_bounded_model_value(value) for value in slot.enum[:10]] if not slot.sensitive else [],
        "examples": [_bounded_model_value(value) for value in slot.examples[:2]] if not slot.sensitive else [],
        "event_name": slot.event_name,
    }


def _bounded_model_value(value: Any) -> Any:
    if isinstance(value, str):
        return value[:200]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return None


def request_slots(endpoint: dict[str, Any]) -> list[AssetSlot]:
    slots: list[AssetSlot] = []
    for parameter in endpoint.get("parameters", []) or []:
        if not isinstance(parameter, dict):
            continue
        name = str(parameter.get("name") or "").strip()
        location = _parameter_location(str(parameter.get("in") or ""))
        if not name or not location:
            continue
        schema = parameter.get("schema") if isinstance(parameter.get("schema"), dict) else parameter
        slots.append(
            AssetSlot(
                name=name,
                location=location,
                path=f"/{_escape_pointer(name)}",
                value_type=_schema_type(schema),
                required=bool(parameter.get("required")),
                sensitive=_is_sensitive(name, schema),
                **_slot_metadata(schema),
            )
        )
    request_body = endpoint.get("request_body") if isinstance(endpoint.get("request_body"), dict) else {}
    content = request_body.get("content") if isinstance(request_body.get("content"), dict) else {}
    if not content and isinstance(request_body.get("schema"), dict):
        content = {str(request_body.get("content_type") or "application/json"): {"schema": request_body["schema"]}}
    for content_type, media in content.items():
        schema = media.get("schema") if isinstance(media, dict) and isinstance(media.get("schema"), dict) else {}
        location = _body_location(str(content_type))
        slots.extend(_schema_slots(schema, location, content_type=str(content_type), required=False))
    return _dedupe_slots(slots)


def response_slots(endpoint: dict[str, Any]) -> list[AssetSlot]:
    slots: list[AssetSlot] = []
    for status, response in (endpoint.get("responses") or {}).items():
        if not _SUCCESS_STATUS_RE.match(str(status)) or not isinstance(response, dict):
            continue
        headers = response.get("headers") if isinstance(response.get("headers"), dict) else {}
        for name, header in headers.items():
            schema = header.get("schema") if isinstance(header, dict) and isinstance(header.get("schema"), dict) else {}
            slots.append(AssetSlot(str(name), "header", f"/{_escape_pointer(str(name))}", _schema_type(schema), response_status=str(status)))
        content = response.get("content") if isinstance(response.get("content"), dict) else {}
        for content_type, media in content.items():
            schema = media.get("schema") if isinstance(media, dict) and isinstance(media.get("schema"), dict) else {}
            if "event-stream" in str(content_type).lower():
                event_schema = media.get("x-event-data-schema") if isinstance(media, dict) else None
                schema = event_schema if isinstance(event_schema, dict) else schema
                slots.extend(_schema_slots(schema, "sse_event_json", content_type=str(content_type), response_status=str(status)))
            else:
                slots.extend(_schema_slots(schema, "json_body", content_type=str(content_type), response_status=str(status)))
    return _dedupe_slots(slots)


def dependency_candidates(source_endpoint: dict[str, Any], target_endpoint: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for output in response_slots(source_endpoint):
        for target in request_slots(target_endpoint):
            score = _slot_score(output, target)
            if score < 0.65:
                continue
            candidates.append({"output": output.public(), "target": target.public(), "score": score})
    return sorted(candidates, key=lambda item: (-item["score"], item["output"]["path"], item["target"]["path"]))


def environment_schema_projection(row: Any | None) -> dict[str, Any]:
    """Expose configuration shape only. Values, URL and headers are deliberately absent."""
    if row is None:
        return {"configured": False, "variables": [], "secrets": [], "auth_type": "none"}
    variables = _loads_row_json(row, "variables_json")
    auth_config = _loads_row_json(row, "auth_config_json")
    secrets = sorted(_secret_keys(str(row["auth_type"] or "none"), auth_config))
    return {
        "configured": True,
        "id": str(row["id"]),
        "name": str(row["name"]),
        "auth_type": str(row["auth_type"] or "none"),
        "variables": [
            {"key": str(key), "value_type": _python_value_type(value), "configured": value not in (None, "")}
            for key, value in sorted(variables.items())
        ],
        "secrets": [{"key": key, "configured": True} for key in secrets],
    }


def _schema_slots(schema: dict[str, Any], location: str, *, content_type: str = "", response_status: str = "", required: bool = False, prefix: str = "") -> list[AssetSlot]:
    encoded_schema = schema.get("x-json-schema") if isinstance(schema.get("x-json-schema"), dict) else None
    if prefix and encoded_schema:
        name = prefix.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
        return [
            AssetSlot(name, location, prefix, _schema_type(schema), required, _is_sensitive(name, schema), response_status, content_type),
            *_schema_slots(
                encoded_schema,
                location,
                content_type=content_type,
                response_status=response_status,
                required=required,
                prefix=prefix,
            ),
        ]
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required_names = set(schema.get("required") if isinstance(schema.get("required"), list) else [])
    if properties:
        slots: list[AssetSlot] = []
        for name, child in properties.items():
            child_schema = child if isinstance(child, dict) else {}
            path = f"{prefix}/{_escape_pointer(str(name))}"
            child_required = required or str(name) in required_names
            nested = _schema_slots(child_schema, location, content_type=content_type, response_status=response_status, required=child_required, prefix=path)
            if nested:
                slots.extend(nested)
            else:
                slots.append(AssetSlot(str(name), location, path, _schema_type(child_schema), child_required, _is_sensitive(str(name), child_schema), response_status, content_type, **_slot_metadata(child_schema)))
        return slots
    if prefix:
        name = prefix.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
        return [AssetSlot(name, location, prefix, _schema_type(schema), required, _is_sensitive(name, schema), response_status, content_type, **_slot_metadata(schema))]
    return []


def _slot_score(output: AssetSlot, target: AssetSlot) -> float:
    if output.sensitive != target.sensitive and (output.sensitive or target.sensitive):
        return 0.0
    output_name = _normalized_name(output.name)
    target_name = _normalized_name(target.name)
    if output_name != target_name:
        return 0.0
    score = 0.8
    if output.value_type == target.value_type or "any" in {output.value_type, target.value_type}:
        score += 0.15
    if output.location == "json_body" and target.location in {"json_body", "form", "multipart"}:
        score += 0.05
    return round(min(score, 1.0), 2)


def _parameter_location(value: str) -> str:
    return {"path": "path", "query": "query", "header": "header", "cookie": "cookie"}.get(value.lower(), "")


def _body_location(content_type: str) -> str:
    value = content_type.lower()
    if "multipart/form-data" in value:
        return "multipart"
    if "application/x-www-form-urlencoded" in value:
        return "form"
    if "json" in value or not value:
        return "json_body"
    return "raw_body"


def _schema_type(schema: dict[str, Any]) -> str:
    value = str(schema.get("type") or "").lower()
    return {"string": "string", "integer": "integer", "number": "number", "boolean": "boolean", "object": "object", "array": "array", "file": "file"}.get(value, "any")


def _slot_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    examples = schema.get("examples") if isinstance(schema.get("examples"), list) else []
    if "example" in schema:
        examples = [schema["example"], *examples]
    nested_schema = schema.get("x-json-schema")
    return {
        "default_value": schema.get("default"),
        "has_default": "default" in schema,
        "enum": tuple(schema.get("enum")) if isinstance(schema.get("enum"), list) else (),
        "examples": tuple(examples[:5]),
        "nested_schema": nested_schema if isinstance(nested_schema, dict) else None,
    }


def _python_value_type(value: Any) -> str:
    if isinstance(value, bool): return "boolean"
    if isinstance(value, int): return "integer"
    if isinstance(value, float): return "number"
    if isinstance(value, list): return "array"
    if isinstance(value, dict): return "object"
    return "string"


def _is_sensitive(name: str, schema: dict[str, Any]) -> bool:
    return bool(schema.get("x-sensitive") or schema.get("writeOnly") or _SENSITIVE_KEY_RE.search(name))


def _secret_keys(auth_type: str, config: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    if auth_type == "static_bearer" and config.get("token_encrypted"):
        keys.add("authorization")
    if auth_type == "cookie" and config.get("cookie_value_encrypted"):
        keys.add(str(config.get("cookie_name") or "cookie"))
    if auth_type == "cybertron_agent":
        for key in ("cybertron_robot_key", "cybertron_robot_token"):
            if config.get(f"{key}_encrypted"):
                keys.add(key)
    for key in (config.get("headers_encrypted") or {}):
        keys.add(str(key))
    return keys


def _loads_row_json(row: Any, field: str) -> dict[str, Any]:
    try:
        value = row[field]
    except (KeyError, IndexError):
        return {}
    if isinstance(value, dict): return value
    try: return json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError): return {}


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _dedupe_slots(slots: list[AssetSlot]) -> list[AssetSlot]:
    seen: set[tuple[str, str, str]] = set()
    result: list[AssetSlot] = []
    for slot in slots:
        key = (slot.location, slot.path, slot.response_status)
        if key not in seen:
            seen.add(key)
            result.append(slot)
    return result
