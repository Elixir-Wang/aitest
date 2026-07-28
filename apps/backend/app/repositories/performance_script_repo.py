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


def save_script(
    db: Connection,
    *,
    script_id: str,
    performance_test_id: str,
    project_id: str,
    generation_source: str,
    model_id: str,
    prompt_version: str,
    plan: dict[str, Any],
    code: str,
    validation_status: str,
    validation_result: dict[str, Any],
) -> None:
    db.execute(
        """
        INSERT INTO performance_test_scripts (
          id, performance_test_id, project_id, generation_source, model_id,
          prompt_version, plan_json, code, validation_status, validation_result_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(performance_test_id) DO UPDATE SET
          generation_source = excluded.generation_source,
          model_id = excluded.model_id,
          prompt_version = excluded.prompt_version,
          plan_json = excluded.plan_json,
          code = excluded.code,
          validation_status = excluded.validation_status,
          validation_result_json = excluded.validation_result_json,
          updated_at = CURRENT_TIMESTAMP
        """,
        (
            script_id,
            performance_test_id,
            project_id,
            generation_source,
            model_id,
            prompt_version,
            _dumps(plan),
            code,
            validation_status,
            _dumps(validation_result),
        ),
    )


def find_script_by_test(db: Connection, performance_test_id: str) -> Row | None:
    return db.execute(
        "SELECT * FROM performance_test_scripts WHERE performance_test_id = ?",
        (performance_test_id,),
    ).fetchone()


def find_script(db: Connection, script_id: str) -> Row | None:
    return db.execute("SELECT * FROM performance_test_scripts WHERE id = ?", (script_id,)).fetchone()


def update_script(
    db: Connection,
    script_id: str,
    *,
    plan: dict[str, Any],
    code: str,
    validation_status: str,
    validation_result: dict[str, Any],
) -> None:
    db.execute(
        """
        UPDATE performance_test_scripts
        SET generation_source = 'user_edited', plan_json = ?, code = ?,
            validation_status = ?, validation_result_json = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (_dumps(plan), code, validation_status, _dumps(validation_result), script_id),
    )


def serialize_script(row: Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "performance_test_id": row["performance_test_id"],
        "project_id": row["project_id"],
        "generation_source": row["generation_source"],
        "model_id": row["model_id"],
        "prompt_version": row["prompt_version"],
        "plan": _loads(row["plan_json"], {}),
        "code": row["code"],
        "assumptions": _loads(row["assumptions_json"], []),
        "required_runtime_variables": _loads(row["required_runtime_variables_json"], []),
        "validation_status": row["validation_status"],
        "validation_result": _loads(row["validation_result_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def delete_scripts_by_test(db: Connection, performance_test_id: str) -> None:
    """Delete all scripts for a performance test."""
    db.execute("DELETE FROM performance_test_scripts WHERE performance_test_id = ?", (performance_test_id,))
