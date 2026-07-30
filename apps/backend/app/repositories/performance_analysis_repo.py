import json
from sqlite3 import Connection, Row
from typing import Any


ACTIVE_STATUSES = ("collecting", "analyzing")


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def create_analysis_session(
    db: Connection,
    *,
    analysis_id: str,
    project_id: str,
    run_id: str,
    analysis_version: int,
    created_by: str,
    audience: str = "engineer",
) -> None:
    db.execute(
        """
        INSERT INTO performance_analysis_sessions (
          id, project_id, run_id, status, analysis_status, analysis_stage,
          repair_status, analysis_version, audience, created_by
        ) VALUES (?, ?, ?, 'collecting', 'collecting', 'evidence_collection',
          'not_applicable', ?, ?, ?)
        """,
        (analysis_id, project_id, run_id, analysis_version, audience, created_by),
    )


def update_analysis_session(db: Connection, analysis_id: str, **fields: Any) -> None:
    if not fields:
        return
    legacy_status = fields.get("status")
    if legacy_status and "analysis_status" not in fields:
        fields["analysis_status"] = _analysis_status(str(legacy_status))
    if legacy_status in {"waiting_approval", "rejected"} and "repair_status" not in fields:
        proposal = fields.get("proposal") if isinstance(fields.get("proposal"), dict) else {}
        fields["repair_status"] = (
            "rejected"
            if legacy_status == "rejected"
            else ("available" if _applicable_change_ids(proposal) else "not_applicable")
        )
    json_fields = {
        "evidence",
        "missing_evidence",
        "proposal",
        "selected_change_ids",
        "preflight",
        "metric_snapshot",
        "report_snapshot",
        "analysis_attempts",
    }
    allowed = {
        "status",
        "analysis_status",
        "analysis_stage",
        "repair_status",
        "category",
        "summary",
        "direct_cause",
        "root_cause",
        "confidence",
        "evidence",
        "missing_evidence",
        "proposal",
        "metric_snapshot",
        "report_snapshot",
        "calculator_version",
        "prompt_version",
        "source_fingerprint",
        "generation_mode",
        "analysis_attempts",
        "audience",
        "application_status",
        "selected_change_ids",
        "preflight",
        "applied_script_id",
        "applied_run_id",
        "applied_by",
        "applied_at",
        "model_name",
        "error_message",
        "finished_at",
    }
    assignments: list[str] = []
    values: list[Any] = []
    for name, value in fields.items():
        if name not in allowed:
            raise ValueError(f"不支持更新性能分析字段：{name}")
        column = f"{name}_json" if name in json_fields else name
        assignments.append(f"{column} = ?")
        values.append(_dumps(value) if name in json_fields else value)
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(analysis_id)
    db.execute(
        f"UPDATE performance_analysis_sessions SET {', '.join(assignments)} WHERE id = ?",
        values,
    )


def find_analysis_session(db: Connection, analysis_id: str) -> Row | None:
    return db.execute("SELECT * FROM performance_analysis_sessions WHERE id = ?", (analysis_id,)).fetchone()


def find_active_analysis_for_run(db: Connection, run_id: str) -> Row | None:
    return db.execute(
        """
        SELECT * FROM performance_analysis_sessions
        WHERE run_id = ? AND analysis_status IN ('collecting', 'analyzing')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (run_id,),
    ).fetchone()


def find_analysis_for_applied_run(db: Connection, run_id: str) -> Row | None:
    return db.execute(
        """
        SELECT * FROM performance_analysis_sessions
        WHERE applied_run_id = ? AND preflight_json <> '{}'
        ORDER BY applied_at DESC, updated_at DESC
        LIMIT 1
        """,
        (run_id,),
    ).fetchone()


def list_analysis_sessions(db: Connection, project_id: str, run_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT * FROM performance_analysis_sessions
        WHERE project_id = ? AND run_id = ?
        ORDER BY analysis_version DESC, created_at DESC
        """,
        (project_id, run_id),
    ).fetchall()


def next_analysis_version(db: Connection, run_id: str) -> int:
    row = db.execute(
        "SELECT COALESCE(MAX(analysis_version), 0) + 1 AS version FROM performance_analysis_sessions WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    return int(row["version"])


def serialize_analysis_session(row: Row) -> dict[str, Any]:
    result = dict(row)
    result["evidence"] = _loads(result.pop("evidence_json", "[]"), [])
    result["missing_evidence"] = _loads(result.pop("missing_evidence_json", "[]"), [])
    result["proposal"] = _loads(result.pop("proposal_json", "{}"), {})
    result["metric_snapshot"] = _loads(result.pop("metric_snapshot_json", "{}"), {})
    result["report_snapshot"] = _loads(result.pop("report_snapshot_json", "{}"), {})
    result["analysis_attempts"] = _loads(result.pop("analysis_attempts_json", "[]"), [])
    result["selected_change_ids"] = _loads(result.pop("selected_change_ids_json", "[]"), [])
    result["preflight"] = _loads(result.pop("preflight_json", "{}"), {})
    result["applicable_change_ids"] = _applicable_change_ids(result["proposal"])
    legacy_status = str(result.get("status") or "")
    result["legacy_status"] = legacy_status
    stored_analysis_status = str(result.get("analysis_status") or "")
    if legacy_status in {"waiting_approval", "rejected"} and stored_analysis_status == "collecting":
        stored_analysis_status = "completed"
    result["analysis_status"] = stored_analysis_status or _analysis_status(legacy_status)
    stored_repair_status = str(result.get("repair_status") or "")
    if legacy_status == "waiting_approval" and result["applicable_change_ids"] and stored_repair_status == "not_applicable":
        stored_repair_status = "available"
    result["repair_status"] = stored_repair_status or _repair_status(legacy_status, result["applicable_change_ids"])
    result["available_actions"] = _available_actions(
        result["analysis_status"],
        result["repair_status"],
        str(result.get("application_status") or ""),
        result["applicable_change_ids"],
    )
    return result


def _available_actions(
    analysis_status: str,
    repair_status: str,
    application_status: str,
    applicable_change_ids: list[str],
) -> list[str]:
    if analysis_status == "completed":
        actions = ["reanalyze"]
        if repair_status == "available":
            actions.insert(0, "reject")
        if applicable_change_ids and application_status in {"not_requested", "preflight_failed", "apply_failed"}:
            actions.insert(0, "apply_and_rerun")
        return actions
    if analysis_status == "failed":
        return ["reanalyze"]
    return []


def _analysis_status(legacy_status: str) -> str:
    if legacy_status in {"collecting", "analyzing", "failed"}:
        return legacy_status
    return "completed"


def _repair_status(legacy_status: str, applicable_change_ids: list[str]) -> str:
    if legacy_status == "rejected":
        return "rejected"
    return "available" if applicable_change_ids else "not_applicable"


def _applicable_change_ids(proposal: dict[str, Any]) -> list[str]:
    return [
        str(change.get("id"))
        for change in proposal.get("changes", [])
        if isinstance(change, dict) and change.get("id") and is_applicable_change(change)
    ]


def is_applicable_change(change: dict[str, Any]) -> bool:
    from app.services.performance_testing.repair_service import is_supported_change

    return is_supported_change(change)
