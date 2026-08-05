import hashlib
import json
import re
import subprocess
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


_PATH_PARAMETER = re.compile(r"\{([^{}]+)\}")
_CONTENT_KEYS = {"answer", "content", "text", "delta", "message", "output", "result"}
_FACT_KEYS = {"event_type", "status", "state", "phase", "stage", "action", "type", "finish", "role", "index"}
_CANDIDATE_FACT_KEYS = {"event_type", "status", "state", "phase", "stage", "action"} | _CONTENT_KEYS
_NOISE_VALUES = {"heartbeat", "ping", "pong", "keepalive", "keep_alive", "ack", "debug", "log"}
_START_MARKER = re.compile(r"(^|[_-])(start|begin|started)$", re.IGNORECASE)
_END_MARKER = re.compile(r"(^|[_-])(end|complete|completed|finish|finished|done)$", re.IGNORECASE)


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
    max_stream_bytes: int = 4_194_304,
    max_stream_seconds: float | None = None,
) -> tuple[list[CapturedSseEvent], bool]:
    captured: list[CapturedSseEvent] = []
    frame_lines: list[str] = []
    stream_size = 0
    for line in response.iter_lines(decode_unicode=True):
        normalized = line if isinstance(line, str) else line.decode("utf-8", errors="replace")
        stream_size += len(normalized.encode("utf-8"))
        if stream_size > max_stream_bytes:
            raise ValueError("sse_stream_too_large")
        frame_lines.append(normalized)
        if normalized.rstrip("\r\n"):
            continue
        parsed = parse_sse_events(frame_lines, max_frame_bytes=max_frame_bytes)
        frame_lines = []
        for event in parsed:
            received_at = clock()
            if max_stream_seconds is not None and received_at - started_at > max_stream_seconds:
                raise ValueError("sse_stream_timeout")
            captured.append(
                CapturedSseEvent(
                    sequence=len(captured) + 1,
                    received_offset_ms=round((received_at - started_at) * 1000),
                    event=event,
                )
            )
            if len(captured) >= max_events:
                return captured, True
    if frame_lines:
        for event in parse_sse_events(frame_lines, max_frame_bytes=max_frame_bytes):
            received_at = clock()
            if max_stream_seconds is not None and received_at - started_at > max_stream_seconds:
                raise ValueError("sse_stream_timeout")
            captured.append(
                CapturedSseEvent(
                    sequence=len(captured) + 1,
                    received_offset_ms=round((received_at - started_at) * 1000),
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
        **_request_payload_kwargs(request),
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
        events, truncated = capture_sse_events(
            response,
            started_at=started_at,
            clock=clock,
            max_stream_seconds=max_stream_seconds,
        )
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
        if payload.endpoint_id:
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
            source_request_id = str(payload.endpoint_id)
            source_request_name = f"{request['method']} {endpoint['path']}"
            scenario_probe = None
        else:
            _, scenario, environment = performance_service._validate_target_references(
                db,
                project_id,
                target_type="scenario",
                endpoint_id=None,
                scenario_id=payload.scenario_id,
                api_environment_id=payload.api_environment_id,
            )
            snapshot = api_automation_repo.loads_json(scenario["published_snapshot_json"], {})
            if not snapshot or not snapshot.get("steps"):
                raise api_error(400, "PERFORMANCE_SCENARIO_VERSION_MISSING", "接口场景没有当前保存版本，请先保存场景。")
            request = None
            source_request_id, source_request_name = _scenario_source_request(snapshot, str(payload.scenario_step_id))
            scenario_probe = {
                "scenario_id": str(payload.scenario_id),
                "target_step_id": str(payload.scenario_step_id),
                "api_environment_id": str(payload.api_environment_id),
            }

    try:
        if scenario_probe is None:
            probe = execute_sse_probe(
                request,
                max_stream_seconds=payload.max_stream_seconds,
                requester=requests.request,
                clock=time.perf_counter,
            )
        else:
            from app.services.api_automation import service as api_automation_service

            execution = api_automation_service.execute_api_scenario_probe(
                project_id,
                scenario_probe["scenario_id"],
                scenario_probe["api_environment_id"],
                target_step_id=str(scenario_probe["target_step_id"]),
                max_stream_seconds=payload.max_stream_seconds,
            )
            probe = _scenario_execution_probe(execution, scenario_probe["target_step_id"])
    except (requests.RequestException, subprocess.SubprocessError, OSError, RuntimeError, ValueError) as exc:
        raise api_error(400, "PERFORMANCE_SSE_PROBE_FAILED", str(exc)) from exc

    if payload.candidate_sse is not None:
        candidate_sse = payload.candidate_sse.model_dump(mode="json")
        validation = validate_sse_candidate(probe["events"], candidate_sse)
        generated = {
            "sample_summary": {
                "event_count": len(probe["events"]),
                "duration_ms": max((event.received_offset_ms for event in probe["events"]), default=0),
                "truncated": probe["truncated"],
            },
            "event_facts": extract_sse_event_facts(probe["events"]),
            "candidates": [],
            "end_rule_candidate": None,
            "candidate_sse": candidate_sse,
            "validation": validation,
            "analysis": {"ai_status": "disabled", "generation_mode": "user_validation", "summary": "已重新验证当前配置"},
            "result_status": "ready" if validation["valid"] else "partial",
            "messages": [] if validation["valid"] else ["部分指标未通过当前样本验证，请检查匹配规则。"],
        }
    else:
        generated = generate_sse_metric_candidate(
            probe["events"],
            max_stream_seconds=payload.max_stream_seconds,
            ai_suggester=suggest_sse_metrics,
            source_request_id=source_request_id,
            source_request_name=source_request_name,
        )
        generated["sample_summary"]["truncated"] = probe["truncated"]
    return {
        "sample": {
            "status_code": probe["status_code"],
            "event_count": len(probe["events"]),
            "truncated": probe["truncated"],
        },
        **generated,
    }


def _scenario_execution_probe(execution: dict[str, Any], target_step_id: str) -> dict[str, Any]:
    scenario_result = execution.get("scenario_result") or {}
    steps = [step for step in scenario_result.get("steps") or [] if isinstance(step, dict)]
    target_step = next((step for step in steps if str(step.get("step_id")) == target_step_id), None)
    if execution.get("status") != "passed" or scenario_result.get("status") != "passed":
        failed_step = next((step for step in steps if step.get("status") == "failed"), target_step)
        if failed_step:
            response_body = ((failed_step.get("response") or {}).get("body"))
            business_message = response_body.get("message") if isinstance(response_body, dict) else ""
            detail = business_message or failed_step.get("error") or execution.get("error_message")
            raise ValueError(f"场景步骤 {failed_step.get('name') or failed_step.get('step_id')} 执行失败：{detail}")
        raise ValueError(execution.get("error_message") or "接口场景探测执行失败")
    if target_step is None:
        raise ValueError("场景 SSE 目标步骤不存在或未执行")
    response = target_step.get("response") or {}
    body = response.get("body") or {}
    if not isinstance(body, dict) or not body.get("streaming"):
        raise ValueError("场景目标步骤响应不是 SSE 事件流")
    captured = []
    for index, item in enumerate(body.get("events") or [], start=1):
        if not isinstance(item, dict):
            continue
        data = item.get("data")
        data_text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        captured.append(
            CapturedSseEvent(
                sequence=index,
                received_offset_ms=max(0, int(item.get("received_offset_ms") or 0)),
                event=SseEvent(event_name=str(item.get("event") or "message"), data_text=data_text),
            )
        )
    if not captured:
        raise ValueError("SSE 探测没有捕获到有效事件")
    return {
        "status_code": int(response.get("status_code") or 0),
        "headers": dict(response.get("headers") or {}),
        "events": captured,
        "truncated": bool(body.get("truncated")),
    }


def _request_payload_kwargs(request: dict[str, Any]) -> dict[str, Any]:
    headers = dict(request.get("headers") or {})
    cookies = dict(request.get("cookies") or {})
    multipart = request.get("multipart_form")
    form = request.get("form")
    kwargs: dict[str, Any] = {"headers": headers, "cookies": cookies or None}
    if multipart is not None:
        for key in list(headers):
            if key.lower() == "content-type":
                headers.pop(key)
        kwargs["files"] = [
            (str(field), (None, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)))
            for field, value in dict(multipart).items()
        ]
    elif form is not None:
        kwargs["data"] = form
    else:
        kwargs["json"] = request.get("body")
    return kwargs


def extract_sse_event_facts(events: list[CapturedSseEvent]) -> list[dict[str, Any]]:
    aggregates: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in events:
        payload = item.event.data_json
        has_non_empty_content = _has_non_empty_content(payload) and not _contains_key_value(payload, "role", "user")
        for path, value in _iter_fact_values(payload):
            normalized_value = _normalize_fact_value(value)
            if normalized_value is None:
                continue
            key = (item.event.event_name, path, normalized_value)
            fact = aggregates.get(key)
            if fact is None:
                signature = json.dumps(key, ensure_ascii=False, separators=(",", ":"))
                fact = {
                    "fact_id": f"fact_{hashlib.sha256(signature.encode('utf-8')).hexdigest()[:8]}",
                    "event_name": item.event.event_name,
                    "source": "data_json",
                    "path": path,
                    "value_type": type(value).__name__,
                    "normalized_value": normalized_value,
                    "matched_count": 0,
                    "first_sequence": item.sequence,
                    "last_sequence": item.sequence,
                    "first_offset_ms": item.received_offset_ms,
                    "last_offset_ms": item.received_offset_ms,
                    "has_non_empty_content": False,
                }
                fact["metric_id"] = _stable_metric_id("custom", _fact_match(fact))
                aggregates[key] = fact
            fact["matched_count"] += 1
            fact["last_sequence"] = item.sequence
            fact["last_offset_ms"] = item.received_offset_ms
            fact["has_non_empty_content"] = fact["has_non_empty_content"] or has_non_empty_content
    return sorted(aggregates.values(), key=lambda fact: (fact["first_sequence"], fact["path"], fact["normalized_value"]))


def build_structural_sse_candidates(
    events: list[CapturedSseEvent],
    facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    event_count = len(events)
    first_output_index_fact = next(
        (
            fact
            for fact in facts
            if str(fact["path"]).endswith(".index") and fact["normalized_value"] == "0"
        ),
        None,
    )
    content_facts = [
        fact
        for fact in facts
        if str(fact["path"]).rsplit(".", 1)[-1] in _CANDIDATE_FACT_KEYS
        and fact["has_non_empty_content"]
        and str(fact["normalized_value"]).lower() not in _NOISE_VALUES
        and not _START_MARKER.search(str(fact["normalized_value"]))
        and not _END_MARKER.search(str(fact["normalized_value"]))
    ]
    first_output_fact_id = first_output_index_fact["fact_id"] if first_output_index_fact else None
    if first_output_fact_id is None and content_facts:
        first_output_fact_id = min(
            content_facts,
            key=lambda fact: (
                0 if str(fact["path"]).endswith(".answer") else 1,
                fact["first_sequence"],
                fact["path"],
            ),
        )["fact_id"]
    for fact in facts:
        if (
            str(fact["path"]).rsplit(".", 1)[-1] not in _CANDIDATE_FACT_KEYS
            and fact["fact_id"] != first_output_fact_id
        ):
            continue
        value = str(fact["normalized_value"])
        lowered = value.lower()
        if lowered in _NOISE_VALUES:
            continue
        category: str | None = None
        score = 0.0
        confidence = 0.45
        reason = ""
        name = f"{value} 事件时间"
        uncertainty: str | None = "事件的准确业务含义需要人工确认。"
        is_terminal = fact["matched_count"] == 1 and fact["last_sequence"] == event_count
        if _START_MARKER.search(lowered):
            category = "milestone_start"
            score = 0.64
            name = _structural_metric_name(value, category)
            reason = f"事件 `{value}` 的名称具有阶段开始特征。"
        elif _END_MARKER.search(lowered):
            category = "completion" if is_terminal else "milestone_end"
            score = 0.82 if is_terminal else 0.68
            confidence = 0.65 if is_terminal else confidence
            name = _structural_metric_name(value, category)
            reason = (
                f"事件 `{value}` 仅出现一次且位于样本末尾，可能代表流式处理完成。"
                if is_terminal
                else f"事件 `{value}` 的名称具有阶段完成特征。"
            )
        elif fact["fact_id"] == first_output_fact_id:
            category = "first_output"
            score = 0.9
            confidence = 0.75
            name = _structural_metric_name(value, category)
            reason = "该事件首次出现时携带非空内容，适合作为用户可感知输出候选。"
            uncertainty = None
        elif str(fact["path"]).rsplit(".", 1)[-1] in _CONTENT_KEYS:
            continue
        elif is_terminal:
            category = "completion"
            score = 0.82
            confidence = 0.65
            name = _structural_metric_name(value, category)
            reason = "该事件仅出现一次且位于样本末尾，可能代表流式处理完成。"
        if category is None:
            continue
        if category == "first_output" and str(fact["path"]).endswith(".index"):
            match = {
                "event_name": str(fact["event_name"]),
                "source": "data_json",
                "path": str(fact["path"]),
                "operator": "equals",
                "expected": 0,
            }
        elif category == "first_output":
            match = {
                "event_name": str(fact["event_name"]),
                "source": "data_json",
                "path": str(fact["path"]),
                "operator": "non_empty",
            }
        else:
            match = _equals_match(str(fact["event_name"]), str(fact["path"]), fact["normalized_value"])
        validation = _validate_match(events, match)
        candidates.append(
            {
                "suggestion_key": f"suggestion_{fact['fact_id']}",
                "metric_id": _stable_metric_id(category, match),
                "name": name,
                "category": category,
                "match": match,
                "occurrence": "first",
                "recommended_missing_policy": "record_null",
                "source": "structural",
                "recommendation_level": "recommended" if score >= 0.75 else "optional",
                "recommendation_score": score,
                "semantic_confidence": confidence,
                "reason": reason,
                "uncertainty": uncertainty,
                "evidence_fact_ids": [fact["fact_id"]],
                "validation": validation,
            }
        )
    candidates.sort(key=_candidate_order_key)
    return candidates[:8]


def _structural_metric_name(value: str, category: str) -> str:
    if category == "first_output":
        return "首次有效内容时间"
    if category == "milestone_start":
        stem = _START_MARKER.sub("", value).strip("_-") or value
        return f"{stem} 开始时间"
    if category in {"milestone_end", "completion"}:
        stem = _END_MARKER.sub("", value).strip("_-") or value
        return f"{stem} 完成时间"
    return f"{value} 事件时间"


def validate_sse_candidate(events: list[CapturedSseEvent], config: dict[str, Any]) -> dict[str, Any]:
    validated = PerformanceSseConfig.model_validate(config)
    metrics = []
    for metric in validated.metrics:
        matched = [item for item in events if event_matches(item.event, metric.match.model_dump(mode="json"))]
        first = matched[0] if matched else None
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
    valid = bool(metrics) and all(metric["matched_count"] > 0 for metric in metrics)
    if validated.end_rule is not None:
        valid = valid and bool(end_matches)
    return {"valid": valid, "metrics": metrics, "end_rule": end_rule}


def generate_sse_metric_candidate(
    events: list[CapturedSseEvent],
    *,
    max_stream_seconds: float,
    ai_suggester: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    source_request_id: str | None = None,
    source_request_name: str | None = None,
) -> dict[str, Any]:
    facts = extract_sse_event_facts(events)
    structural = build_structural_sse_candidates(events, facts)
    candidates = structural
    ai_status = "disabled" if ai_suggester is None else "not_used"
    generation_mode = "structural_only" if structural else "event_catalog_only"
    end_rule_candidate = _structural_end_rule_candidate(events, facts)
    if ai_suggester is not None:
        try:
            suggested = dict(ai_suggester(_ai_input(events, facts)) or {})
            ai_candidates = _ai_candidates(events, facts, suggested.get("candidates") or [])
            candidates = _merge_candidates(structural, ai_candidates)
            if suggested.get("end_rule_candidate_fact_id"):
                suggested_end_rule = _end_rule_from_fact(
                    events,
                    facts,
                    str(suggested["end_rule_candidate_fact_id"]),
                )
                if suggested_end_rule is not None:
                    end_rule_candidate = suggested_end_rule
            ai_status = "used" if not (suggested.get("candidates") or []) or ai_candidates else "not_used"
            if ai_candidates:
                generation_mode = "ai_and_structural" if structural else "ai_only"
        except Exception:
            ai_status = "unavailable"
    result_status = "ready" if candidates else "empty"
    messages = [] if candidates else ["本次样本未发现高可信度性能指标，可从事件目录中手动选择。"]
    timing = {
        "scope": "request",
        "start": "request_started",
        "source_request_id": source_request_id,
        "source_request_name": source_request_name,
    }
    candidates = [{**candidate, "timing": timing} for candidate in candidates]
    return {
        "sample_summary": {
            "event_count": len(events),
            "duration_ms": max((event.received_offset_ms for event in events), default=0),
            "truncated": False,
        },
        "event_facts": facts,
        "candidates": candidates,
        "end_rule_candidate": end_rule_candidate,
        "analysis": {
            "ai_status": ai_status,
            "generation_mode": generation_mode,
            "summary": f"发现 {len(candidates)} 个候选指标",
        },
        "result_status": result_status,
        "messages": messages,
    }


def _scenario_source_request(snapshot: dict[str, Any], target_step_id: str) -> tuple[str, str]:
    for index, step in enumerate(snapshot.get("steps") or [], start=1):
        if not isinstance(step, dict) or str(step.get("id") or "") != target_step_id:
            continue
        endpoint = step.get("endpoint") if isinstance(step.get("endpoint"), dict) else {}
        overrides = step.get("request_overrides") if isinstance(step.get("request_overrides"), dict) else {}
        request = overrides.get("request") if isinstance(overrides.get("request"), dict) else overrides
        method = str(request.get("method") or endpoint.get("method") or "POST").upper()
        path = str(request.get("path") or endpoint.get("path") or "")
        return target_step_id, f"{index:02d} {method} {path}".strip()
    return target_step_id, target_step_id


def _equals_match(event_name: str, path: str, expected: str) -> dict[str, Any]:
    return {
        "event_name": event_name,
        "source": "data_json",
        "path": path,
        "operator": "equals",
        "expected": expected,
    }


def _ai_input(events: list[CapturedSseEvent], facts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "task": "discover_performance_metric_candidates",
        "sample": {
            "event_count": len(events),
            "duration_ms": max((event.received_offset_ms for event in events), default=0),
        },
        "facts": facts,
    }


def _iter_fact_values(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_path = f"{path}.{key}"
            if key in _FACT_KEYS and isinstance(nested, (str, int, float, bool)):
                yield nested_path, nested
            elif key in _CONTENT_KEYS and nested not in (None, "", [], {}, False):
                yield nested_path, "<non-empty>"
            if isinstance(nested, (dict, list)):
                yield from _iter_fact_values(nested, nested_path)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_fact_values(nested, f"{path}[*]")


def _normalize_fact_value(value: Any) -> str | None:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 120:
        return None
    if re.fullmatch(r"[0-9a-fA-F-]{20,}", normalized):
        return None
    return normalized


def _has_non_empty_content(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in _CONTENT_KEYS and nested not in (None, "", [], {}):
                return True
            if _has_non_empty_content(nested):
                return True
    elif isinstance(value, list):
        return any(_has_non_empty_content(item) for item in value)
    return False


def _validate_match(events: list[CapturedSseEvent], match: dict[str, Any]) -> dict[str, Any]:
    matched = [item for item in events if event_matches(item.event, match)]
    first = matched[0] if matched else None
    return {
        "valid": first is not None,
        "matched_count": len(matched),
        "first_event_sequence": first.sequence if first else None,
        "sample_elapsed_ms": first.received_offset_ms if first else None,
        "sample_event": _sample_event(first.event) if first else None,
    }


def _stable_metric_id(category: str, match: dict[str, Any]) -> str:
    signature = json.dumps(match, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_") or "event"
    return f"sse_{slug}_{digest}"[:64]


def _fact_match(fact: dict[str, Any]) -> dict[str, Any]:
    if str(fact["path"]).rsplit(".", 1)[-1] in _CONTENT_KEYS:
        return {
            "event_name": str(fact["event_name"]),
            "source": "data_json",
            "path": str(fact["path"]),
            "operator": "non_empty",
        }
    return _equals_match(str(fact["event_name"]), str(fact["path"]), fact["normalized_value"])


def _ai_candidates(
    events: list[CapturedSseEvent],
    facts: list[dict[str, Any]],
    suggestions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    facts_by_id = {fact["fact_id"]: fact for fact in facts}
    candidates: list[dict[str, Any]] = []
    allowed_categories = {
        "first_output",
        "milestone_start",
        "milestone_end",
        "completion",
        "first_external_action",
        "state_transition",
        "custom_event",
    }
    for suggestion in suggestions[:8]:
        fact = facts_by_id.get(str(suggestion.get("fact_id") or ""))
        if fact is None or str(fact["path"]).rsplit(".", 1)[-1] not in _CANDIDATE_FACT_KEYS:
            continue
        category = str(suggestion.get("category") or "custom_event")
        if category not in allowed_categories:
            category = "custom_event"
        confidence = min(1.0, max(0.0, float(suggestion.get("confidence") or 0.5)))
        match = _fact_match(fact)
        score = min(1.0, 0.55 + confidence * 0.35)
        candidates.append(
            {
                "suggestion_key": f"suggestion_ai_{fact['fact_id']}",
                "metric_id": _stable_metric_id(category, match),
                "name": str(suggestion.get("name") or f"事件 {fact['normalized_value']} 首次到达时间")[:80],
                "category": category,
                "match": match,
                "occurrence": "first",
                "recommended_missing_policy": "record_null",
                "source": "ai",
                "recommendation_level": "recommended" if score >= 0.75 else "optional",
                "recommendation_score": score,
                "semantic_confidence": confidence,
                "reason": str(suggestion.get("reason") or "AI 根据当前样本将该事件识别为性能观测候选。")[:500],
                "uncertainty": str(suggestion["uncertainty"])[:500] if suggestion.get("uncertainty") else None,
                "evidence_fact_ids": [fact["fact_id"]],
                "validation": _validate_match(events, match),
            }
        )
    return candidates


def _candidate_signature(candidate: dict[str, Any]) -> str:
    return json.dumps(candidate["match"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _candidate_order_key(candidate: dict[str, Any]) -> tuple[int, int, int, float, str]:
    validation = candidate.get("validation") or {}
    first_sequence = validation.get("first_event_sequence")
    sample_elapsed_ms = validation.get("sample_elapsed_ms")
    return (
        1 if first_sequence is None else 0,
        int(first_sequence) if first_sequence is not None else 0,
        int(sample_elapsed_ms) if sample_elapsed_ms is not None else 0,
        -float(candidate.get("recommendation_score") or 0),
        str(candidate.get("name") or ""),
    )


def _merge_candidates(
    structural: list[dict[str, Any]],
    ai_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = {_candidate_signature(candidate): dict(candidate) for candidate in structural}
    for candidate in ai_candidates:
        signature = _candidate_signature(candidate)
        existing = merged.get(signature)
        if existing is None:
            merged[signature] = candidate
            continue
        existing.update(
            {
                "name": candidate["name"],
                "category": candidate["category"],
                "metric_id": candidate["metric_id"],
                "source": "merged",
                "recommendation_score": max(existing["recommendation_score"], candidate["recommendation_score"]),
                "semantic_confidence": candidate["semantic_confidence"],
                "reason": candidate["reason"],
                "uncertainty": candidate["uncertainty"],
                "evidence_fact_ids": sorted(set(existing["evidence_fact_ids"] + candidate["evidence_fact_ids"])),
            }
        )
        existing["recommendation_level"] = (
            "recommended" if existing["recommendation_score"] >= 0.75 else "optional"
        )
    return sorted(merged.values(), key=_candidate_order_key)[:8]


def _end_rule_from_fact(
    events: list[CapturedSseEvent],
    facts: list[dict[str, Any]],
    fact_id: str,
) -> dict[str, Any] | None:
    fact = next((item for item in facts if item["fact_id"] == fact_id), None)
    if fact is None or str(fact["path"]).rsplit(".", 1)[-1] not in _CANDIDATE_FACT_KEYS:
        return None
    match = _fact_match(fact)
    return {
        "fact_id": fact_id,
        "match": match,
        "reason": "该事件被识别为流结束候选。",
        "validation": _validate_match(events, match),
    }


def _structural_end_rule_candidate(
    events: list[CapturedSseEvent],
    facts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    event_count = len(events)
    candidates = [
        fact
        for fact in facts
        if fact["matched_count"] == 1
        and fact["last_sequence"] == event_count
        and str(fact["path"]).rsplit(".", 1)[-1] in _CANDIDATE_FACT_KEYS
        and str(fact["normalized_value"]).lower() not in _NOISE_VALUES
    ]
    return _end_rule_from_fact(events, facts, candidates[0]["fact_id"]) if candidates else None


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
    "build_structural_sse_candidates",
    "capture_sse_events",
    "execute_sse_probe",
    "extract_sse_event_facts",
    "generate_project_sse_metrics",
    "generate_sse_metric_candidate",
    "validate_sse_candidate",
]
