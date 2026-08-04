import json

from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan


def render_locust_script(plan: LocustScriptPlan) -> str:
    plan_json = json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    locust_imports = "HttpUser, between, events, task" if plan.target_type == "scenario" else "HttpUser, between, task"
    if plan.load.mode != "fixed":
        locust_imports = locust_imports.replace("HttpUser,", "HttpUser, LoadTestShape,")
    prefix = f'''import json
import math
import random
import re
import time
import uuid

from locust import {locust_imports}


PLAN = json.loads({plan_json!r})


def _resolve(value, sequence, data):
    if isinstance(value, dict):
        return {{key: _resolve(item, sequence, data) for key, item in value.items()}}
    if isinstance(value, list):
        return [_resolve(item, sequence, data) for item in value]
    if not isinstance(value, str):
        return value
    resolved = (
        value.replace("${{sequence}}", str(sequence))
        .replace("${{uuid}}", str(uuid.uuid4()))
        .replace("${{timestamp}}", str(int(time.time())))
        .replace("${{random_int}}", str(random.randint(1, 1000000)))
    )
    for key, item in data.items():
        resolved = resolved.replace("${{" + str(key) + "}}", str(item))
    return resolved


def _next_data_row(user):
    rows = PLAN["data"]["json_rows"]
    if not rows:
        return {{}}
    if PLAN["data"]["selection_strategy"] == "random":
        return random.choice(rows)
    row = rows[user.data_index % len(rows)]
    user.data_index += 1
    return row


def _request_payload_kwargs(request, headers=None):
    resolved_headers = dict(headers if headers is not None else request.get("headers") or {{}})
    kwargs = {{
        "headers": resolved_headers,
        "cookies": request.get("cookies") or None,
    }}
    multipart = request.get("multipart_form")
    form = request.get("form")
    if multipart is not None:
        for key in list(resolved_headers):
            if key.lower() == "content-type":
                resolved_headers.pop(key)
        kwargs["files"] = [
            (str(field), (None, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)))
            for field, value in multipart.items()
        ]
    elif form is not None:
        kwargs["data"] = form
    else:
        kwargs["json"] = request.get("body")
    return kwargs


def _json_path(payload, path):
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
'''
    if plan.target_type == "scenario":
        has_sse_step = any(step.request and step.request.transport == "sse" for step in plan.steps)
        body = _render_scenario_helpers() + (_render_sse_helpers() if has_sse_step else "") + _render_scenario_user(
            plan.load.wait_time_min_seconds,
            plan.load.wait_time_max_seconds,
            plan.scenario_name,
        )
    elif plan.request and plan.request.transport == "sse":
        body = _render_sse_helpers() + _render_sse_user(plan.load.wait_time_min_seconds, plan.load.wait_time_max_seconds)
    else:
        body = _render_http_user(plan.load.wait_time_min_seconds, plan.load.wait_time_max_seconds)
    return prefix + body + (_render_load_shape() if plan.load.mode != "fixed" else "")


