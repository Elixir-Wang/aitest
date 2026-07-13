import copy
import os

from support.assertions import assert_response_assertions


def run_scenario(api_client, scenario: dict) -> None:
    outputs = {}
    failures = []
    stopped = False
    for step in scenario.get("steps", []):
        policy = step.get("on_failure", "stop")
        if stopped and policy != "always_run":
            continue
        try:
            case = step["case"]
            state = {
                "request": _deep_merge(copy.deepcopy(case.get("request", {})), step.get("request_overrides", {})),
                "test_data": copy.deepcopy(case.get("test_data", {})),
            }
            for binding in step.get("bindings", []):
                _set_pointer(state, binding.get("target", ""), _resolve_source(binding.get("source", {}), scenario, outputs))
            response = api_client.request(state["request"], state["test_data"])
            assertions = step.get("assertions") or case.get("assertions", [])
            assert_response_assertions(response, assertions)
            outputs[step["id"]] = _extract_outputs(response, step.get("extractors", []))
        except Exception as exc:
            failures.append(f"{step.get('name') or step.get('id')}: {exc}")
            if policy == "stop":
                stopped = True
    if failures:
        raise AssertionError("Scenario failed:\n" + "\n".join(failures))


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
