import re
from pprint import pformat
from typing import Any

from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan
from app.services.performance_testing.compiler.blocks import resolve_blocks, source_for_blocks
from app.services.performance_testing.compiler.capabilities import analyze_capabilities
from app.services.performance_testing.locust_runtime import standalone_runtime_support_source


_SENSITIVE_KEY_MARKERS = ("authorization", "credential", "password", "secret", "token", "api_key")


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return normalized == "key" or normalized.endswith("_key") or any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def _environment_name(key: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(key).upper()).strip("_") or "SECRET"


def _externalize_sensitive_values(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: f"${{ENV:{_environment_name(key)}}}" if _is_sensitive_key(key) and value not in (None, "") else value
        for key, value in values.items()
    }


def runtime_plan(plan: LocustScriptPlan) -> dict[str, Any]:
    raw = plan.model_dump(mode="json")
    if plan.target_type == "scenario":
        steps = raw.get("steps") or []
        for step in steps:
            request = step.get("request") if isinstance(step, dict) else None
            if isinstance(request, dict):
                request["headers"] = _externalize_sensitive_values(dict(request.get("headers") or {}))
        payload = {"target_type": "scenario", "scenario_name": plan.scenario_name, "steps": steps}
        if raw.get("scenario_variables"):
            payload["scenario_variables"] = _externalize_sensitive_values(raw["scenario_variables"])
    else:
        request = raw.get("request")
        if isinstance(request, dict):
            request["headers"] = _externalize_sensitive_values(dict(request.get("headers") or {}))
        payload = {"target_type": "endpoint", "request": request, "success_rules": raw.get("success_rules") or []}
    if raw.get("data", {}).get("json_rows"):
        payload["data"] = raw["data"]
    if raw.get("random_seed") is not None:
        payload["random_seed"] = raw["random_seed"]
    if plan.load.mode != "fixed":
        payload["load"] = {"stages": raw.get("load", {}).get("stages") or []}
        payload["circuit_breaker"] = raw.get("circuit_breaker") or {}
    return payload


def _requested_blocks(capabilities) -> set[str]:
    requested = {"sse"} if capabilities.uses_sse else set()
    requested.add("scenario" if capabilities.target_type == "scenario" else "endpoint")
    if capabilities.target_type == "endpoint" and not capabilities.uses_sse:
        requested.add("endpoint_assertions")
    if capabilities.uses_bindings or capabilities.uses_assignments or capabilities.uses_conditions:
        requested.add("bindings")
    if capabilities.uses_conditions:
        requested.add("conditions")
    if capabilities.uses_extractors:
        requested.add("extractors")
    if capabilities.uses_dynamic_values:
        requested.add("dynamic_values")
    if capabilities.uses_load_shape:
        requested.add("load_shape")
    return requested


def _scenario_step_runner_source(capabilities) -> str:
    control_branches = []
    if capabilities.uses_wait_steps:
        control_branches.append(
            '''    if step_type == "wait":
        time.sleep(max(0, float(step.get("control_config", {}).get("duration_ms", 0))) / 1000)
        return {}'''
        )
    if capabilities.uses_assignments:
        control_branches.append(
            '''    if step_type == "assign":
        config = step.get("control_config") or {}
        name = str(config.get("name") or "value")
        value = _source(config.get("source") or {}, user.variables, user.outputs)
        user.variables[name] = value
        return {name: value}'''
        )
    if capabilities.uses_conditions:
        control_branches.append(
            '''    if step_type == "condition":
        config = step.get("control_config") or {}
        actual = _source(config.get("source") or {}, user.variables, user.outputs)
        if not _condition(actual, config.get("operator"), config.get("expected")):
            raise AssertionError("scenario condition failed")
        return {}'''
        )
    bindings = "    _apply_bindings(request, step.get(\"bindings\") or [], user)\n" if capabilities.uses_bindings else ""
    sse = (
        '''    if request.get("transport") == "sse":
        _execute_sse(user, request, path, step)
        return {}
'''
        if capabilities.uses_sse
        else ""
    )
    extraction = "            extracted = _extract(response, step.get(\"extractors\") or [])" if capabilities.uses_extractors else "            extracted = {}"
    controls = "\n".join(control_branches)
    if controls:
        controls += "\n"
    step_type = '    step_type = step["step_type"]\n' if control_branches else ""
    return f'''def _run_step(user, step: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
{step_type}{controls}    request = _resolve(step["request"], user.sequence, data, user.rng)
{bindings}    path = request["path"]
    for key, value in request.get("path_parameters", {{}}).items():
        path = path.replace("{{" + str(key) + "}}", str(value))
{sse}    with user.client.request(
        method=request["method"], url=path, name=request["name"], params=request.get("query_parameters") or {{}},
        **_payload_kwargs(request), timeout=request["timeout_seconds"], catch_response=True,
    ) as response:
        try:
            _assert_response(response, step.get("assertions") or [])
{extraction}
        except Exception as exc:
            response.failure(str(exc))
            raise
        response.success()
        return extracted'''