def _render_scenario_helpers() -> str:
    return r'''


def _scenario_variable(variables, key):
    if key in variables:
        return variables[key]
    normalized = str(key or "").lower().replace("_", "-")
    matches = []
    for variable_name, value in variables.items():
        if str(variable_name).lower().replace("_", "-") == normalized:
            matches.append(value)
    if len(matches) > 1:
        raise ValueError("ambiguous scenario variable: " + str(key))
    if matches:
        return matches[0]
    return None


def _scenario_source(source, variables, outputs):
    kind = source.get("type")
    if kind == "literal":
        return source.get("value")
    if kind == "object":
        return {key: _scenario_source(value, variables, outputs) for key, value in (source.get("properties") or {}).items()}
    if kind in {"scenario", "environment", "secret", "user_input"}:
        return _scenario_variable(variables, source.get("name") or source.get("key"))
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
            return uuid.uuid4().hex[:int(source.get("length") or 0)]
    raise ValueError("unsupported scenario source: " + str(kind))


def _scenario_transform(value, transform):
    if not transform:
        return value
    if transform == "string":
        return str(value)
    if transform == "integer":
        return int(value)
    if transform == "float":
        return float(value)
    if transform == "boolean":
        return bool(value)
    if transform == "json_encode":
        return json.dumps(value, ensure_ascii=False)
    raise ValueError("unsupported scenario transform: " + str(transform))


def _scenario_binding_source_name(source):
    return str(source.get("name") or source.get("key") or source.get("variable") or source.get("type") or "unknown")


def _apply_scenario_bindings(request, bindings, variables, outputs):
    for binding in bindings:
        target = str(binding.get("target") or "")
        if not target.startswith("/request/"):
            raise ValueError("unsupported scenario binding target: " + target)
        source = binding.get("source") or {}
        value = _scenario_source(source, variables, outputs)
        if value is None:
            if binding.get("required"):
                raise ValueError(
                    "required scenario binding unresolved: "
                    + _scenario_binding_source_name(source)
                    + " -> "
                    + target
                )
            continue
        value = _scenario_transform(value, binding.get("transform"))
        _scenario_set_pointer(request, target.removeprefix("/request"), value)


def _scenario_set_pointer(target, pointer, value):
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.strip("/").split("/") if part]
    if not parts:
        raise ValueError("scenario binding target is empty")
    current = target
    for part in parts[:-1]:
        current = current.setdefault(part, {})
        if not isinstance(current, dict):
            raise ValueError("scenario binding target is invalid: " + pointer)
    current[parts[-1]] = value


def _scenario_value(payload, path):
    if not path or path == "$":
        return payload
    exists, value = _json_path(payload, path)
    return value if exists else None


def _scenario_condition(actual, operator, expected):
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


def _scenario_assert(response, assertions):
    payload = None
    for assertion in assertions:
        assertion_type = assertion.get("type")
        expected = assertion.get("expected")
        if assertion_type == "status_code" and response.status_code != expected:
            raise AssertionError(f"unexpected status code: {response.status_code}")
        if assertion_type in {"json_path", "jsonpath_equals", "jsonpath_exists"}:
            if payload is None:
                payload = response.json()
            path = assertion.get("path") or assertion.get("json_path") or ""
            actual = _scenario_value(payload, path)
            if assertion_type == "jsonpath_exists" and actual is None:
                raise AssertionError("JSONPath missing: " + path)
            if assertion_type != "jsonpath_exists" and actual != expected:
                raise AssertionError("JSONPath mismatch: " + path)


def _scenario_extract(response, extractors):
    result = {}
    for extractor in extractors:
        source = extractor.get("source") or "response.body"
        path = extractor.get("path") or extractor.get("expression") or ""
        if source in {"response.body", "json_body"}:
            value = _scenario_value(response.json(), path)
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


def _run_scenario_step(user, step, data):
    step_type = step["step_type"]
    if step_type == "wait":
        time.sleep(max(0, float(step.get("control_config", {}).get("duration_ms", 0))) / 1000)
        return {}
    if step_type == "assign":
        config = step.get("control_config") or {}
        name = str(config.get("name") or "value")
        value = _scenario_source(config.get("source") or {}, user.variables, user.outputs)
        user.variables[name] = value
        return {name: value}
    if step_type == "condition":
        config = step.get("control_config") or {}
        actual = _scenario_source(config.get("source") or {}, user.variables, user.outputs)
        if not _scenario_condition(actual, config.get("operator"), config.get("expected")):
            raise AssertionError("scenario condition failed")
        return {}

    request = _resolve(step["request"], user.sequence, data)
    _apply_scenario_bindings(request, step.get("bindings") or [], user.variables, user.outputs)
    path = request["path"]
    for key, value in request.get("path_parameters", {}).items():
        path = path.replace("{" + str(key) + "}", str(value))
    if request.get("transport") == "sse":
        failure_reason = _execute_sse_request(
            user,
            request,
            path,
            measurement_context={"scenario_step_id": step["id"], "scenario_step_name": step["name"]},
        )
        if failure_reason:
            raise AssertionError(failure_reason)
        return {}
    with user.client.request(
        method=request["method"],
        url=path,
        name=request["name"],
        params=request.get("query_parameters") or {},
        **_request_payload_kwargs(request),
        timeout=request["timeout_seconds"],
        catch_response=True,
    ) as response:
        try:
            _scenario_assert(response, step.get("assertions") or [])
            extracted = _scenario_extract(response, step.get("extractors") or [])
        except Exception as exc:
            response.failure(str(exc))
            raise
        response.success()
        return extracted
'''


