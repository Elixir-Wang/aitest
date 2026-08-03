import json
from sqlite3 import Connection, Row
from typing import Any


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def create_performance_test(
    db: Connection,
    *,
    test_id: str,
    project_id: str,
    name: str,
    description: str,
    target_type: str,
    endpoint_id: str | None,
    scenario_id: str | None,
    api_environment_id: str,
    request_config: dict[str, Any],
    load_config: dict[str, Any],
    data_config: dict[str, Any],
    circuit_breaker: dict[str, Any],
    performance_goal: dict[str, Any],
    success_rules: list[dict[str, Any]],
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO performance_tests (
          id, project_id, name, description, target_type, endpoint_id, scenario_id,
          api_environment_id, request_config_json,
          load_config_json, data_config_json, circuit_breaker_json,
          performance_goal_json, success_rules_json, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            test_id,
            project_id,
            name,
            description,
            target_type,
            endpoint_id,
            scenario_id,
            api_environment_id,
            _dumps(request_config),
            _dumps(load_config),
            _dumps(data_config),
            _dumps(circuit_breaker),
            _dumps(performance_goal),
            _dumps(success_rules),
            created_by,
        ),
    )


def list_performance_tests(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT
          performance_tests.*,
          COALESCE(api_endpoints.summary, '') AS endpoint_name,
          COALESCE(api_endpoints.method, '') AS endpoint_method,
          COALESCE(api_endpoints.path, '') AS endpoint_path,
          COALESCE(api_scenarios.name, '') AS scenario_name,
          COALESCE(api_test_environments.name, '') AS environment_name,
          (
            SELECT id
            FROM performance_test_scripts
            WHERE performance_test_id = performance_tests.id
            LIMIT 1
          ) AS latest_script_id,
          '' AS latest_run_status,
          '{}' AS latest_goal_result_json,
          NULL AS latest_run_at
        FROM performance_tests
        LEFT JOIN api_endpoints ON api_endpoints.id = performance_tests.endpoint_id
        LEFT JOIN api_scenarios ON api_scenarios.id = performance_tests.scenario_id
        LEFT JOIN api_test_environments ON api_test_environments.id = performance_tests.api_environment_id
        WHERE performance_tests.project_id = ?
        ORDER BY performance_tests.updated_at DESC, performance_tests.created_at DESC
        """,
        (project_id,),
    ).fetchall()


def find_performance_test(db: Connection, test_id: str) -> Row | None:
    return db.execute(
        """
        SELECT
          performance_tests.*,
          COALESCE(api_endpoints.summary, '') AS endpoint_name,
          COALESCE(api_endpoints.method, '') AS endpoint_method,
          COALESCE(api_endpoints.path, '') AS endpoint_path,
          COALESCE(api_scenarios.name, '') AS scenario_name,
          COALESCE(api_test_environments.name, '') AS environment_name,
          (
            SELECT id
            FROM performance_test_scripts
            WHERE performance_test_id = performance_tests.id
            LIMIT 1
          ) AS latest_script_id,
          '' AS latest_run_status,
          '{}' AS latest_goal_result_json,
          NULL AS latest_run_at
        FROM performance_tests
        LEFT JOIN api_endpoints ON api_endpoints.id = performance_tests.endpoint_id
        LEFT JOIN api_scenarios ON api_scenarios.id = performance_tests.scenario_id
        LEFT JOIN api_test_environments ON api_test_environments.id = performance_tests.api_environment_id
        WHERE performance_tests.id = ?
        """,
        (test_id,),
    ).fetchone()


def update_performance_test(db: Connection, test_id: str, fields: dict[str, Any]) -> None:
    if not fields:
        return
    json_columns = {
        "request_config": "request_config_json",
        "load_config": "load_config_json",
        "data_config": "data_config_json",
        "circuit_breaker": "circuit_breaker_json",
        "performance_goal": "performance_goal_json",
        "success_rules": "success_rules_json",
    }
    assignments: list[str] = []
    values: list[Any] = []
    for field, value in fields.items():
        assignments.append(f"{json_columns.get(field, field)} = ?")
        values.append(_dumps(value) if field in json_columns else value)
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(test_id)
    db.execute(f"UPDATE performance_tests SET {', '.join(assignments)} WHERE id = ?", tuple(values))


def delete_performance_test(db: Connection, test_id: str) -> None:
    db.execute("DELETE FROM performance_tests WHERE id = ?", (test_id,))


def serialize_performance_test(row: Row) -> dict[str, Any]:
    latest_goal_result = _loads(row["latest_goal_result_json"], {})
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "description": row["description"],
        "target_type": row["target_type"],
        "endpoint_id": row["endpoint_id"],
        "endpoint_name": row["endpoint_name"],
        "endpoint_method": row["endpoint_method"],
        "endpoint_path": row["endpoint_path"],
        "scenario_id": row["scenario_id"],
        "scenario_name": row["scenario_name"],
        "api_environment_id": row["api_environment_id"],
        "environment_name": row["environment_name"],
        "latest_script_id": row["latest_script_id"],
        "request_config": _loads(row["request_config_json"], {}),
        "load_config": _loads(row["load_config_json"], {}),
        "data_config": _loads(row["data_config_json"], {}),
        "circuit_breaker": _loads(row["circuit_breaker_json"], {}),
        "performance_goal": _loads(row["performance_goal_json"], {}),
        "success_rules": _loads(row["success_rules_json"], []),
        "latest_run_status": row["latest_run_status"],
        "latest_goal_status": str(latest_goal_result.get("status", "")),
        "latest_run_at": row["latest_run_at"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