def _static_value_resolver_source() -> str:
    return '''def _resolve(value: Any, sequence: int, data: dict[str, Any], rng=random) -> Any:
    if isinstance(value, dict):
        return {key: _resolve(item, sequence, data, rng) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, sequence, data, rng) for item in value]
    return value'''


def _scenario_plan_runner_source(capabilities) -> str:
    if capabilities.uses_data_rows:
        data_selection = '''    rows = plan.get("data", {}).get("json_rows") or []
    if plan.get("data", {}).get("selection_strategy") == "random":
        data = user.rng.choice(rows)
    else:
        data = rows[user.data_index % len(rows)]
        user.data_index += 1'''
    else:
        data_selection = "    data = {}"
    return f'''def execute_plan(user, plan: dict[str, Any]) -> None:
    user.sequence += 1
{data_selection}
    user.variables = {{**user.base_variables, **data}}
    user.outputs = {{}}
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
    )'''


def _endpoint_runner_source(capabilities) -> str:
    if capabilities.uses_sse:
        execution = '''    status_codes = next(
        (rule.get("status_codes") or [] for rule in plan.get("success_rules") or [] if rule.get("kind") == "status_code"),
        [],
    )
    assertions = [{"type": "status_code", "expected": status_codes[0]}] if len(status_codes) == 1 else []
    _execute_sse(user, request, path, {"id": "endpoint", "name": request["name"], "assertions": assertions})'''
    else:
        execution = '''    with user.client.request(
        method=request["method"], url=path, name=request["name"], params=request.get("query_parameters") or {},
        **_payload_kwargs(request), timeout=request["timeout_seconds"], catch_response=True,
    ) as response:
        try:
            _assert_endpoint_success(response, plan.get("success_rules") or [])
        except Exception as exc:
            response.failure(str(exc))
            return
        response.success()'''
    if capabilities.uses_data_rows:
        data_selection = '''    rows = plan.get("data", {}).get("json_rows") or []
    if plan.get("data", {}).get("selection_strategy") == "random":
        data = user.rng.choice(rows)
    else:
        data = rows[user.data_index % len(rows)]
        user.data_index += 1'''
    else:
        data_selection = "    data = {}"
    return f'''def execute_endpoint(user, plan: dict[str, Any]) -> None:
    user.sequence += 1
{data_selection}
    request = _resolve(plan["request"], user.sequence, data, user.rng)
    path = request["path"]
    for key, value in request.get("path_parameters", {{}}).items():
        path = path.replace("{{" + str(key) + "}}", str(value))
{execution}'''


def _load_shape_source(capabilities) -> str:
    breaker = ""
    state = ""
    if capabilities.uses_circuit_breaker:
        state = '''    next_breaker_check = 0.0
    previous_requests = 0
    previous_failures = 0
    failed_windows = 0
'''
        breaker = '''        breaker = self.plan.get("circuit_breaker") or {}
        if run_time >= self.next_breaker_check:
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
'''
    return f'''class PerformanceLoadShape(LoadTestShape):
{state}    def tick(self):
        run_time = self.get_run_time()
{breaker}        elapsed = 0
        previous_users = 0
        for stage in self.plan.get("load", {{}}).get("stages", []):
            ramp_seconds = max(1, math.ceil(abs(stage["target_users"] - previous_users) / stage["spawn_rate"]))
            elapsed += ramp_seconds + stage["hold_seconds"]
            if run_time < elapsed:
                return stage["target_users"], stage["spawn_rate"]
            previous_users = stage["target_users"]
        return None'''


def compile_locustfile(plan: LocustScriptPlan) -> str:
    capabilities = analyze_capabilities(plan)
    source = source_for_blocks(resolve_blocks(_requested_blocks(capabilities)))
    runner_sources = [] if capabilities.uses_dynamic_values else [_static_value_resolver_source()]
    if capabilities.target_type == "scenario":
        runner_sources.extend([_scenario_step_runner_source(capabilities), _scenario_plan_runner_source(capabilities)])
    else:
        runner_sources.append(_endpoint_runner_source(capabilities))
    if capabilities.uses_load_shape:
        runner_sources.append(_load_shape_source(capabilities))
    source = source + "\n\n" + "\n\n".join(runner_sources)
    plan_source = pformat(runtime_plan(plan), sort_dicts=True, width=100)
    base = "ScenarioUser" if capabilities.target_type == "scenario" else "EndpointUser"
    shape = "\n\nPerformanceLoadShape.plan = PLAN" if capabilities.uses_load_shape else ""
    generated = f'''PLAN = {plan_source}


class PerformanceUser({base}):
    plan = PLAN
    wait_time = between({plan.load.wait_time_min_seconds!r}, {plan.load.wait_time_max_seconds!r})

    @task
    def execute_target(self):
        self.run_plan()
{shape}
'''
    return "\n\n".join((source, generated.rstrip(), standalone_runtime_support_source(enable_sse=capabilities.uses_sse).strip())) + "\n"
