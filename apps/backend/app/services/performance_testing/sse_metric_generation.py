from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote

import requests

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import api_automation_repo
from app.schemas.performance_test import PerformanceSseMetricGenerateIn
from app.schemas.performance_test import PerformanceSseConfig
from app.services.performance_testing.sse import SseEvent, event_matches, parse_sse_events


REQUIRED_METRIC_IDS = ("call_llm_start", "first_answer")
_PATH_PARAMETER = re.compile(r"\{([^{}]+)\}")


@dataclass(frozen=True)
class CapturedSseEvent:
    sequence: int
    received_offset_ms: int
    event: SseEvent


def capture_sse_events(
    response: Any,
    *,
    started_at: float,
    clock: Callable[[], float],
    max_events: int = 200,
    max_frame_bytes: int = 262_144,
) -> tuple[list[CapturedSseEvent], bool]:
    captured: list[CapturedSseEvent] = []
    frame_lines: list[str] = []
    for line in response.iter_lines(decode_unicode=True):
        normalized = line if isinstance(line, str) else line.decode("utf-8", errors="replace")
        frame_lines.append(normalized)
        if normalized.rstrip("\r\n"):
            continue
        parsed = parse_sse_events(frame_lines, max_frame_bytes=max_frame_bytes)
        frame_lines = []
        for event in parsed:
            captured.append(
                CapturedSseEvent(
                    sequence=len(captured) + 1,
                    received_offset_ms=round((clock() - started_at) * 1000),
                    event=event,
                )
            )
            if len(captured) >= max_events:
                return captured, True
    if frame_lines:
        for event in parse_sse_events(frame_lines, max_frame_bytes=max_frame_bytes):
            captured.append(
                CapturedSseEvent(
                    sequence=len(captured) + 1,
                    received_offset_ms=round((clock() - started_at) * 1000),
                    event=event,
                )
            )
    return captured, False


def execute_sse_probe(
    request: dict[str, Any],
    *,
    max_stream_seconds: float,
    requester: Callable[..., Any],
    clock: Callable[[], float],
) -> dict[str, Any]:
    started_at = clock()
    response = requester(
        method=request["method"],
        url=request["url"],
        params=request.get("query_parameters") or {},
        headers=request.get("headers") or {},
        json=request.get("body"),
        timeout=(request.get("timeout_seconds", 30), max_stream_seconds),
        verify=request.get("verify_ssl", True),
        allow_redirects=False,
        stream=True,
    )
    try:
        content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if not 200 <= int(response.status_code) < 300:
            raise ValueError(f"SSE 探测请求返回状态码 {response.status_code}")
        if content_type != "text/event-stream":
            raise ValueError("响应 Content-Type 不是 text/event-stream")
        events, truncated = capture_sse_events(response, started_at=started_at, clock=clock)
        if not events:
            raise ValueError("SSE 探测没有捕获到有效事件")
        return {
            "status_code": int(response.status_code),
            "headers": dict(response.headers),
            "events": events,
            "truncated": truncated,
        }
    finally:
        response.close()


def generate_project_sse_metrics(
    project_id: str,
    payload: PerformanceSseMetricGenerateIn,
    actor: dict[str, Any],
) -> dict[str, Any]:
    from app.agents.performance_testing.sse_metric_generation import suggest_sse_metrics
    from app.services.performance_testing import service as performance_service

    with connect() as db:
        performance_service._require_visible_project(db, project_id, actor)
        endpoint, environment = performance_service._validate_references(
            db,
            project_id,
            endpoint_id=payload.endpoint_id,
            api_environment_id=payload.api_environment_id,
        )
        headers = {
            **performance_service._environment_runtime_headers(environment),
            **{str(key): str(value) for key, value in payload.headers.items()},
        }
        request = {
            "method": str(endpoint["method"]).upper(),
            "url": _endpoint_url(str(environment["api_base_url"]), str(endpoint["path"]), payload.path_parameters),
            "query_parameters": payload.query_parameters,
            "headers": headers,
            "body": payload.body,
            "timeout_seconds": int(environment["timeout_seconds"]),
            "verify_ssl": bool(environment["verify_ssl"]),
        }

    try:
        probe = execute_sse_probe(
            request,
            max_stream_seconds=payload.max_stream_seconds,
            requester=requests.request,
            clock=time.perf_counter,
        )
    except (requests.RequestException, ValueError) as exc:
        raise api_error(400, "PERFORMANCE_SSE_PROBE_FAILED", str(exc)) from exc

    if payload.candidate_sse is not None:
        candidate_sse = payload.candidate_sse.model_dump(mode="json")
        generated = {
            "candidate_sse": candidate_sse,
            "validation": validate_sse_candidate(probe["events"], candidate_sse),
            "generation_source": "user_validation",
            "warnings": [],
        }
    else:
        generated = generate_sse_metric_candidate(
            probe["events"],
            max_stream_seconds=payload.max_stream_seconds,
            ai_suggester=suggest_sse_metrics,
        )
    return {
        "sample": {
            "status_code": probe["status_code"],
            "event_count": len(probe["events"]),
            "truncated": probe["truncated"],
        },
        **generated,
    }


