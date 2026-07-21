import json
from sqlite3 import Connection, Row


def create_run(db: Connection, *, run_id: str, project_id: str, document_id: str, version_id: str, task_id: str, input_json: str, created_by: str) -> None:
    db.execute(
        """INSERT INTO test_point_generation_runs
        (id, project_id, document_id, requirement_version_id, task_id, status, input_json, created_by)
        VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)""",
        (run_id, project_id, document_id, version_id, task_id, input_json, created_by),
    )


def find_run_by_version(db: Connection, document_id: str, version_id: str) -> Row | None:
    return db.execute(
        "SELECT * FROM test_point_generation_runs WHERE document_id = ? AND requirement_version_id = ?",
        (document_id, version_id),
    ).fetchone()


def find_run(db: Connection, run_id: str) -> Row | None:
    return db.execute("SELECT * FROM test_point_generation_runs WHERE id = ?", (run_id,)).fetchone()


def update_run(db: Connection, run_id: str, *, status: str, error_message: str | None = None) -> None:
    assignments = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    values: list[object] = [status]
    if error_message is not None:
        assignments.append("error_message = ?")
        values.append(error_message[:1000])
    if status in {"completed", "failed"}:
        assignments.append("finished_at = CURRENT_TIMESTAMP")
    values.append(run_id)
    db.execute(f"UPDATE test_point_generation_runs SET {', '.join(assignments)} WHERE id = ?", tuple(values))


def requeue_run(db: Connection, run_id: str) -> None:
    run = db.execute("SELECT requirement_version_id FROM test_point_generation_runs WHERE id = ?", (run_id,)).fetchone()
    if run:
        db.execute("DELETE FROM test_points WHERE requirement_version_id = ?", (run["requirement_version_id"],))
    db.execute(
        """UPDATE test_point_generation_runs
        SET status = 'queued', error_message = '', finished_at = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?""",
        (run_id,),
    )


def list_points(db: Connection, document_id: str, version_id: str) -> list[Row]:
    return db.execute(
        """SELECT * FROM test_points
        WHERE document_id = ? AND requirement_version_id = ?
        ORDER BY priority ASC, module ASC, point_key ASC""",
        (document_id, version_id),
    ).fetchall()


def replace_points(db: Connection, *, run_id: str, project_id: str, document_id: str, version_id: str, points: list[dict]) -> None:
    db.execute("DELETE FROM test_points WHERE requirement_version_id = ?", (version_id,))
    for point in points:
        db.execute(
            """INSERT INTO test_points
            (id, project_id, document_id, requirement_version_id, generation_run_id,
             point_key, title, module, category, priority, description,
             preconditions_json, verification_points_json, source_refs_json, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                point["id"], project_id, document_id, version_id, run_id,
                point["point_key"], point["title"], point["module"], point["category"], point["priority"], point["description"],
                json.dumps(point["preconditions"], ensure_ascii=False),
                json.dumps(point["verification_points"], ensure_ascii=False), json.dumps(point["source_refs"], ensure_ascii=False),
                point["notes"], point.get("status", "draft"),
            ),
        )


def find_point(db: Connection, point_id: str) -> Row | None:
    return db.execute("SELECT * FROM test_points WHERE id = ?", (point_id,)).fetchone()


def update_point(db: Connection, point_id: str, values: dict[str, object]) -> None:
    if not values:
        return
    assignments = []
    params: list[object] = []
    json_fields = {"preconditions", "verification_points", "source_refs"}
    for key, value in values.items():
        column = f"{key}_json" if key in json_fields else key
        assignments.append(f"{column} = ?")
        params.append(json.dumps(value, ensure_ascii=False) if key in json_fields else value)
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    params.append(point_id)
    db.execute(f"UPDATE test_points SET {', '.join(assignments)} WHERE id = ?", tuple(params))


def delete_point(db: Connection, point_id: str) -> None:
    db.execute("DELETE FROM test_points WHERE id = ?", (point_id,))
