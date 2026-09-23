"""Core runtime source inlined into generated standalone Locust files."""

import json
import math
import random
import re
import time
import uuid
from typing import Any

from locust import HttpUser, LoadTestShape, between, events, task


SSE_MEASUREMENT_SINK = None
_SSE_PATH_TOKEN = re.compile(r"(?:\.([A-Za-z_][A-Za-z0-9_-]*)|\[([0-9]+|\*)\])")


def set_sse_measurement_sink(sink) -> None:
    global SSE_MEASUREMENT_SINK
    SSE_MEASUREMENT_SINK = sink


def _resolve(value: Any, sequence: int, data: dict[str, Any], rng=random) -> Any:
    if isinstance(value, dict):
        return {key: _resolve(item, sequence, data, rng) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, sequence, data, rng) for item in value]
    if not isinstance(value, str):
        return value
    resolved = (
        value.replace("${sequence}", str(sequence))
        .replace("${uuid}", str(uuid.uuid4()))
        .replace("${timestamp}", str(int(time.time())))
        .replace("${random_int}", str(rng.randint(1, 1000000)))
    )
    for key, item in data.items():
        resolved = resolved.replace("${" + str(key) + "}", str(item))
    return resolved


def _json_path(payload: Any, path: str) -> tuple[bool, Any]:
    if not path or path == "$":
        return True, payload
    if path.startswith("/"):
        parts = [part.replace("~1", "/").replace("~0", "~") for part in path.strip("/").split("/") if part]
    else:
        parts = path.removeprefix("$").strip(".").replace("[", ".").replace("]", "").split(".")
    current = payload
    for part in parts:
        if not part:
            continue
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return True, current


def _variable(variables: dict[str, Any], key: Any) -> Any:
    if key in variables:
        return variables[key]
    normalized = str(key or "").lower().replace("_", "-")
    matches = [value for name, value in variables.items() if str(name).lower().replace("_", "-") == normalized]
    if len(matches) > 1:
        raise ValueError("ambiguous scenario variable: " + str(key))
    return matches[0] if matches else None


def _source(source: dict[str, Any], variables: dict[str, Any], outputs: dict[str, Any]) -> Any:
    kind = source.get("type")
    if kind == "literal":
        return source.get("value")
    if kind == "object":
        return {key: _source(item, variables, outputs) for key, item in (source.get("properties") or {}).items()}
    if kind in {"scenario", "environment", "secret", "user_input"}:
        return _variable(variables, source.get("name") or source.get("key"))
    if kind == "step_output":
        return (outputs.get(source.get("step_id")) or {}).get(source.get("variable"))
    if kind == "generated":
        generator = source.get("generator")
        if generator == "uuid4":
            return str(uuid.uuid4())
        if generator == "timestamp_ms":
            return int(time.time() * 1000)
        if generator == "timestamp_iso":
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if generator == "random_string":
            return uuid.uuid4().hex[: int(source.get("length") or 0)]
    raise ValueError("unsupported scenario source: " + str(kind))


def _condition(actual: Any, operator: str | None, expected: Any) -> bool:
    if operator == "exists":
        return actual is not None
    if operator == "non_empty":
        return actual not in (None, "", [], {})
    if operator in {"equals", "eq"}:
        return actual == expected
    if operator in {"not_equals", "ne"}:
        return actual != expected
    if operator == "contains":
        return expected in actual
    if operator == "matches":
        return re.search(str(expected), str(actual)) is not None
    if operator == "gt":
        return actual > expected
    if operator == "gte":
        return actual >= expected
    if operator == "lt":
        return actual < expected
    if operator == "lte":
        return actual <= expected
    raise ValueError("unsupported scenario condition: " + str(operator))


def _transform(value: Any, transform: str | None) -> Any:
    if not transform:
        return value
    if transform == "string":
        return str(value)
    if transform == "integer":
        return int(value)
    if transform == "float":
        return float(value)
    if transform == "boolean":
        if isinstance(value, str):
            return value.strip().lower() not in {"", "0", "false", "no", "off"}
        return bool(value)
    if transform == "json_encode":
        return json.dumps(value, ensure_ascii=False)
    raise ValueError("unsupported scenario transform: " + str(transform))


def _set_pointer(target: dict[str, Any], pointer: str, value: Any) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.strip("/").split("/") if part]
    if not parts:
        raise ValueError("scenario binding target is empty")
    current = target
    for part in parts[:-1]:
        current = current.setdefault(part, {})
        if not isinstance(current, dict):
            raise ValueError("scenario binding target is invalid: " + pointer)
    current[parts[-1]] = value