def build_deterministic_sse_config(
    events: list[CapturedSseEvent],
    *,
    max_stream_seconds: float,
) -> dict[str, Any]:
    event_path = _find_event_type_path(events) or "$.data.event_type"
    event_name = _common_event_name(events)
    return {
        "max_stream_seconds": max_stream_seconds,
        "metrics": [
            {
                "id": "call_llm_start",
                "name": "LLM 调用开始时间",
                "match": _equals_match(event_name, event_path, "call_llm_start"),
                "occurrence": "first",
                "missing_policy": "record_null",
            },
            {
                "id": "first_answer",
                "name": "首次回答时间",
                "match": _equals_match(event_name, event_path, "answer"),
                "occurrence": "first",
                "missing_policy": "fail_request",
            },
        ],
        "end_rule": _equals_match(event_name, event_path, "query_end") if _has_event_type(events, "query_end") else None,
    }


def validate_sse_candidate(events: list[CapturedSseEvent], config: dict[str, Any]) -> dict[str, Any]:
    validated = PerformanceSseConfig.model_validate(config)
    metrics = []
    matched_ids: set[str] = set()
    for metric in validated.metrics:
        matched = [item for item in events if event_matches(item.event, metric.match.model_dump(mode="json"))]
        first = matched[0] if matched else None
        if first is not None:
            matched_ids.add(metric.id)
        metrics.append(
            {
                "metric_id": metric.id,
                "matched_count": len(matched),
                "first_event_sequence": first.sequence if first else None,
                "sample_elapsed_ms": first.received_offset_ms if first else None,
                "sample_event": _sample_event(first.event) if first else None,
            }
        )

    end_matches: list[CapturedSseEvent] = []
    if validated.end_rule is not None:
        end_match = validated.end_rule.model_dump(mode="json")
        end_matches = [item for item in events if event_matches(item.event, end_match)]
    end_rule = {
        "matched_count": len(end_matches),
        "first_event_sequence": end_matches[0].sequence if end_matches else None,
    }
    valid = set(REQUIRED_METRIC_IDS).issubset(matched_ids)
    if validated.end_rule is not None:
        valid = valid and bool(end_matches)
    return {"valid": valid, "metrics": metrics, "end_rule": end_rule}


