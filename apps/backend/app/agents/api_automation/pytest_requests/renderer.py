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
            return _request_with_lifecycle(api_client, step, variables, outputs)


        def _request_with_lifecycle(api_client, step, variables, outputs):
            config = step.get("control_config") or {}
            pre_request = config.get("pre_request") or {}
            post_response = config.get("post_response") or {}
            _apply_variable_actions(pre_request.get("actions") or [], variables, variables, outputs)
            retries = max(0, int(config.get("retries", 0) or 0))
            retry_interval = max(0, float(config.get("retry_interval_ms", 1000) or 0)) / 1000
            for attempt in range(retries + 1):
                try:
                    result = _request(api_client, step, variables, outputs)
                    _apply_variable_actions(post_response.get("actions") or [], result, variables, outputs)
                    return result
                except Exception:
                    if attempt >= retries:
                        raise
                    if retry_interval:
                        time.sleep(retry_interval)


        def _apply_variable_actions(actions, target, variables, outputs):
            for action in actions:
                if action.get("type") != "set_variable":
                    raise ValueError("不支持的生命周期变量动作: " + str(action.get("type")))
                name = str(action.get("name") or "").strip()
                if not name:
                    raise ValueError("生命周期变量动作缺少变量名")
                target[name] = _resolve_source(action.get("source") or {}, variables, outputs)


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
            response = _dispatch_request(api_client, request, test_data, endpoint)
            assert_response_assertions(response, step.get("assertions") or case.get("assertions") or [])
            return _extract(response, step.get("extractors") or [])


        def _dispatch_request(api_client, request, test_data, endpoint):
            multipart = request.get("multipart_form")
            form = request.get("form")
            session = getattr(api_client, "session", None)
            base_url = str(getattr(api_client, "base_url", "") or "").rstrip("/")
            if session is None or not base_url or (multipart is None and form is None):
                return api_client.request(request, test_data)
            method = str(request.get("method") or endpoint.get("method") or "GET").upper()
            path = _expand_request_path(str(request.get("path") or endpoint.get("path") or ""), request, test_data)
            headers = dict(_expand_runtime_value(request.get("headers") or {}))
            query = _expand_runtime_value(request.get("query") or {})
            cookies = _expand_runtime_value(request.get("cookies") or {})
            timeout = getattr(api_client, "timeout", 30)
            if multipart is not None:
                _pop_header(headers, "Content-Type")
                parts, handles = _multipart_parts(multipart, request.get("files") or {})
                try:
                    return session.request(
                        method,
                        f"{base_url}{path}",
                        params=query or None,
                        headers=headers or None,
                        cookies=cookies or None,
                        files=parts or None,
                        timeout=timeout,
                        stream=_is_sse_endpoint(endpoint),
                    )
                finally:
                    for handle in handles:
                        handle.close()
            return session.request(
                method,
                f"{base_url}{path}",
                params=query or None,
                headers=headers or None,
                cookies=cookies or None,
                data=_expand_runtime_value(form),
                timeout=timeout,
                stream=_is_sse_endpoint(endpoint),
            )


        def _expand_request_path(path, request, test_data):
            values = {}
            for source in (test_data or {}, request.get("path_params") or {}):
                for key, value in source.items():
                    values[key] = value.get("value") if isinstance(value, dict) and "value" in value else value
            expanded = _expand_runtime_value(path)
            for key, value in values.items():
                expanded = expanded.replace("{" + str(key) + "}", quote(str(_expand_runtime_value(value)), safe=""))
            return expanded


        def _expand_runtime_value(value):
            if isinstance(value, dict): return {key: _expand_runtime_value(item) for key, item in value.items()}
            if isinstance(value, list): return [_expand_runtime_value(item) for item in value]
            if not isinstance(value, str): return value
            return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", lambda match: os.getenv(match.group(1), match.group(0)), value)


        def _multipart_parts(form, file_specs):
            parts = []
            handles = []
            for field, value in _expand_runtime_value(form).items():
                serialized = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
                parts.append((field, (None, serialized)))
            try:
                for field, raw_specs in file_specs.items():
                    specs = raw_specs if isinstance(raw_specs, list) else [raw_specs]
                    for raw_spec in specs:
                        spec = raw_spec if isinstance(raw_spec, dict) else {"path": raw_spec}
                        file_path = Path(str(_expand_runtime_value(spec.get("path", "")))).expanduser()
                        if not file_path.is_file():
                            raise RuntimeError(f"Upload file does not exist for field {field}: {file_path}")
                        handle = file_path.open("rb")
                        handles.append(handle)
                        filename = str(_expand_runtime_value(spec.get("filename") or file_path.name))
                        content_type = str(_expand_runtime_value(spec.get("content_type") or "application/octet-stream"))
                        parts.append((field, (filename, handle, content_type)))
                return parts, handles
            except Exception:
                for handle in handles:
                    handle.close()
                raise


        def _pop_header(headers, name):
            for key in list(headers):
                if str(key).lower() == name.lower():
                    headers.pop(key, None)


        def _is_sse_endpoint(endpoint):
            for response in (endpoint.get("responses") or {}).values():
                content = response.get("content") if isinstance(response, dict) else {}
                if any("text/event-stream" in str(content_type).lower() for content_type in (content or {})):
                    return True
            return False


        def _resolve_source(source, variables, outputs):
            kind = source.get("type")
            if kind == "literal": return source.get("value")
            if kind == "object": return {key: _resolve_source(item, variables, outputs) for key, item in (source.get("properties") or {}).items()}
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
            sse_events = _sse_events(response) if any(
                extractor.get("source") == "sse_event_json" for extractor in extractors
            ) else []
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
                elif source == "sse_event_json":
                    result[extractor["name"]] = _extract_sse_event_json(sse_events, extractor, path)
                else:
                    raise ValueError("当前执行器不支持提取器来源: " + str(source))
                missing = result[extractor["name"]] is None or (
                    source == "sse_event_json"
                    and extractor.get("occurrence") == "all"
                    and result[extractor["name"]] == []
                )
                if extractor.get("required", True) and missing:
                    raise AssertionError("未提取到必填变量: " + extractor["name"])
            return result


        def _sse_events(response):
            events = []
            event_name = "message"
            data_lines = []

            def flush():
                nonlocal event_name, data_lines
                if data_lines:
                    events.append({"event": event_name or "message", "data": "\n".join(data_lines)})
                event_name = "message"
                data_lines = []

            for raw_line in response.iter_lines(decode_unicode=True):
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else str(raw_line)
                if not line:
                    flush()
                elif line.startswith(":"):
                    continue
                elif line.startswith("event:"):
                    event_name = line[6:].lstrip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
            flush()
            return events


        def _extract_sse_event_json(events, extractor, path):
            expected_event = str(extractor.get("event") or "message")
            occurrence = str(extractor.get("occurrence") or "first")
            values = []
            for event in events:
                if event["event"] != expected_event:
                    continue
                try:
                    payload = json.loads(event["data"])
                except (TypeError, json.JSONDecodeError):
                    continue
                value = _json_path(payload, path)
                if value is not None:
                    values.append(value)
            if occurrence == "all":
                return values
            if occurrence == "last":
                return values[-1] if values else None
            if occurrence != "first":
                raise ValueError("不支持的 SSE 提取 occurrence: " + occurrence)
            return values[0] if values else None


        def _json_path(value, path):
            if not path or path == "$": return value
            if path.startswith("/"):
                tokens = [part.replace("~1", "/").replace("~0", "~") for part in path.strip("/").split("/") if part]
            else:
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