def _apply_bindings(request: dict[str, Any], bindings: list[dict[str, Any]], user) -> None:
    for binding in bindings:
        target = str(binding.get("target") or "")
        if not target.startswith("/request/"):
            raise ValueError("unsupported scenario binding target: " + target)
        source = binding.get("source") or {}
        value = _source(source, user.variables, user.outputs)
        if value is None:
            if binding.get("required"):
                raise ValueError(
                    "required scenario binding unresolved: "
                    + str(source.get("key") or source.get("name"))
                    + " -> "
                    + target
                )
            continue
        _set_pointer(request, target.removeprefix("/request"), _transform(value, binding.get("transform")))


def _payload_kwargs(request: dict[str, Any], headers: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved_headers = dict(headers if headers is not None else request.get("headers") or {})
    kwargs: dict[str, Any] = {"headers": resolved_headers, "cookies": request.get("cookies") or None}
    multipart = request.get("multipart_form")
    if multipart is not None:
        for key in list(resolved_headers):
            if key.lower() == "content-type":
                resolved_headers.pop(key)
        kwargs["files"] = [
            (str(field), (None, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)))
            for field, value in multipart.items()
        ]
    elif request.get("form") is not None:
        kwargs["data"] = request["form"]
    else:
        kwargs["json"] = request.get("body")
    return kwargs


def _assert_response(response, assertions: list[dict[str, Any]]) -> None:
    payload = None
    for assertion in assertions:
        assertion_type = assertion.get("type")
        expected = assertion.get("expected")
        if assertion_type == "status_code" and response.status_code != expected:
            raise AssertionError(f"unexpected status code: {response.status_code}")
        if assertion_type in {"json_path", "jsonpath_equals", "jsonpath_exists"}:
            if payload is None:
                payload = response.json()
            exists, actual = _json_path(payload, assertion.get("path") or assertion.get("json_path") or "")
            if not exists:
                raise AssertionError("JSONPath missing: " + str(assertion.get("path") or assertion.get("json_path")))
            if assertion_type != "jsonpath_exists" and actual != expected:
                raise AssertionError("JSONPath mismatch: " + str(assertion.get("path")))


def _assert_endpoint_success(response, rules: list[dict[str, Any]]) -> None:
    payload = None
    for rule in rules:
        kind = rule.get("kind")
        if kind == "status_code" and response.status_code not in rule.get("status_codes", []):
            raise AssertionError(f"unexpected status code: {response.status_code}")
        if kind in {"jsonpath_exists", "jsonpath_equals"}:
            if payload is None:
                payload = response.json()
            exists, actual = _json_path(payload, rule.get("json_path") or "")
            if not exists or (kind == "jsonpath_equals" and actual != rule.get("expected")):
                raise AssertionError("JSONPath mismatch: " + str(rule.get("json_path")))


def _extract(response, extractors: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for extractor in extractors:
        source = extractor.get("source") or "response.body"
        path = extractor.get("path") or extractor.get("expression") or ""
        if source in {"response.body", "json_body"}:
            exists, value = _json_path(response.json(), path)
            value = value if exists else None
        elif source in {"response.header", "header"}:
            value = response.headers.get(path)
        elif source in {"response.status", "status_code"}:
            value = response.status_code
        elif source == "text_regex":
            match = re.search(path, response.text or "")
            value = match.group(1) if match else None
        else:
            raise ValueError("unsupported scenario extractor: " + str(source))
        if extractor.get("required", True) and value is None:
            raise AssertionError("required extractor missing: " + str(extractor.get("name")))
        result[str(extractor.get("name"))] = value
    return result


def _sse_values(payload: Any, path: str) -> list[Any]:
    if not path.startswith("$"):
        return []
    values = [payload]
    position = 1
    while position < len(path):
        token = _SSE_PATH_TOKEN.match(path, position)
        if not token:
            return []
        field, index = token.groups()
        next_values = []
        for value in values:
            if field is not None and isinstance(value, dict) and field in value:
                next_values.append(value[field])
            elif index == "*" and isinstance(value, list):
                next_values.extend(value)
            elif index is not None and isinstance(value, list) and int(index) < len(value):
                next_values.append(value[int(index)])
        values = next_values
        position = token.end()
    return values


def _sse_matches(event_name: str, data_text: str, match: dict[str, Any]) -> bool:
    if match.get("event_name") and event_name != match["event_name"]:
        return False
    source = match.get("source")
    if source == "data_json":
        try:
            values = _sse_values(json.loads(data_text), match.get("path") or "")
        except (TypeError, ValueError):
            return False
    elif source == "data_text":
        values = [data_text]
    else:
        values = [event_name]
    for value in values:
        operator = match.get("operator")
        expected = match.get("expected")
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


def _sse_metric_roles(config: dict[str, Any]) -> tuple[str | None, set[str]]:
    llm_start = next(
        (
            metric["id"]
            for metric in config["metrics"]
            if metric["match"].get("source") == "data_json"
            and metric["match"].get("path") == "$.data.event_type"
            and metric["match"].get("operator") == "equals"
            and metric["match"].get("expected") == "call_llm_start"
        ),
        None,
    )
    first_output = {
        metric["id"]
        for metric in config["metrics"]
        if "first_output" in str(metric.get("id") or "") or "首次有效内容" in str(metric.get("name") or "")
    }
    return llm_start, first_output


def _execute_sse(
    user,
    request: dict[str, Any],
    path: str,
    step: dict[str, Any],
    measurement_context: dict[str, Any] | None = None,
) -> str:
    config = request["sse"]
    headers = dict(request.get("headers") or {})
    headers.setdefault("Accept", "text/event-stream")
    started_at = time.perf_counter()
    connection_ms = 0.0
    observed: dict[str, float] = {}
    event_name, data_lines, frame_size, stream_size, ended = "message", [], 0, 0, False
    failure_reason = ""
    quality = {
        "line_count": 0, "frame_count": 0, "data_frame_count": 0,
        "json_frame_count": 0, "non_json_frame_count": 0, "non_sse_line_count": 0,
        "stream_bytes": 0, "parse_error_count": 0, "content_type": "",
    }
    llm_start_id, first_output_ids = _sse_metric_roles(config)

    def record_frame(data_text: str) -> None:
        elapsed = (time.perf_counter() - started_at) * 1000
        quality["frame_count"] += 1
        quality["data_frame_count"] += 1
        try:
            json.loads(data_text)
            quality["json_frame_count"] += 1
        except (TypeError, ValueError):
            quality["non_json_frame_count"] += 1
            stripped_data = data_text.strip()
            looks_like_json = stripped_data.startswith(("{", "[")) and stripped_data not in {"[DONE]"}
            if looks_like_json and any(metric["match"].get("source") == "data_json" for metric in config["metrics"]):
                quality["parse_error_count"] += 1
        matched = [
            metric for metric in config["metrics"]
            if metric["id"] not in observed and _sse_matches(event_name, data_text, metric["match"])
        ]
        for metric in matched:
            if metric["id"] == llm_start_id:
                observed[metric["id"]] = elapsed
        for metric in matched:
            if metric["id"] != llm_start_id and not (
                metric["id"] in first_output_ids and llm_start_id and llm_start_id not in observed
            ):
                observed[metric["id"]] = elapsed
    with user.client.request(
        method=request["method"], url=path, name=request["name"], params=request.get("query_parameters") or {},
        **_payload_kwargs(request, headers=headers), timeout=request["timeout_seconds"], stream=True, catch_response=True,
    ) as response:
        connection_ms = (time.perf_counter() - started_at) * 1000
        quality["content_type"] = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        try:
            _assert_response(response, [item for item in step.get("assertions", []) if item.get("type") == "status_code"])
        except Exception as exc:
            failure_reason = str(exc)
        if not failure_reason and not 200 <= response.status_code < 300:
            failure_reason = f"unexpected status code: {response.status_code}"
        elif not failure_reason and str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower() != "text/event-stream":
            failure_reason = "sse_invalid_content_type"
        else:
            for raw_line in response.iter_lines(chunk_size=1, decode_unicode=True):
                if time.perf_counter() - started_at > config["max_stream_seconds"]:
                    failure_reason = "sse_stream_timeout"
                    break
                line = (raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else (raw_line or "")).removeprefix("\ufeff").rstrip("\r\n")
                quality["line_count"] += 1
                stream_size += len(line.encode("utf-8"))
                quality["stream_bytes"] = stream_size
                if stream_size > 16777216:
                    failure_reason = "sse_stream_too_large"
                    break
                if not line:
                    if data_lines:
                        data_text = "\n".join(data_lines)
                        record_frame(data_text)
                        ended = bool(config.get("end_rule") and _sse_matches(event_name, data_text, config["end_rule"])) or ended
                    event_name, data_lines, frame_size = "message", [], 0
                    if ended:
                        break
                    continue
                if line.startswith(":"):
                    continue
                if line.lstrip().startswith(("{", "[")):
                    try:
                        payload = json.loads(line)
                    except (TypeError, ValueError):
                        payload = None
                    if isinstance(payload, dict) and payload.get("code") is not None:
                        quality["non_sse_line_count"] += 1
                        failure_reason = "sse_business_error:" + re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload["code"]))[:64]
                        break
                field, separator, value = line.partition(":")
                if separator:
                    value = value.removeprefix(" ")
                    frame_size += len(line.encode("utf-8"))
                    if frame_size > 262144:
                        failure_reason = "sse_frame_too_large"
                        break
                    if field == "event":
                        event_name = value or "message"
                    elif field == "data":
                        data_lines.append(value)
            if data_lines and not ended and not failure_reason:
                data_text = "\n".join(data_lines)
                record_frame(data_text)
                ended = bool(config.get("end_rule") and _sse_matches(event_name, data_text, config["end_rule"]))
            if not failure_reason and quality["data_frame_count"] == 0:
                failure_reason = "sse_no_data_frames"
            if not failure_reason and config.get("end_rule") and not ended:
                failure_reason = "sse_end_rule_not_matched"
        measured = {}
        for metric in config["metrics"]:
            metric_id = metric["id"]
            if metric_id not in observed:
                continue
            timing = metric.get("timing") or {}
            if timing.get("start") == "metric_matched":
                start_metric_id = timing.get("start_metric_id")
                if start_metric_id not in observed or observed[metric_id] < observed[start_metric_id]:
                    continue
                measured[metric_id] = observed[metric_id] - observed[start_metric_id]
            else:
                measured[metric_id] = observed[metric_id]
        missing = [metric["id"] for metric in config["metrics"] if metric["id"] not in measured]
        reported_missing = [
            metric["id"] for metric in config["metrics"]
            if metric["id"] in missing and metric.get("missing_policy") != "ignore"
        ]
        required_missing = [metric["id"] for metric in config["metrics"] if metric["id"] in missing and metric["missing_policy"] == "fail_request"]
        if required_missing and not failure_reason:
            failure_reason = "sse_metric_missing:" + ",".join(required_missing)
        if failure_reason:
            response.failure(failure_reason)
        else:
            response.success()
    measurement = {
        "stream_completed_ms": round((time.perf_counter() - started_at) * 1000, 4),
        "connection_ms": round(connection_ms, 4),
        "source_request_id": (measurement_context or {}).get("scenario_step_id") or step.get("id") or "",
        "source_request_name": (measurement_context or {}).get("scenario_step_name") or step.get("name") or request.get("name") or "",
        "metrics": measured,
        "missing_metric_ids": reported_missing,
        "failure_reason": failure_reason,
        **quality,
        "response_error_code": re.search(r"sse_business_error:([^,]+)", failure_reason).group(1)
        if failure_reason.startswith("sse_business_error:") else "",
        **(measurement_context or {}),
    }
    if callable(SSE_MEASUREMENT_SINK):
        SSE_MEASUREMENT_SINK(measurement)
    if failure_reason:
        raise AssertionError(failure_reason)
    return failure_reason


def _run_step(user, step: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    step_type = step["step_type"]
    if step_type == "wait":
        time.sleep(max(0, float(step.get("control_config", {}).get("duration_ms", 0))) / 1000)
        return {}
    if step_type == "assign":
        config = step.get("control_config") or {}
        name = str(config.get("name") or "value")
        value = _source(config.get("source") or {}, user.variables, user.outputs)
        user.variables[name] = value
        return {name: value}
    if step_type == "condition":
        config = step.get("control_config") or {}
        actual = _source(config.get("source") or {}, user.variables, user.outputs)
        operator, expected = config.get("operator"), config.get("expected")
        if not _condition(actual, operator, expected):
            raise AssertionError("scenario condition failed")
        return {}
    request = _resolve(step["request"], user.sequence, data, user.rng)
    _apply_bindings(request, step.get("bindings") or [], user)
    path = request["path"]
    for key, value in request.get("path_parameters", {}).items():
        path = path.replace("{" + str(key) + "}", str(value))
    if request.get("transport") == "sse":
        _execute_sse(user, request, path, step)
        return {}
    with user.client.request(
        method=request["method"], url=path, name=request["name"], params=request.get("query_parameters") or {},
        **_payload_kwargs(request), timeout=request["timeout_seconds"], catch_response=True,
    ) as response:
        try:
            _assert_response(response, step.get("assertions") or [])
            extracted = _extract(response, step.get("extractors") or [])
        except Exception as exc:
            response.failure(str(exc))
            raise
        response.success()
        return extracted


def execute_plan(user, plan: dict[str, Any]) -> None:
    user.sequence += 1
    rows = plan.get("data", {}).get("json_rows") or []
    if rows:
        if plan.get("data", {}).get("selection_strategy") == "random":
            data = user.rng.choice(rows)
        else:
            data = rows[user.data_index % len(rows)]
            user.data_index += 1
    else:
        data = {}
    user.variables = {**user.base_variables, **data}
    user.outputs = {}
    started_at = time.perf_counter()
    first_error = None
    stop_chain = False
    for step in plan.get("steps") or []:
        if stop_chain and step.get("on_failure") != "always_run":
            continue
        try:
            user.outputs[step["id"]] = _run_step(user, step, data)
        except Exception as exc:
            first_error = first_error or exc
            if step.get("on_failure") != "continue":
                stop_chain = True
    events.request.fire(
        request_type="SCENARIO", name="SCENARIO " + str(plan.get("scenario_name") or "scenario"),
        response_time=(time.perf_counter() - started_at) * 1000, response_length=0, exception=first_error,
    )


def execute_endpoint(user, plan: dict[str, Any]) -> None:
    user.sequence += 1
    rows = plan.get("data", {}).get("json_rows") or []
    if rows and plan.get("data", {}).get("selection_strategy") == "random":
        data = user.rng.choice(rows)
    else:
        data = rows[user.data_index % len(rows)] if rows else {}
    if rows and plan.get("data", {}).get("selection_strategy") != "random":
        user.data_index += 1
    request = _resolve(plan["request"], user.sequence, data, user.rng)
    path = request["path"]
    for key, value in request.get("path_parameters", {}).items():
        path = path.replace("{" + str(key) + "}", str(value))
    if request.get("transport") == "sse":
        status_codes = next(
            (rule.get("status_codes") or [] for rule in plan.get("success_rules") or [] if rule.get("kind") == "status_code"),
            [],
        )
        assertions = [{"type": "status_code", "expected": status_codes[0]}] if len(status_codes) == 1 else []
        _execute_sse(
            user,
            request,
            path,
            {"id": "endpoint", "name": request["name"], "assertions": assertions},
        )
        return
    with user.client.request(
        method=request["method"], url=path, name=request["name"],
        params=request.get("query_parameters") or {}, **_payload_kwargs(request),
        timeout=request["timeout_seconds"], catch_response=True,
    ) as response:
        try:
            _assert_endpoint_success(response, plan.get("success_rules") or [])
        except Exception as exc:
            response.failure(str(exc))
            return
        response.success()


class ScenarioUser(HttpUser):
    abstract = True
    plan: dict[str, Any] = {}

    def on_start(self):
        self.sequence = 0
        self.data_index = 0
        self.base_variables = dict(self.plan.get("scenario_variables") or {})
        self.variables = dict(self.base_variables)
        self.outputs = {}
        self.rng = random.Random(self.plan.get("random_seed"))

    def run_plan(self) -> None:
        execute_plan(self, self.plan)


class EndpointUser(HttpUser):
    abstract = True
    plan: dict[str, Any] = {}

    def on_start(self):
        self.sequence = 0
        self.data_index = 0
        self.rng = random.Random(self.plan.get("random_seed"))

    def run_plan(self) -> None:
        execute_endpoint(self, self.plan)


class PerformanceLoadShape(LoadTestShape):
    next_breaker_check = 0.0
    previous_requests = 0
    previous_failures = 0
    failed_windows = 0

    def tick(self):
        run_time = self.get_run_time()
        breaker = self.plan.get("circuit_breaker") or {}
        if breaker.get("enabled") and run_time >= self.next_breaker_check:
            total = self.runner.stats.total
            window_requests = total.num_requests - self.previous_requests
            window_failures = total.num_failures - self.previous_failures
            if window_requests > 0:
                if window_failures / window_requests > breaker["max_fail_ratio"]:
                    self.failed_windows += 1
                else:
                    self.failed_windows = 0
                self.previous_requests = total.num_requests
                self.previous_failures = total.num_failures
            self.next_breaker_check = run_time + breaker["window_seconds"]
            if self.failed_windows >= breaker["consecutive_windows"]:
                return None
        stages = self.user_count_stages
        elapsed = 0
        previous_users = 0
        for stage in stages:
            ramp_seconds = max(1, math.ceil(abs(stage["target_users"] - previous_users) / stage["spawn_rate"]))
            elapsed += ramp_seconds + stage["hold_seconds"]
            if run_time < elapsed:
                return stage["target_users"], stage["spawn_rate"]
            previous_users = stage["target_users"]
        return None

    @property
    def user_count_stages(self):
        return self.plan.get("load", {}).get("stages", [])