def _render_scenario_user(wait_min: float, wait_max: float, scenario_name: str) -> str:
    return f'''


class PerformanceUser(HttpUser):
    wait_time = between({wait_min!r}, {wait_max!r})

    def on_start(self):
        self.sequence = 0
        self.data_index = 0
        self.base_variables = dict(PLAN.get("scenario_variables") or {{}})
        self.variables = dict(self.base_variables)
        self.outputs = {{}}
        if PLAN.get("random_seed") is not None:
            random.seed(PLAN["random_seed"])

    @task
    def execute_target(self):
        self.sequence += 1
        data = _next_data_row(self)
        self.variables = {{**self.base_variables, **data}}
        self.outputs = {{}}
        started_at = time.perf_counter()
        first_error = None
        stop_chain = False
        for step in PLAN["steps"]:
            if stop_chain and step.get("on_failure") != "always_run":
                continue
            try:
                self.outputs[step["id"]] = _run_scenario_step(self, step, data)
            except Exception as exc:
                if first_error is None:
                    first_error = exc
                if step.get("on_failure") != "continue":
                    stop_chain = True
        events.request.fire(
            request_type="SCENARIO",
            name={f"SCENARIO {scenario_name}"!r},
            response_time=(time.perf_counter() - started_at) * 1000,
            response_length=0,
            exception=first_error,
        )
'''


def _render_http_user(wait_min: float, wait_max: float) -> str:
    return f'''

class PerformanceUser(HttpUser):
    wait_time = between({wait_min!r}, {wait_max!r})

    def on_start(self):
        self.sequence = 0
        self.data_index = 0
        if PLAN.get("random_seed") is not None:
            random.seed(PLAN["random_seed"])

    @task
    def execute_target(self):
        self.sequence += 1
        data = _next_data_row(self)
        request = PLAN["request"]
        path = request["path"]
        for key, value in _resolve(request["path_parameters"], self.sequence, data).items():
            path = path.replace("{{" + key + "}}", str(value))
        query = _resolve(request["query_parameters"], self.sequence, data)
        headers = _resolve(request["headers"], self.sequence, data)
        body = _resolve(request["body"], self.sequence, data)
        with self.client.request(method=request["method"], url=path, name=request["name"], params=query, headers=headers, json=body, timeout=request["timeout_seconds"], catch_response=True) as response:
            payload = None
            payload_loaded = False
            for rule in PLAN["success_rules"]:
                if rule["kind"] == "status_code" and response.status_code not in rule["status_codes"]:
                    response.failure(f"unexpected status code: {{response.status_code}}")
                    return
                if rule["kind"].startswith("jsonpath_"):
                    if not payload_loaded:
                        try:
                            payload = response.json()
                        except ValueError:
                            response.failure("response is not JSON")
                            return
                        payload_loaded = True
                    exists, actual = _json_path(payload, rule["json_path"])
                    if rule["kind"] == "jsonpath_exists" and not exists:
                        response.failure(f"JSONPath missing: {{rule['json_path']}}")
                        return
                    if rule["kind"] == "jsonpath_equals" and (not exists or actual != rule["expected"]):
                        response.failure(f"JSONPath mismatch: {{rule['json_path']}}")
                        return
            response.success()
'''


