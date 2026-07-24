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
) -> None:
    db.execute(
        """
        INSERT INTO performance_analysis_sessions (
          id, project_id, run_id, status, analysis_version, created_by
        ) VALUES (?, ?, ?, 'collecting', ?, ?)
        """,
        (analysis_id, project_id, run_id, analysis_version, created_by),
    )


def update_analysis_session(db: Connection, analysis_id: str, **fields: Any) -> None:
    if not fields:
        return
    json_fields = {"evidence", "missing_evidence", "proposal", "selected_change_ids", "preflight"}
    allowed = {
        "status",
        "category",
        "summary",
        "direct_cause",
        "root_cause",
        "confidence",
        "evidence",
        "missing_evidence",
        "proposal",
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
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    return db.execute(
        f"""
        SELECT * FROM performance_analysis_sessions
        WHERE run_id = ? AND status IN ({placeholders})
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (run_id, *ACTIVE_STATUSES),
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
    result["selected_change_ids"] = _loads(result.pop("selected_change_ids_json", "[]"), [])
    result["preflight"] = _loads(result.pop("preflight_json", "{}"), {})
    result["applicable_change_ids"] = _applicable_change_ids(result["proposal"])
    result["available_actions"] = _available_actions(
        str(result.get("status") or ""),
        str(result.get("application_status") or ""),
        result["applicable_change_ids"],
    )
    return result


def _available_actions(status: str, application_status: str, applicable_change_ids: list[str]) -> list[str]:
    if status == "waiting_approval":
        actions = ["reject", "reanalyze"]
        if applicable_change_ids and application_status in {"not_requested", "preflight_failed", "apply_failed"}:
            actions.insert(0, "apply_and_rerun")
        return actions
    if status in {"failed", "rejected"}:
        return ["reanalyze"]
    return []


def _applicable_change_ids(proposal: dict[str, Any]) -> list[str]:
    from app.services.performance_testing.repair_service import is_supported_change

    return [
        str(change.get("id"))
        for change in proposal.get("changes", [])
        if isinstance(change, dict) and change.get("id") and is_supported_change(change)
    ]
