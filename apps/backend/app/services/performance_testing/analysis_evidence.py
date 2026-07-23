import csv
import json
from pathlib import Path
from typing import Any

from app.core.db import connect
from app.repositories import api_automation_repo, performance_script_repo, performance_test_repo
from app.services.performance_testing import run_repo


SENSITIVE_NAMES = {
    "authorization",
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "cybertron-robot-key",
    "cybertron-robot-token",
}
DEFAULT_TEXT_LIMIT = 4000


def redact_sensitive(value: Any, *, key: str = "", max_text_length: int = DEFAULT_TEXT_LIMIT) -> Any:
    normalized_key = key.strip().lower().replace("-", "_")
    if normalized_key in {name.replace("-", "_") for name in SENSITIVE_NAMES} or any(
        marker in normalized_key for marker in ("password", "secret", "token")
    ):
        return "***"
    if isinstance(value, dict):
        return {
            str(item_key): redact_sensitive(item, key=str(item_key), max_text_length=max_text_length)
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item, max_text_length=max_text_length) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item, max_text_length=max_text_length) for item in value]
    if isinstance(value, bytes):
        return {"type": "binary", "length": len(value)}
    if isinstance(value, str) and len(value) > max_text_length:
        return f"{value[:max_text_length]}…[truncated]"
    return value


def collect_performance_evidence(project_id: str, run_id: str) -> dict[str, Any]:
    with connect() as db:
        run = run_repo.get_run(db, run_id)
        if not run or run["project_id"] != project_id:
            raise LookupError("性能测试运行不存在")
        performance_test_row = performance_test_repo.find_performance_test(db, run["performance_test_id"])
        script_row = performance_script_repo.find_script(db, run["script_id"])
        endpoint_row = None
        if performance_test_row and performance_test_row["endpoint_id"]:
            endpoint_row = api_automation_repo.find_endpoint(db, performance_test_row["endpoint_id"])
        stats = [_stat_payload(row) for row in run_repo.list_stats(db, run_id)]
        failures = [dict(row) for row in run_repo.list_failures(db, run_id)]
        exceptions = [dict(row) for row in run_repo.list_exceptions(db, run_id)]
        events = [_event_payload(row) for row in run_repo.list_events(db, run_id)]
        history = [
            _run_summary(row)
            for row in run_repo.list_runs(db, project_id, run["performance_test_id"])
            if row["id"] != run_id
        ][:5]

    performance_test = performance_test_repo.serialize_performance_test(performance_test_row) if performance_test_row else {}
    script = performance_script_repo.serialize_script(script_row) if script_row else {}
    endpoint = _endpoint_payload(endpoint_row)
    report_directory = Path(str(run["report_directory"] or "")) if run["report_directory"] else None
    artifacts, missing_evidence = _collect_artifacts(report_directory)
    if not endpoint:
        missing_evidence.append("openapi_endpoint")
    if not failures:
        missing_evidence.append("performance_failures")

    return redact_sensitive(
        {
            "run": _run_summary(run),
            "summary": _json_value(run["latest_summary_json"], {}),
            "stats": stats,
            "failures": failures,
            "exceptions": exceptions,
            "events": events,
            "performance_test": performance_test,
            "script": script,
            "endpoint": endpoint,
            "runtime_config": _json_value(run["runtime_config_json"], {}),
            "historical_runs": history,
            "artifacts": artifacts,
            "missing_evidence": list(dict.fromkeys(missing_evidence)),
        }
    )


def has_analyzable_evidence(bundle: dict[str, Any]) -> bool:
    summary = bundle.get("summary") if isinstance(bundle.get("summary"), dict) else {}
    return bool(
        int(summary.get("request_count") or 0)
        or bundle.get("failures")
        or bundle.get("exceptions")
        or bundle.get("events")
        or bundle.get("artifacts", {}).get("locust_events")
    )


def _collect_artifacts(report_directory: Path | None) -> tuple[dict[str, Any], list[str]]:
    artifacts: dict[str, Any] = {}
    missing: list[str] = []
    expected = {
        "locust_events": "locust-events.jsonl",
        "result_failures": "result_failures.csv",
        "result_exceptions": "result_exceptions.csv",
        "generated_locustfile": "generated_locustfile.py",
        "effective_locustfile": "locustfile.py",
    }
    if report_directory is None or not report_directory.is_dir():
        return artifacts, list(expected.values())
    for key, file_name in expected.items():
        path = report_directory / file_name
        if not path.is_file():
            missing.append(file_name)
            continue
        if path.suffix == ".jsonl":
            artifacts[key] = _read_jsonl(path)
        elif path.suffix == ".csv":
            artifacts[key] = _read_csv(path)
        else:
            artifacts[key] = path.read_text(encoding="utf-8", errors="replace")[:12000]
    return artifacts, missing


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:200]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))[:200]


def _endpoint_payload(row) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "id": row["id"],
        "method": row["method"],
        "path": row["path"],
        "summary": row["summary"],
        "description": row["description"],
        "parameters": _json_value(row["parameters_json"], []),
        "request_body": _json_value(row["request_body_json"], {}),
        "responses": _json_value(row["responses_json"], {}),
    }


def _run_summary(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "performance_test_id": row["performance_test_id"],
        "script_id": row["script_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "trace_id": row["trace_id"],
    }


def _stat_payload(row) -> dict[str, Any]:
    payload = dict(row)
    payload.update(_json_value(payload.pop("stats_json", "{}"), {}))
    return payload


def _event_payload(row) -> dict[str, Any]:
    payload = dict(row)
    payload["payload"] = _json_value(payload.pop("payload_json", "{}"), {})
    return payload


def _json_value(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default

