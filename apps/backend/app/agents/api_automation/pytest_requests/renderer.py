"""Deterministic renderer for validated API scenario snapshots."""

from __future__ import annotations

import json
from textwrap import dedent
from typing import Any


RENDERER_VERSION = 1


def render_scenario_files(scenario_key: str, snapshot: dict[str, Any]) -> dict[str, str]:
    scenario_dir = f"scenarios/{scenario_key}"
    return {
        "support/scenario.py": _scenario_py(),
        f"{scenario_dir}/scenario.json": json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        f"{scenario_dir}/scenario.py": _scenario_py(),
        f"{scenario_dir}/test_scenario.py": _test_scenario_py(),
    }


def _test_scenario_py() -> str:
    return dedent(
        """
        import json
        from pathlib import Path

        from scenario import run_scenario


        def test_scenario(api_client):
            scenario = json.loads((Path(__file__).parent / "scenario.json").read_text(encoding="utf-8"))
            run_scenario(api_client, scenario)
        """
    ).lstrip()


def _scenario_py() -> str:
    return dedent(
        r'''
        import copy
        import json
        import os
        import re
        import time
        import uuid
        from datetime import datetime, timezone
        from pathlib import Path
        from urllib.parse import quote

        try:
            from support.assertions import assert_response_assertions
        except ModuleNotFoundError:
            def assert_response_assertions(response, assertions):
                for assertion in assertions:
                    if assertion.get("type") == "status_code":
                        assert response.status_code == assertion["expected"]


        _SENSITIVE = re.compile(r"(?:authorization|cookie|token|secret|password|api[_-]?key)", re.IGNORECASE)


        def run_scenario(api_client, scenario):
            variables = dict(scenario.get("variables") or {})
            outputs = {}
            result_steps = []
            failure = None
            steps = list(scenario.get("steps") or [])
            for step in steps:
                if not step.get("enabled", True):
                    result_steps.append(_step_result(step, "skipped"))
                    continue
                if failure is not None and step.get("on_failure") != "always_run":
                    result_steps.append(_step_result(step, "skipped"))
                    continue
                try:
                    outputs[step.get("id", "")] = _run_step(api_client, step, variables, outputs)
                    result_steps.append(_step_result(step, "passed", outputs[step.get("id", "")]))
                except Exception as exc:
                    result_steps.append(_step_result(step, "failed", error=str(exc)))
                    if failure is None:
                        failure = exc
            _write_result(scenario, result_steps, "failed" if failure else "passed")
            if failure:
                raise failure
            return outputs


        def _run_step(api_client, step, variables, outputs):
            step_type = step.get("step_type") or step.get("type") or "api_request"
            if step_type == "assign":
                config = step.get("control_config") or {}
                value = _resolve_source(config.get("source") or {}, variables, outputs)
                return {str(config.get("name") or "value"): value}
            if step_type == "condition":
                config = step.get("control_config") or {}
                actual = _resolve_source(config.get("source") or {}, variables, outputs)
                if not _condition(actual, config.get("operator"), config.get("expected")):
                    raise AssertionError("场景条件不满足")
                return {}
            if step_type == "wait":
                time.sleep(float((step.get("control_config") or {}).get("duration_ms", 0)) / 1000)
                return {}
            if step_type == "poll":
                return _poll(api_client, step, variables, outputs)
            return _request(api_client, step, variables, outputs)


        def _poll(api_client, step, variables, outputs):
            config = step.get("control_config") or {}
            interval = float(config.get("interval_ms", 1000)) / 1000
            timeout = float(config.get("timeout_ms", 30000)) / 1000
            deadline = time.monotonic() + timeout
            while True:
                try:
                    return _request(api_client, step, variables, outputs)
                except AssertionError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(interval)


        def _request(api_client, step, variables, outputs):
            case = copy.deepcopy(step.get("case") or {})
            endpoint = step.get("endpoint") or {}
            request = copy.deepcopy(case.get("request") or {"method": endpoint.get("method"), "path": endpoint.get("path")})
            request.setdefault("method", endpoint.get("method", "GET"))
            request.setdefault("path", endpoint.get("path", ""))
            test_data = copy.deepcopy(case.get("test_data") or {})
            overrides = step.get("request_overrides") or {}
            _merge(request, overrides.get("request") or {})
            _merge(test_data, overrides.get("test_data") or {})
            for binding in step.get("bindings") or []:
                value = _resolve_source(binding.get("source") or {}, variables, outputs)
                value = _transform(value, binding.get("transform"))
                target = str(binding.get("target") or "")
                if target.startswith("/request/"):
                    _set_pointer(request, target.removeprefix("/request"), value)
                elif target.startswith("/test_data/"):
                    _set_pointer(test_data, target.removeprefix("/test_data"), value)
            response = api_client.request(request, test_data)
            assert_response_assertions(response, step.get("assertions") or case.get("assertions") or [])
            return _extract(response, step.get("extractors") or [])


        def _resolve_source(source, variables, outputs):
            kind = source.get("type")
            if kind == "literal": return source.get("value")
            if kind == "environment":
                key = str(source.get("key") or source.get("name") or "")
                return os.getenv("API_VAR_" + key.upper(), os.getenv(key, variables.get(key)))
            if kind == "scenario": return variables.get(source.get("name"))
            if kind == "user_input": return os.getenv("API_SCENARIO_INPUT_" + str(source.get("name", "")).upper())
            if kind == "secret":
                key = str(source.get("key", ""))
                normalized = key.upper().replace("-", "_")
                fallback = os.getenv("API_HEADER_" + normalized, os.getenv(key, variables.get(key)))
                if key.lower() == "authorization":
                    fallback = fallback or os.getenv("API_AUTH_BEARER")
                return os.getenv("API_SCENARIO_SECRET_" + normalized, fallback)
            if kind == "step_output": return (outputs.get(source.get("step_id")) or {}).get(source.get("variable"))
            if kind == "generated":
                generator = source.get("generator")
                if generator == "uuid4": return str(uuid.uuid4())
                if generator == "timestamp_ms": return int(time.time() * 1000)
                if generator == "timestamp_iso": return datetime.now(timezone.utc).isoformat()
                if generator == "random_string": return uuid.uuid4().hex[:int(source.get("length", 0))]
            raise ValueError("不支持的场景变量来源: " + str(kind))


        def _extract(response, extractors):
            result = {}
            for extractor in extractors:
                source = extractor.get("source") or "response.body"
                path = extractor.get("path") or extractor.get("expression") or ""
                if source in ("response.body", "json_body"):
                    result[extractor["name"]] = _json_path(response.json(), path)
                elif source in ("response.header", "header"):
                    result[extractor["name"]] = _header(response.headers, path)
                elif source in ("response.status", "status_code"):
                    result[extractor["name"]] = response.status_code
                elif source == "text_regex":
                    match = re.search(path, getattr(response, "text", ""))
                    result[extractor["name"]] = match.group(1) if match else None
                else:
                    raise ValueError("当前执行器不支持提取器来源: " + str(source))
                if extractor.get("required", True) and result[extractor["name"]] is None:
                    raise AssertionError("未提取到必填变量: " + extractor["name"])
            return result


        def _json_path(value, path):
            if not path or path == "$": return value
            tokens = path.removeprefix("$").strip(".").replace("[", ".").replace("]", "").split(".")
            current = value
            for token in (token for token in tokens if token):
                if isinstance(current, dict): current = current.get(token)
                elif isinstance(current, list) and token.isdigit() and int(token) < len(current): current = current[int(token)]
                else: return None
            return current


        def _header(headers, name):
            for key, value in dict(headers or {}).items():
                if key.lower() == name.lstrip("/").lower(): return value
            return None


        def _set_pointer(target, pointer, value):
            parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.strip("/").split("/") if part]
            current = target
            for part in parts[:-1]: current = current.setdefault(part, {})
            if parts: current[parts[-1]] = value


        def _merge(target, updates):
            for key, value in updates.items():
                if isinstance(value, dict) and isinstance(target.get(key), dict): _merge(target[key], value)
                else: target[key] = value


        def _transform(value, transform):
            if transform == "string": return str(value)
            if transform == "integer": return int(value)
            if transform == "number": return float(value)
            if transform == "boolean": return bool(value)
            if transform == "json_encode": return json.dumps(value, ensure_ascii=False)
            if transform == "url_encode": return quote(str(value), safe="")
            return value


        def _condition(actual, operator, expected):
            return {"equals": actual == expected, "not_equals": actual != expected, "contains": expected in actual if actual is not None else False, "not_contains": expected not in actual if actual is not None else True, "truthy": bool(actual), "falsy": not bool(actual), "gt": actual > expected, "gte": actual >= expected, "lt": actual < expected, "lte": actual <= expected}.get(operator, False)


        def _step_result(step, status, outputs=None, error=""):
            return {"step_id": step.get("id", ""), "name": step.get("name", ""), "status": status, "outputs": _redact(outputs or {}), "error": _redact(error)}


        def _redact(value):
            if isinstance(value, dict): return {key: ("******" if _SENSITIVE.search(str(key)) else _redact(item)) for key, item in value.items()}
            if isinstance(value, list): return [_redact(item) for item in value]
            if isinstance(value, str) and _SENSITIVE.search(value): return "******"
            return value


        def _write_result(scenario, steps, status):
            path = os.getenv("API_SCENARIO_RESULT_PATH")
            if path: Path(path).write_text(json.dumps({"scenario_id": scenario.get("id", ""), "status": status, "steps": steps}, ensure_ascii=False), encoding="utf-8")
        '''
    ).lstrip()