def generate_sse_metric_candidate(
    events: list[CapturedSseEvent],
    *,
    max_stream_seconds: float,
    ai_suggester: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    deterministic = build_deterministic_sse_config(events, max_stream_seconds=max_stream_seconds)
    warnings: list[str] = []
    if ai_suggester is not None:
        try:
            suggested = dict(ai_suggester(_ai_input(events)) or {})
            suggested["max_stream_seconds"] = max_stream_seconds
            validation = validate_sse_candidate(events, suggested)
            suggested_ids = {metric.get("id") for metric in suggested.get("metrics") or []}
            if validation["valid"] and set(REQUIRED_METRIC_IDS).issubset(suggested_ids):
                return {
                    "candidate_sse": PerformanceSseConfig.model_validate(suggested).model_dump(mode="json"),
                    "validation": validation,
                    "generation_source": "ai",
                    "warnings": warnings,
                }
        except Exception:
            pass
        warnings.append("AI 生成的指标规则未通过样本回放，已使用确定性识别结果。")

    return {
        "candidate_sse": PerformanceSseConfig.model_validate(deterministic).model_dump(mode="json"),
        "validation": validate_sse_candidate(events, deterministic),
        "generation_source": "deterministic_fallback" if ai_suggester is not None else "deterministic",
        "warnings": warnings,
    }


def _equals_match(event_name: str, path: str, expected: str) -> dict[str, Any]:
    return {
        "event_name": event_name,
        "source": "data_json",
        "path": path,
        "operator": "equals",
        "expected": expected,
    }


def _ai_input(events: list[CapturedSseEvent]) -> dict[str, Any]:
    return {
        "requested_metrics": ["首次 call_llm_start", "首次 answer"],
        "events": [
            {
                "sequence": item.sequence,
                "event_name": item.event.event_name,
                "received_offset_ms": item.received_offset_ms,
                "data_json": _sanitize_ai_value(item.event.data_json),
            }
            for item in events
        ],
    }


def _sanitize_ai_value(value: Any) -> Any:
    allowed = {"event_type", "role", "answer", "finish", "content_type", "type"}
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, nested in value.items():
            if key in allowed:
                sanitized[key] = "<non-empty>" if key == "answer" and nested not in (None, "") else nested
                continue
            child = _sanitize_ai_value(nested)
            if child not in (None, {}, []):
                sanitized[key] = child
        return sanitized
    if isinstance(value, list):
        return [child for item in value if (child := _sanitize_ai_value(item)) not in (None, {}, [])]
    return None


def _find_event_type_path(events: list[CapturedSseEvent]) -> str | None:
    for item in events:
        path = _find_key_path(item.event.data_json, "event_type")
        if path:
            return path
    return None


def _find_key_path(value: Any, target: str, path: str = "$") -> str | None:
    if isinstance(value, dict):
        if target in value:
            return f"{path}.{target}"
        for key, nested in value.items():
            found = _find_key_path(nested, target, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_key_path(nested, target, f"{path}[*]")
            if found:
                return found
    return None


def _has_event_type(events: list[CapturedSseEvent], expected: str) -> bool:
    for item in events:
        payload = item.event.data_json
        if _contains_key_value(payload, "event_type", expected):
            return True
    return False


def _contains_key_value(value: Any, key: str, expected: Any) -> bool:
    if isinstance(value, dict):
        return value.get(key) == expected or any(_contains_key_value(nested, key, expected) for nested in value.values())
    if isinstance(value, list):
        return any(_contains_key_value(nested, key, expected) for nested in value)
    return False


def _common_event_name(events: list[CapturedSseEvent]) -> str:
    names = [item.event.event_name for item in events if item.event.event_name]
    return max(set(names), key=names.count) if names else ""


def _sample_event(event: SseEvent) -> dict[str, Any]:
    payload = event.data_json
    data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else {}
    sample = {"event": event.event_name, "event_type": data.get("event_type"), "role": data.get("role")}
    if data.get("answer") not in (None, ""):
        sample["answer"] = str(data["answer"])[:120]
    return {key: value for key, value in sample.items() if value not in (None, "")}


def _endpoint_url(base_url: str, path: str, path_parameters: dict[str, Any]) -> str:
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in path_parameters:
            missing.append(name)
            return match.group(0)
        return quote(str(path_parameters[name]), safe="")

    resolved_path = _PATH_PARAMETER.sub(replace, path)
    if missing:
        raise api_error(400, "PERFORMANCE_PATH_PARAMETER_REQUIRED", f"缺少 Path 参数：{', '.join(missing)}。")
    return f"{base_url.rstrip('/')}/{resolved_path.lstrip('/')}"


__all__ = [
    "CapturedSseEvent",
    "build_deterministic_sse_config",
    "capture_sse_events",
    "execute_sse_probe",
    "generate_project_sse_metrics",
    "generate_sse_metric_candidate",
    "validate_sse_candidate",
]
