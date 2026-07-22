import json
from sqlite3 import Connection, Row
from typing import Any


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: str | None, default: Any) -> Any:
    return json.loads(value) if value else default


def create_scenario(
    db: Connection,
    *,
    scenario_id: str,
    project_id: str,
    name: str,
    description: str,
    api_environment_id: str,
    scenario_definition: dict[str, Any],
    load_profile: dict[str, Any],
    data_source: dict[str, Any],
    quality_gate: dict[str, Any],
    safety_policy: dict[str, Any],
    created_by: str,
) -> None:
    db.execute(
        """INSERT INTO performance_scenarios (
          id, project_id, name, description, api_environment_id, scenario_definition_json,
          load_profile_json, data_source_json, quality_gate_json, safety_policy_json, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (scenario_id, project_id, name, description, api_environment_id, _dumps(scenario_definition), _dumps(load_profile), _dumps(data_source), _dumps(quality_gate), _dumps(safety_policy), created_by),
    )


def get_scenario(db: Connection, scenario_id: str) -> Row | None:
    return db.execute("SELECT * FROM performance_scenarios WHERE id = ?", (scenario_id,)).fetchone()


def serialize_scenario(row: Row) -> dict[str, Any]:
    return {
        "id": row["id"], "project_id": row["project_id"], "name": row["name"], "description": row["description"],
        "api_environment_id": row["api_environment_id"], "definition_version": row["definition_version"],
        "scenario_definition": _loads(row["scenario_definition_json"], {}), "load_profile": _loads(row["load_profile_json"], {}),
        "data_source": _loads(row["data_source_json"], {}), "quality_gate": _loads(row["quality_gate_json"], {}),
        "safety_policy": _loads(row["safety_policy_json"], {}), "created_by": row["created_by"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }
