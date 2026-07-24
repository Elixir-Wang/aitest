import copy
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from support.assertions import assert_response_assertions


def run_scenario(api_client, scenario: dict) -> dict:
    outputs = {}
    failures = []
    step_results = []
    stopped = False
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    for step in scenario.get("steps", []):
        policy = step.get("on_failure", "stop")
        step_type = step.get("step_type", "api_request")
        record = _new_step_result(step, step_type)
        if stopped and policy != "always_run":
            record["status"] = "skipped"
            record["skip_reason"] = "前序步骤失败，执行链路已停止。"
            step_results.append(record)
            continue
        step_clock = time.perf_counter()
        try:
            config = step.get("control_config") or {}
            if step_type == "assign":
                outputs[step["id"]] = {
                    config["name"]: _resolve_source(config.get("source", {}), scenario, outputs)
                }
                record["inputs"] = {"source": config.get("source", {})}
            elif step_type == "condition":
                matched = _evaluate_condition(config, scenario, outputs)
                outputs[step["id"]] = {"matched": matched}
                record["inputs"] = {"source": config.get("source", {}), "expected": config.get("expected")}
                if not matched:
                    record["status"] = "skipped"
                    record["skip_reason"] = "条件不满足。"
                    continue
            elif step_type == "wait":
                time.sleep(config.get("duration_ms", 0) / 1000)
                outputs[step["id"]] = {}
                record["inputs"] = {"duration_ms": config.get("duration_ms", 0)}
            elif step_type == "poll":
                response, state = _run_poll(api_client, step, scenario, outputs, record["attempts"])
                record["request"] = state["request"]
                record["inputs"] = state["test_data"]
                record["response"] = _serialize_response(response)
                outputs[step["id"]] = _extract_outputs(response, step.get("extractors", []))
            else:
                response, state = _run_api_request(api_client, step, scenario, outputs)
                record["request"] = state["request"]
                record["inputs"] = state["test_data"]
                record["response"] = _serialize_response(response)
                record["attempts"].append({"status": "passed", "response": record["response"]})
                outputs[step["id"]] = _extract_outputs(response, step.get("extractors", []))
            record["outputs"] = outputs.get(step["id"], {})
            if record["status"] != "skipped":
                record["status"] = "passed"
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = str(exc)
            failures.append(f"{step.get('name') or step.get('id')}: {exc}")
            if policy == "stop":
                stopped = True
        finally:
            record["duration_ms"] = round((time.perf_counter() - step_clock) * 1000, 2)
            record["request"] = _redact(record["request"])
            record["response"] = _redact(record["response"])
            record["inputs"] = _redact(record["inputs"])
            record["outputs"] = _redact(record["outputs"])
            record["attempts"] = _redact(record["attempts"])
            step_results.append(record)
    finished_at = datetime.now(timezone.utc)
    result = {
        "scenario_id": scenario.get("id", ""),
        "status": "failed" if failures else "passed",
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
        "duration_ms": round((time.perf_counter() - started_clock) * 1000, 2),
        "steps": step_results,
    }
    _write_scenario_result(result)
    if failures:
        raise AssertionError("Scenario failed:\n" + "\n".join(failures))
    return outputs


def _run_api_request(api_client, step: dict, scenario: dict, outputs: dict):
    state, case = _build_request_state(step, scenario, outputs)
    response = api_client.request(state["request"], state["test_data"])
    assert_response_assertions(response, step.get("assertions") or case.get("assertions", []))
    return response, state


def _run_poll(api_client, step: dict, scenario: dict, outputs: dict, attempts: list):
    config = step.get("control_config") or {}
    deadline = time.monotonic() + config.get("timeout_ms", 0) / 1000
    while True:
        state = None
        try:
            response, state = _run_api_request(api_client, step, scenario, outputs)
            attempts.append({"status": "passed", "request": state["request"], "response": _serialize_response(response)})
            return response, state
        except AssertionError as exc:
            attempts.append({
                "status": "failed",
                "request": state["request"] if state else {},
                "error": str(exc),
            })
            if time.monotonic() >= deadline:
                raise
            time.sleep(config.get("interval_ms", 0) / 1000)


def _new_step_result(step: dict, step_type: str) -> dict:
    return {
        "step_id": step.get("id", ""),
        "name": step.get("name", ""),
        "step_type": step_type,
        "status": "pending",
        "duration_ms": 0,
        "request": {},
        "response": {},
        "inputs": {},
        "outputs": {},
        "assertions": copy.deepcopy(step.get("assertions", [])),
        "attempts": [],
        "error": "",
        "skip_reason": "",
    }


def _serialize_response(response) -> dict:
    try:
        body = response.json()
    except Exception:
        content = getattr(response, "content", b"")
        body = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
    return {
        "status_code": getattr(response, "status_code", None),
        "headers": dict(getattr(response, "headers", {}) or {}),
        "body": body,
    }


def _write_scenario_result(result: dict) -> None:
    target = os.environ.get("API_SCENARIO_RESULT_PATH", "")
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_redact(result), ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _redact(value):
    sensitive = ("authorization", "cookie", "token", "password", "secret", "api_key", "apikey")
    if isinstance(value, dict):
        return {
            key: "***" if any(part in str(key).lower() for part in sensitive) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _build_request_state(step: dict, scenario: dict, outputs: dict):
    case = step.get("case") or {}
    endpoint = step.get("endpoint") or {}
    request_overrides = copy.deepcopy(step.get("request_overrides", {}))
    request_patch = request_overrides.get("request", request_overrides)
    state = {
        "request": _deep_merge(
            {
                "method": endpoint.get("method", case.get("request", {}).get("method", "GET")),
                "path": endpoint.get("path", case.get("request", {}).get("path", "")),
            },
            request_patch,
        ),
        "test_data": copy.deepcopy(request_overrides.get("test_data", case.get("test_data", {}))),
    }
    for binding in step.get("bindings", []):
        _set_pointer(state, binding.get("target", ""), _resolve_source(binding.get("source", {}), scenario, outputs))
    return state, case


def _evaluate_condition(config: dict, scenario: dict, outputs: dict) -> bool:
    actual = _resolve_source(config.get("source", {}), scenario, outputs)
    expected = config.get("expected")
    operator = config.get("operator")
    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "contains":
        return expected in actual
    if operator == "not_contains":
        return expected not in actual
    if operator == "truthy":
        return bool(actual)
    if operator == "falsy":
        return not actual
    if operator == "gt":
        return actual > expected
    if operator == "gte":
        return actual >= expected
    if operator == "lt":
        return actual < expected
    if operator == "lte":
        return actual <= expected
    raise RuntimeError(f"Unsupported condition operator: {operator}")


def _resolve_source(source: dict, scenario: dict, outputs: dict):
    source_type = source.get("type")
    if source_type == "literal":
        return source.get("value")
    if source_type == "environment":
        name = str(source.get("name") or "")
        value = os.environ.get(f"API_VAR_{name.upper()}")
        if value is None:
            raise RuntimeError(f"Required environment variable is missing: {name}")
        return value
    if source_type == "scenario":
        name = str(source.get("name") or "")
        if name not in scenario.get("variables", {}):
            raise RuntimeError(f"Required scenario variable is missing: {name}")
        return scenario["variables"][name]
    if source_type == "step_output":
        step_id = str(source.get("step_id") or "")
        variable = str(source.get("variable") or "")
        try:
            return outputs[step_id][variable]
        except KeyError as exc:
            raise RuntimeError(f"Step output is unavailable: {step_id}.{variable}") from exc
    raise RuntimeError(f"Unsupported binding source: {source_type}")


def _set_pointer(document: dict, pointer: str, value) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.strip("/").split("/") if part]
    if not parts:
        raise RuntimeError("Binding target is required.")
    current = document
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def _extract_outputs(response, extractors: list[dict]) -> dict:
    values = {}
    for extractor in extractors:
        source = extractor.get("source", "response.body")
        if source == "response.status":
            value = response.status_code
        elif source == "response.header":
            value = response.headers.get(extractor.get("expression", ""))
        else:
            value = _read_path(response.json(), extractor.get("expression") or extractor.get("path", ""))
        if value is None and extractor.get("required", True):
            raise AssertionError(f"Required extraction failed: {extractor.get('name')}")
        values[extractor.get("name", "")] = value
    return values


def _read_path(data, path: str):
    if not path or path == "$":
        return data
    current = data
    for part in path.removeprefix("$.").split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _deep_merge(base: dict, overrides: dict) -> dict:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base
