import json
from sqlite3 import Connection, Row
from typing import Any


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def next_version(db: Connection, performance_test_id: str) -> int:
    row = db.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM performance_test_scripts WHERE performance_test_id = ?",
        (performance_test_id,),
    ).fetchone()
    return int(row["next_version"])


def create_script(
    db: Connection,
    *,
    script_id: str,
    performance_test_id: str,
    project_id: str,
    version: int,
    generation_source: str,
    template_version: str,
    input_hash: str,
    plan: dict[str, Any],
    code: str,
    validation_status: str,
    validation_result: dict[str, Any],
) -> None:
    db.execute(
        """
        INSERT INTO performance_test_scripts (
          id, performance_test_id, project_id, version, generation_source,
          template_version, input_hash, plan_json, code, validation_status,
          validation_result_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            script_id,
            performance_test_id,
            project_id,
            version,
            generation_source,
            template_version,
            input_hash,
            _dumps(plan),
            code,
            validation_status,
            _dumps(validation_result),
        ),
    )


def list_scripts(db: Connection, performance_test_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM performance_test_scripts WHERE performance_test_id = ? ORDER BY version DESC",
        (performance_test_id,),
    ).fetchall()


def find_script(db: Connection, script_id: str) -> Row | None:
    return db.execute("SELECT * FROM performance_test_scripts WHERE id = ?", (script_id,)).fetchone()


def update_pending_script(
    db: Connection,
    script_id: str,
    *,
    plan: dict[str, Any],
    code: str,
    input_hash: str,
    validation_status: str,
    validation_result: dict[str, Any],
) -> None:
    db.execute(
        """
        UPDATE performance_test_scripts
        SET generation_source = 'user_edited', plan_json = ?, code = ?, input_hash = ?,
            validation_status = ?, validation_result_json = ?
        WHERE id = ?
        """,
        (_dumps(plan), code, input_hash, validation_status, _dumps(validation_result), script_id),
    )


def confirm_script(db: Connection, script_id: str, actor_id: str) -> None:
    row = find_script(db, script_id)
    if not row:
        return
    db.execute(
        """
        UPDATE performance_test_scripts
        SET validation_status = 'superseded'
        WHERE performance_test_id = ? AND validation_status = 'confirmed' AND id <> ?
        """,
        (row["performance_test_id"], script_id),
    )
    db.execute(
        """
        UPDATE performance_test_scripts
        SET validation_status = 'confirmed', confirmed_by = ?, confirmed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (actor_id, script_id),
    )


def serialize_script(row: Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "performance_test_id": row["performance_test_id"],
        "project_id": row["project_id"],
        "version": row["version"],
        "generation_source": row["generation_source"],
        "model_id": row["model_id"],
        "prompt_version": row["prompt_version"],
        "template_version": row["template_version"],
        "input_hash": row["input_hash"],
        "plan": _loads(row["plan_json"], {}),
        "code": row["code"],
        "assumptions": _loads(row["assumptions_json"], []),
        "required_runtime_variables": _loads(row["required_runtime_variables_json"], []),
        "validation_status": row["validation_status"],
        "validation_result": _loads(row["validation_result_json"], {}),
        "confirmed_by": row["confirmed_by"],
        "confirmed_at": row["confirmed_at"],
        "created_at": row["created_at"],
    }


def delete_scripts_by_test(db: Connection, performance_test_id: str) -> None:
    """Delete all scripts for a performance test."""
    db.execute("DELETE FROM performance_test_scripts WHERE performance_test_id = ?", (performance_test_id,))

