import json

from app.services.performance_testing.models import LocustScriptPlan


def render_locust_script(plan: LocustScriptPlan) -> str:
    plan_json = json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    wait_min = plan.load.wait_time_min_seconds
    wait_max = plan.load.wait_time_max_seconds
    locust_imports = "HttpUser, LoadTestShape, between, task" if plan.load.mode != "fixed" else "HttpUser, between, task"
    shape_source = _render_load_shape() if plan.load.mode != "fixed" else ""
    return f'''import json
import math
import random
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
        with self.client.request(
            method=request["method"],
            url=path,
            name=request["name"],
            params=query,
            headers=headers,
            json=body,
            timeout=request["timeout_seconds"],
            catch_response=True,
        ) as response:
            for rule in PLAN["success_rules"]:
                if rule["kind"] == "status_code" and response.status_code not in rule["status_codes"]:
                    response.failure(f"unexpected status code: {{response.status_code}}")
                    return
                if rule["kind"].startswith("jsonpath_"):
                    try:
                        payload = response.json()
                    except ValueError:
                        response.failure("response is not JSON")
                        return
                    exists, actual = _json_path(payload, rule["json_path"])
                    if rule["kind"] == "jsonpath_exists" and not exists:
                        response.failure(f"JSONPath missing: {{rule['json_path']}}")
                        return
                    if rule["kind"] == "jsonpath_equals" and (not exists or actual != rule["expected"]):
                        response.failure(f"JSONPath mismatch: {{rule['json_path']}}")
                        return
            response.success()
{shape_source}'''


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
