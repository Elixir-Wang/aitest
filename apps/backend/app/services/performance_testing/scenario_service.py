from __future__ import annotations

import hashlib
import json
import math
import secrets
import sqlite3
from typing import Any

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import api_automation_repo, performance_scenario_repo, project_repo
from app.schemas.performance_scenario import PerformanceScenarioCreateIn, PerformanceScenarioUpdateIn
from app.services.performance_testing.service import SENSITIVE_HEADER_NAMES


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _require_visible_project(db, project_id: str, actor) -> None:
    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "NOT_FOUND", "项目不存在。")
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return
    if project["name"] != actor["project_scope"]:
        raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _validate_payload(db, project_id: str, payload: PerformanceScenarioCreateIn) -> None:
    step = payload.scenario_definition.personas[0].steps[0]
    endpoint = api_automation_repo.find_endpoint(db, step.endpoint_id)
    if not endpoint or endpoint["project_id"] != project_id:
        raise api_error(422, "PERFORMANCE_ENDPOINT_INVALID", "接口必须属于当前项目。")
    environment = api_automation_repo.find_api_environment(db, payload.api_environment_id)
    if not environment or environment["project_id"] != project_id:
        raise api_error(422, "PERFORMANCE_ENVIRONMENT_INVALID", "环境必须属于当前项目。")
    sensitive = sorted(key for key in step.request.headers if key.lower() in SENSITIVE_HEADER_NAMES)
    if sensitive:
        raise api_error(422, "PERFORMANCE_SENSITIVE_HEADER", f"敏感 Header 必须由环境凭据注入：{', '.join(sensitive)}")
    if payload.data_source.source == "csv" and not (payload.data_source.dataset_id or payload.data_source.rows):
        raise api_error(422, "PERFORMANCE_DATASET_REQUIRED", "CSV 数据源必须提供 dataset_id 或已解析的数据行。")


def _serialize(row) -> dict[str, Any]:
    return performance_scenario_repo.serialize_scenario(row)


def create_scenario(project_id: str, payload: PerformanceScenarioCreateIn, actor) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _validate_payload(db, project_id, payload)
        scenario_id = f"perfscenario-{secrets.token_hex(8)}"
        try:
            performance_scenario_repo.create_scenario(
                db, scenario_id=scenario_id, project_id=project_id, name=payload.name.strip(),
                description=payload.description.strip(), api_environment_id=payload.api_environment_id,
                scenario_definition=payload.scenario_definition.model_dump(mode="json"),
                load_profile=payload.load_profile.model_dump(mode="json"),
                data_source=payload.data_source.model_dump(mode="json"),
                quality_gate=payload.quality_gate.model_dump(mode="json", exclude_none=True),
                safety_policy=payload.safety_policy.model_dump(mode="json"), created_by=str(actor["id"]),
            )
        except sqlite3.IntegrityError as exc:
            raise api_error(409, "PERFORMANCE_SCENARIO_NAME_CONFLICT", "当前项目已存在同名性能场景。") from exc
        return _serialize(performance_scenario_repo.get_scenario(db, scenario_id))


def list_scenarios(project_id: str, actor) -> list[dict[str, Any]]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        return [_serialize(row) for row in performance_scenario_repo.list_scenarios(db, project_id)]


def get_scenario(project_id: str, scenario_id: str, actor) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = performance_scenario_repo.get_scenario(db, scenario_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "PERFORMANCE_SCENARIO_NOT_FOUND", "性能场景不存在。")
        return _serialize(row)


def update_scenario(project_id: str, scenario_id: str, payload: PerformanceScenarioUpdateIn, actor) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = performance_scenario_repo.get_scenario(db, scenario_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "PERFORMANCE_SCENARIO_NOT_FOUND", "性能场景不存在。")
        _validate_payload(db, project_id, payload)
        try:
            performance_scenario_repo.update_scenario(
                db, scenario_id, name=payload.name.strip(), description=payload.description.strip(),
                api_environment_id=payload.api_environment_id,
                scenario_definition=payload.scenario_definition.model_dump(mode="json"),
                load_profile=payload.load_profile.model_dump(mode="json"),
                data_source=payload.data_source.model_dump(mode="json"),
                quality_gate=payload.quality_gate.model_dump(mode="json", exclude_none=True),
                safety_policy=payload.safety_policy.model_dump(mode="json"),
            )
        except sqlite3.IntegrityError as exc:
            raise api_error(409, "PERFORMANCE_SCENARIO_NAME_CONFLICT", "当前项目已存在同名性能场景。") from exc
        return _serialize(performance_scenario_repo.get_scenario(db, scenario_id))


def delete_scenario(project_id: str, scenario_id: str, actor) -> None:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = performance_scenario_repo.get_scenario(db, scenario_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "PERFORMANCE_SCENARIO_NOT_FOUND", "性能场景不存在。")
        performance_scenario_repo.delete_scenario(db, scenario_id)


