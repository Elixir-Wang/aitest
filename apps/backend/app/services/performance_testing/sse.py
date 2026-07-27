"""Safe SSE framing and first-match metric evaluation for performance tests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable


_PATH_TOKEN = re.compile(r"(?:\.([A-Za-z_][A-Za-z0-9_-]*)|\[([0-9]+|\*)\])")
_METRIC_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_OPERATORS = {"exists", "non_empty", "equals", "contains", "matches"}
_SOURCES = {"data_json", "data_text", "event_name"}


@dataclass(frozen=True)
class SseEvent:
    event_name: str
    data_text: str

    @property
    def data_json(self) -> Any | None:
        try:
            return json.loads(self.data_text)
        except json.JSONDecodeError:
            return None


def parse_sse_events(chunks: Iterable[str], *, max_frame_bytes: int = 262_144) -> list[SseEvent]:
    """Parse already-decoded SSE lines; an empty line commits the current frame."""
    events: list[SseEvent] = []
    event_name = ""
    data_lines: list[str] = []
    frame_size = 0
    first_line = True
    for raw_line in chunks:
        line = raw_line.rstrip("\r\n")
        if first_line:
            line = line.removeprefix("\ufeff")
            first_line = False
        if not line:
            if data_lines:
                events.append(SseEvent(event_name=event_name, data_text="\n".join(data_lines)))
            event_name, data_lines, frame_size = "", [], 0
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if not separator:
            continue
        value = value.removeprefix(" ")
        frame_size += len(line.encode("utf-8"))
        if frame_size > max_frame_bytes:
            raise ValueError("sse_frame_too_large")
        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)
    if data_lines:
        events.append(SseEvent(event_name=event_name, data_text="\n".join(data_lines)))
    return events


def validate_json_path(path: str) -> str:
    if path == "$":
        return path
    if not isinstance(path, str) or not path.startswith("$"):
        raise ValueError("JSONPath 必须以 $ 开头")
    position = 1
    while position < len(path):
        match = _PATH_TOKEN.match(path, position)
        if not match:
            raise ValueError("JSONPath 仅支持字段、数组下标和 [*]")
        position = match.end()
    return path


def extract_json_path(payload: Any, path: str) -> list[Any]:
    validate_json_path(path)
    values = [payload]
    position = 1
    while position < len(path):
        match = _PATH_TOKEN.match(path, position)
        assert match is not None
        field, index = match.groups()
        next_values: list[Any] = []
        for value in values:
            if field is not None:
                if isinstance(value, dict) and field in value:
                    next_values.append(value[field])
            elif index == "*" and isinstance(value, list):
                next_values.extend(value)
            elif index is not None and isinstance(value, list) and int(index) < len(value):
                next_values.append(value[int(index)])
        values = next_values
        position = match.end()
    return values


def validate_metric_rule(rule: dict[str, Any]) -> dict[str, Any]:
    metric_id = str(rule.get("id") or "")
    if not _METRIC_ID.fullmatch(metric_id):
        raise ValueError("指标 ID 必须以小写字母开头，且只能包含小写字母、数字和下划线")
    match = dict(rule.get("match") or {})
    source = match.get("source")
    operator = match.get("operator")
    if source not in _SOURCES or operator not in _OPERATORS:
        raise ValueError("SSE 指标包含不支持的匹配来源或操作符")
    if source == "data_json":
        validate_json_path(str(match.get("path") or ""))
    elif match.get("path"):
        raise ValueError("只有 data_json 可以配置字段路径")
    if operator in {"equals", "contains", "matches"} and "expected" not in match:
        raise ValueError("当前匹配操作符必须填写 expected")
    if operator == "matches":
        expected = str(match.get("expected") or "")
        if len(expected) > 256:
            raise ValueError("正则表达式不能超过 256 个字符")
        re.compile(expected)
    if rule.get("missing_policy", "record_null") not in {"record_null", "fail_request", "ignore"}:
        raise ValueError("不支持的 SSE 指标缺失策略")
    return rule


def event_matches(event: SseEvent, match: dict[str, Any]) -> bool:
    expected_event = str(match.get("event_name") or "")
    if expected_event and event.event_name != expected_event:
        return False
    source = match.get("source")
    if source == "data_json":
        payload = event.data_json
        if payload is None:
            return False
        values = extract_json_path(payload, str(match.get("path") or ""))
    elif source == "data_text":
        values = [event.data_text]
    else:
        values = [event.event_name]
    operator = match.get("operator")
    expected = match.get("expected")
    for value in values:
        if operator == "exists":
            return True
        if operator == "non_empty" and value not in (None, "", [], {}, False):
            return True
        if operator == "equals" and value == expected:
            return True
        if operator == "contains" and str(expected) in str(value):
            return True
        if operator == "matches" and re.search(str(expected), str(value)):
            return True
    return False
