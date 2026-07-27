import json

from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan


def render_locust_script(plan: LocustScriptPlan) -> str:
    plan_json = json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    locust_imports = "HttpUser, LoadTestShape, between, task" if plan.load.mode != "fixed" else "HttpUser, between, task"
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


def _json_path(payload, path):
    current = payload
    for part in path.removeprefix("$").strip(".").split("."):
        if not part:
            continue
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current
'''
    if plan.request.transport == "sse":
        body = _render_sse_helpers() + _render_sse_user(plan.load.wait_time_min_seconds, plan.load.wait_time_max_seconds)
    else:
        body = _render_http_user(plan.load.wait_time_min_seconds, plan.load.wait_time_max_seconds)
    return prefix + body + (_render_load_shape() if plan.load.mode != "fixed" else "")


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


def _sse_finish_frame(event_name, data_lines, started_at, config, observed):
    if not data_lines:
        return False
    data_text = "\\n".join(data_lines)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    for metric in config["metrics"]:
        if metric["id"] not in observed and _sse_matches(event_name, data_text, metric["match"]):
            observed[metric["id"]] = elapsed_ms
    end_rule = config.get("end_rule")
    return bool(end_rule and _sse_matches(event_name, data_text, end_rule))
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
        request = PLAN["request"]
        config = request["sse"]
        path = request["path"]
        for key, value in _resolve(request["path_parameters"], self.sequence, data).items():
            path = path.replace("{{" + key + "}}", str(value))
        headers = _resolve(request["headers"], self.sequence, data)
        headers.setdefault("Accept", "text/event-stream")
        started_at = time.perf_counter()
        observed = {{}}
        event_name, data_lines, frame_size, ended = "", [], 0, False
        failure_reason = ""
        with self.client.request(method=request["method"], url=path, name=request["name"], params=_resolve(request["query_parameters"], self.sequence, data), headers=headers, json=_resolve(request["body"], self.sequence, data), timeout=request["timeout_seconds"], stream=True, catch_response=True) as response:
            status_rules = [rule for rule in PLAN["success_rules"] if rule["kind"] == "status_code"]
            allowed_statuses = status_rules[0]["status_codes"] if status_rules else [200]
            if response.status_code not in allowed_statuses:
                failure_reason = f"unexpected status code: {{response.status_code}}"
            else:
                for raw_line in response.iter_lines(decode_unicode=True):
                    if (time.perf_counter() - started_at) > config["max_stream_seconds"]:
                        failure_reason = "sse_stream_timeout"
                        break
                    if isinstance(raw_line, bytes):
                        raw_line = raw_line.decode("utf-8", errors="replace")
                    line = (raw_line or "").removeprefix("\\ufeff")
                    if not line:
                        ended = _sse_finish_frame(event_name, data_lines, started_at, config, observed) or ended
                        event_name, data_lines, frame_size = "", [], 0
                        if ended:
                            break
                    elif line.startswith(":"):
                        continue
                    else:
                        field, separator, value = line.partition(":")
                        if separator:
                            value = value.removeprefix(" ")
                            frame_size += len(line.encode("utf-8"))
                            if frame_size > 262144:
                                failure_reason = "sse_frame_too_large"
                                break
                            if field == "event":
                                event_name = value
                            elif field == "data":
                                data_lines.append(value)
                if data_lines and not ended and not failure_reason:
                    ended = _sse_finish_frame(event_name, data_lines, started_at, config, observed)
                if not failure_reason and config.get("end_rule") and not ended:
                    failure_reason = "sse_end_rule_not_matched"
            missing = [metric["id"] for metric in config["metrics"] if metric["id"] not in observed]
            required_missing = [metric["id"] for metric in config["metrics"] if metric["id"] in missing and metric["missing_policy"] == "fail_request"]
            if required_missing and not failure_reason:
                failure_reason = "sse_metric_missing:" + ",".join(required_missing)
            if failure_reason:
                response.failure(failure_reason)
            else:
                response.success()
        measurement = {{"stream_completed_ms": round((time.perf_counter() - started_at) * 1000, 4), "metrics": observed, "missing_metric_ids": missing, "failure_reason": failure_reason}}
        if callable(SSE_MEASUREMENT_SINK):
            SSE_MEASUREMENT_SINK(measurement)
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