def execution_preview(load_profile: dict[str, Any]) -> dict[str, Any]:
    if load_profile["mode"] == "fixed":
        ramp = math.ceil(load_profile["target_users"] / load_profile["spawn_rate"])
        return {
            "peak_users": load_profile["target_users"],
            "total_run_seconds": ramp + load_profile["warmup_seconds"] + load_profile["measurement_seconds"],
            "measurement_seconds": load_profile["measurement_seconds"],
            "stages": [{
                "name": "fixed",
                "ramp_seconds": ramp,
                "hold_seconds": load_profile["warmup_seconds"] + load_profile["measurement_seconds"],
                "record_metrics": True,
            }],
        }
    previous = 0
    stages = []
    for stage in load_profile["stages"]:
        ramp = math.ceil(abs(stage["target_users"] - previous) / stage["spawn_rate"])
        stages.append({**stage, "ramp_seconds": ramp})
        previous = stage["target_users"]
    return {
        "peak_users": max(stage["target_users"] for stage in load_profile["stages"]),
        "total_run_seconds": sum(stage["ramp_seconds"] + stage["hold_seconds"] for stage in stages),
        "measurement_seconds": sum(stage["ramp_seconds"] + stage["hold_seconds"] for stage in stages if stage["record_metrics"]),
        "stages": stages,
    }


def create_run(project_id: str, scenario_id: str, actor) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = performance_scenario_repo.get_scenario(db, scenario_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "PERFORMANCE_SCENARIO_NOT_FOUND", "性能场景不存在。")
        scenario = _serialize(row)
        load_preview = execution_preview(scenario["load_profile"])
        snapshot = {
            "scenario": scenario,
            "execution_preview": load_preview,
            "data_hash": hashlib.sha256(_canonical(scenario["data_source"]).encode()).hexdigest(),
            "template_version": "managed-v1",
        }
        snapshot["snapshot_hash"] = hashlib.sha256(_canonical(snapshot).encode()).hexdigest()
        run_id = f"perfrun-{secrets.token_hex(8)}"
        db.execute("""INSERT INTO performance_runs (id, project_id, scenario_id, run_snapshot_json, created_by)
                      VALUES (?, ?, ?, ?, ?)""", (run_id, project_id, scenario_id, _canonical(snapshot), str(actor["id"])))
        return {"id": run_id, "process_status": "created", "quality_status": "not_evaluated", "run_snapshot": snapshot, "execution_preview": load_preview}


def get_run(project_id: str, run_id: str, actor) -> dict[str, Any]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = db.execute("SELECT * FROM performance_runs WHERE id = ? AND project_id = ?", (run_id, project_id)).fetchone()
        if not row:
            raise api_error(404, "PERFORMANCE_RUN_NOT_FOUND", "性能运行不存在。")
        gate_results = db.execute(
            "SELECT metric, operator, threshold, actual, status, reason, evaluated_at FROM performance_run_gate_results WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return {
            "id": row["id"], "project_id": row["project_id"], "scenario_id": row["scenario_id"],
            "process_status": row["process_status"], "stop_reason": row["stop_reason"],
            "quality_status": row["quality_status"], "run_snapshot": json.loads(row["run_snapshot_json"]),
            "latest_summary": json.loads(row["latest_summary_json"]), "script_hash": row["script_hash"],
            "locust_version": row["locust_version"], "exit_code": row["exit_code"],
            "error_code": row["error_code"], "error_message": row["error_message"],
            "created_at": row["created_at"], "started_at": row["started_at"],
            "measurement_started_at": row["measurement_started_at"], "finished_at": row["finished_at"],
            "gate_results": [dict(result) for result in gate_results],
        }


def save_quality_gate_result(run_id: str, gate: dict[str, Any], metrics: dict[str, Any], *, terminal_reason: str = "completed") -> str:
    quality_status, results = evaluate_quality_gate(gate, metrics, terminal_reason=terminal_reason)
    with connect() as db:
        db.execute("DELETE FROM performance_run_gate_results WHERE run_id = ?", (run_id,))
        for result in results:
            db.execute(
                """INSERT INTO performance_run_gate_results (id, run_id, metric, operator, threshold, actual, status, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"perfgate-{secrets.token_hex(8)}", run_id, result["metric"], result["operator"], result["threshold"],
                 result["actual"], result["status"], result["reason"]),
            )
        db.execute("UPDATE performance_runs SET quality_status = ?, latest_summary_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (quality_status, _canonical(metrics), run_id))
    return quality_status


def evaluate_quality_gate(gate: dict[str, Any], metrics: dict[str, Any], *, terminal_reason: str = "completed") -> tuple[str, list[dict[str, Any]]]:
    rules = (
        ("max_fail_ratio", "failure_rate", "<="),
        ("max_average_response_time_ms", "average_response_time_ms", "<="),
        ("max_p95_response_time_ms", "p95_response_time_ms", "<="),
        ("min_average_rps", "requests_per_second", ">="),
        ("min_request_count", "request_count", ">="),
    )
    if not gate:
        return "not_configured", []
    results = []
    if terminal_reason != "completed":
        return "not_evaluated", [
            {"metric": metric, "operator": op, "threshold": gate[key], "actual": metrics.get(metric),
             "status": "not_evaluated", "reason": f"run stopped: {terminal_reason}"}
            for key, metric, op in rules if key in gate
        ]
    for key, metric, op in rules:
        if key not in gate:
            continue
        actual = metrics.get(metric)
        if metrics.get("request_count", 0) == 0 and metric in {"failure_rate", "average_response_time_ms", "p95_response_time_ms"}:
            status, reason = "not_evaluated", "measurement window has no requests"
        else:
            status, reason = ("passed", "") if (actual <= gate[key] if op == "<=" else actual >= gate[key]) else ("failed", "threshold not met")
        results.append({"metric": metric, "operator": op, "threshold": gate[key], "actual": actual, "status": status, "reason": reason})
    return ("failed" if any(item["status"] in {"failed", "not_evaluated"} for item in results) else "passed"), results