def _render_sse_helpers() -> str:
    return '''

SSE_MEASUREMENT_SINK = None
_SSE_PATH_TOKEN = re.compile(r"(?:\\.([A-Za-z_][A-Za-z0-9_-]*)|\\[([0-9]+|\\*)\\])")


def _sse_values(payload, path):
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


def _sse_matches(event_name, data_text, match):
    expected_event = str(match.get("event_name") or "")
    if expected_event and event_name != expected_event:
        return False
    if match["source"] == "data_json":
        try:
            values = _sse_values(json.loads(data_text), match.get("path") or "")
        except (TypeError, ValueError):
            return False
    elif match["source"] == "data_text":
        values = [data_text]
    else:
        values = [event_name]
    for value in values:
        operator = match["operator"]
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


def _sse_finish_frame(event_name, data_lines, started_at, config, observed, quality):
    if not data_lines:
        return False
    data_text = "\\n".join(data_lines)
    quality["frame_count"] += 1
    quality["data_frame_count"] += 1
    requires_json = any(metric["match"]["source"] == "data_json" for metric in config["metrics"])
    requires_json = requires_json or bool(config.get("end_rule") and config["end_rule"]["source"] == "data_json")
    try:
        json.loads(data_text)
        quality["json_frame_count"] += 1
    except (TypeError, ValueError):
        quality["non_json_frame_count"] += 1
        if requires_json:
            quality["parse_error_count"] += 1
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    for metric in config["metrics"]:
        if metric["id"] not in observed and _sse_matches(event_name, data_text, metric["match"]):
            observed[metric["id"]] = elapsed_ms
    end_rule = config.get("end_rule")
    return bool(end_rule and _sse_matches(event_name, data_text, end_rule))


def _execute_sse_request(user, request, path, measurement_context=None):
    config = request["sse"]
    headers = dict(request.get("headers") or {})
    headers.setdefault("Accept", "text/event-stream")
    started_at = time.perf_counter()
    observed = {}
    event_name, data_lines, frame_size, stream_size, ended = "message", [], 0, 0, False
    quality = {
        "parse_error_count": 0,
        "line_count": 0,
        "frame_count": 0,
        "data_frame_count": 0,
        "json_frame_count": 0,
        "non_json_frame_count": 0,
        "non_sse_line_count": 0,
        "stream_bytes": 0,
        "content_type": "",
        "response_error_code": "",
    }
    failure_reason = ""
    with user.client.request(
        method=request["method"],
        url=path,
        name=request["name"],
        params=request.get("query_parameters") or {},
        **_request_payload_kwargs(request, headers=headers),
        timeout=request["timeout_seconds"],
        stream=True,
        catch_response=True,
    ) as response:
        quality["content_type"] = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if not 200 <= response.status_code < 300:
            failure_reason = f"unexpected status code: {response.status_code}"
        elif quality["content_type"] != "text/event-stream":
            failure_reason = "sse_invalid_content_type"
        else:
            for raw_line in response.iter_lines(decode_unicode=True):
                if (time.perf_counter() - started_at) > config["max_stream_seconds"]:
                    failure_reason = "sse_stream_timeout"
                    break
                if isinstance(raw_line, bytes):
                    raw_line = raw_line.decode("utf-8", errors="replace")
                line = (raw_line or "").removeprefix("\\ufeff").rstrip("\\r\\n")
                quality["line_count"] += 1
                stream_size += len(line.encode("utf-8"))
                quality["stream_bytes"] = stream_size
                if stream_size > 16777216:
                    failure_reason = "sse_stream_too_large"
                    break
                if not line:
                    ended = _sse_finish_frame(event_name, data_lines, started_at, config, observed, quality) or ended
                    event_name, data_lines, frame_size = "message", [], 0
                    if ended:
                        break
                elif line.startswith(":"):
                    continue
                else:
                    json_payload = None
                    separator = ""
                    if line.lstrip().startswith(("{", "[")):
                        try:
                            json_payload = json.loads(line)
                        except (TypeError, ValueError):
                            json_payload = None
                    if isinstance(json_payload, dict) and json_payload.get("code") is not None:
                        quality["non_sse_line_count"] += 1
                        quality["response_error_code"] = re.sub(
                            r"[^A-Za-z0-9_.-]", "_", str(json_payload["code"])
                        )[:64]
                    else:
                        field, separator, value = line.partition(":")
                    if separator and json_payload is None:
                        value = value.removeprefix(" ")
                        frame_size += len(line.encode("utf-8"))
                        if frame_size > 262144:
                            failure_reason = "sse_frame_too_large"
                            break
                        if field == "event":
                            event_name = value or "message"
                        elif field == "data":
                            data_lines.append(value)
                    elif not isinstance(json_payload, dict):
                        quality["non_sse_line_count"] += 1
            if data_lines and not ended and not failure_reason:
                ended = _sse_finish_frame(event_name, data_lines, started_at, config, observed, quality)
            if not failure_reason and quality["data_frame_count"] == 0:
                if quality["response_error_code"]:
                    failure_reason = "sse_business_error:" + quality["response_error_code"]
                else:
                    failure_reason = "sse_no_data_frames"
            if not failure_reason and config.get("end_rule") and not ended:
                failure_reason = "sse_end_rule_not_matched"
        missing = [metric["id"] for metric in config["metrics"] if metric["id"] not in observed]
        reported_missing = [metric["id"] for metric in config["metrics"] if metric["id"] in missing and metric["missing_policy"] != "ignore"]
        required_missing = [metric["id"] for metric in config["metrics"] if metric["id"] in missing and metric["missing_policy"] == "fail_request"]
        if required_missing and not failure_reason:
            failure_reason = "sse_metric_missing:" + ",".join(required_missing)
        if failure_reason:
            response.failure(failure_reason)
        else:
            response.success()
    first_content_id = next((metric["id"] for metric in config["metrics"] if metric["match"].get("source") == "data_json" and metric["match"].get("path") == "$.data.answer" and metric["match"].get("operator") == "non_empty"), None)
    llm_start_id = next((metric["id"] for metric in config["metrics"] if metric["match"].get("source") == "data_json" and metric["match"].get("path") == "$.data.event_type" and metric["match"].get("operator") == "equals" and metric["match"].get("expected") == "call_llm_start"), None)
    derived_metrics = {}
    if first_content_id in observed and llm_start_id in observed:
        derived_metrics["llm_start_to_first_content_ms"] = max(0, observed[first_content_id] - observed[llm_start_id])
    measurement = {"stream_completed_ms": round((time.perf_counter() - started_at) * 1000, 4), "metrics": observed, "derived_metrics": derived_metrics, "missing_metric_ids": reported_missing, "failure_reason": failure_reason, **quality, **(measurement_context or {})}
    if callable(SSE_MEASUREMENT_SINK):
        SSE_MEASUREMENT_SINK(measurement)
    return failure_reason
'''


def _render_sse_user(wait_min: float, wait_max: float) -> str:
    return f'''

class PerformanceUser(HttpUser):
    wait_time = between({wait_min!r}, {wait_max!r})

    def on_start(self):
        self.sequence = 0
        self.data_index = 0
        if PLAN.get("random_seed") is not None:
            random.seed(PLAN["random_seed"])

    @task
    def execute_target(self):
        self.sequence += 1
        data = _next_data_row(self)
        request = _resolve(PLAN["request"], self.sequence, data)
        path = request["path"]
        for key, value in request["path_parameters"].items():
            path = path.replace("{{" + key + "}}", str(value))
        _execute_sse_request(self, request, path)
'''


def _render_load_shape() -> str:
    return '''


class PerformanceLoadShape(LoadTestShape):
    def tick(self):
        run_time = self.get_run_time()
        elapsed = 0
        previous_users = 0
        for stage in PLAN["load"]["stages"]:
            ramp_seconds = math.ceil(abs(stage["target_users"] - previous_users) / stage["spawn_rate"])
            elapsed += ramp_seconds + stage["hold_seconds"]
            if run_time < elapsed:
                return (stage["target_users"], stage["spawn_rate"])
            previous_users = stage["target_users"]
        return None
'''
