from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.core.storage import resolve_stored_path


ALLOWED_EVIDENCE_TYPES = {"page", "page_yaml", "graph", "summary", "blocker", "snapshot", "trace", "screenshot"}


def build_case_data(source_case, *, automation_case_id: str) -> dict:
    steps = _loads_json(_value(source_case, "steps_json", "[]"), [])
    expected = str(_value(source_case, "expected_result", "")).strip()
    payload = {
        "schema_version": "v1",
        "project_id": _value(source_case, "project_id", ""),
        "automation_case_id": automation_case_id,
        "source_test_case": {
            "id": _value(source_case, "id", ""),
            "title": _value(source_case, "title", ""),
            "status": _value(source_case, "status", ""),
            "updated_at": _value(source_case, "updated_at", ""),
        },
        "preconditions": _lines(_value(source_case, "preconditions", "")),
        "variables": {},
        "steps": [_normalize_step(step, index) for index, step in enumerate(steps, 1)],
        "expected_results": ([{"id": "expected-1", "text": expected}] if expected else []),
    }
    parameters = _extract_step_parameters(steps)
    if parameters:
        payload["parameters"] = parameters
    return payload


def build_evidence_context(*, exploration_run_id: str, artifact_rows: list) -> dict:
    artifacts = []
    for row in artifact_rows:
        artifact_type = str(_value(row, "artifact_type", "")).strip().lower()
        if artifact_type not in ALLOWED_EVIDENCE_TYPES:
            continue
        path = resolve_stored_path(str(_value(row, "file_path", "")))
        if path is None or not path.is_file():
            continue
        content = _read_supported(path)
        if content is None:
            continue
        artifacts.append(
            {
                "type": artifact_type,
                "title": _value(row, "title", ""),
                "path": str(path),
                "content": content,
            }
        )
    return {"exploration_run_id": exploration_run_id, "artifacts": artifacts}


def _read_supported(path: Path):
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _normalize_step(step, index: int) -> dict:
    if isinstance(step, dict):
        normalized = dict(step)
        normalized.setdefault("id", f"step-{index}")
        return normalized
    return {"id": f"step-{index}", "action": str(step)}


def _extract_step_parameters(steps: list) -> dict:
    parameters = {}
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("parameter"), dict):
            continue
        definition = dict(step["parameter"])
        name = str(definition.pop("name", "")).strip()
        if name:
            parameters[name] = definition
    return parameters


def _loads_json(value, default):
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default


def _lines(value) -> list[str]:
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


__all__ = ["build_case_data", "build_evidence_context"]
