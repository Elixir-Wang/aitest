import json
import secrets
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


def update_run(db: Connection, run_id: str, *, status: str, error_message: str | None = None, **fields) -> None:
    assignments = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    values: list[object] = [status]
    if error_message is not None:
        assignments.append("error_message = ?")
        values.append(error_message[:1000])
    for column, value in fields.items():
        assignments.append(f"{column} = ?")
        values.append(value)
    if status in {"completed", "failed"}:
        assignments.append("finished_at = CURRENT_TIMESTAMP")
    values.append(run_id)
    db.execute(f"UPDATE test_point_generation_runs SET {', '.join(assignments)} WHERE id = ?", tuple(values))


def requeue_run(db: Connection, run_id: str) -> None:
    db.execute(
        """UPDATE test_point_generation_runs
        SET status = 'queued', error_message = '', coverage_status = 'pending',
            missing_obligations_json = '[]', obligations_json = '[]', unsupported_assumptions_json = '[]',
            supplement_round = 0, finished_at = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?""",
        (run_id,),
    )


def replace_obligations(
    db: Connection,
    *,
    project_id: str,
    document_id: str,
    version_id: str,
    obligations: list[dict],
) -> None:
    db.execute("DELETE FROM test_point_obligations WHERE requirement_version_id = ?", (version_id,))
    db.execute("DELETE FROM test_point_requirement_obligations WHERE requirement_version_id = ?", (version_id,))
    for obligation in obligations:
        db.execute(
            """INSERT INTO test_point_requirement_obligations
            (id, project_id, document_id, requirement_version_id, obligation_key,
             source_section, statement, obligation_type, modules_json, thresholds_json,
             explicit, test_required)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"tpro-{secrets.token_hex(8)}",
                project_id,
                document_id,
                version_id,
                obligation["obligation_key"],
                obligation["source_section"],
                obligation["statement"],
                obligation["obligation_type"],
                json.dumps(obligation.get("modules", []), ensure_ascii=False),
                json.dumps(obligation.get("thresholds", []), ensure_ascii=False),
                int(obligation.get("explicit", True)),
                int(obligation.get("test_required", True)),
            ),
        )


def list_obligations(db: Connection, document_id: str, version_id: str) -> list[dict]:
    rows = db.execute(
        """SELECT * FROM test_point_requirement_obligations
        WHERE document_id = ? AND requirement_version_id = ?
        ORDER BY obligation_key ASC""",
        (document_id, version_id),
    ).fetchall()
    return [
        dict(row)
        | {
            "modules": json.loads(row["modules_json"] or "[]"),
            "thresholds": json.loads(row["thresholds_json"] or "[]"),
            "explicit": bool(row["explicit"]),
            "test_required": bool(row["test_required"]),
        }
        for row in rows
    ]


def replace_point_obligation_links(db: Connection, *, version_id: str, links: dict[str, list[str]]) -> None:
    db.execute("DELETE FROM test_point_obligations WHERE requirement_version_id = ?", (version_id,))
    obligation_rows = db.execute(
        "SELECT id, obligation_key FROM test_point_requirement_obligations WHERE requirement_version_id = ?",
        (version_id,),
    ).fetchall()
    obligation_ids = {row["obligation_key"]: row["id"] for row in obligation_rows}
    for point_id, obligation_keys in links.items():
        for obligation_key in obligation_keys:
            obligation_id = obligation_ids.get(obligation_key)
            if obligation_id is None:
                raise ValueError(f"不存在的需求义务：{obligation_key}")
            db.execute(
                """INSERT INTO test_point_obligations
                (test_point_id, obligation_id, requirement_version_id)
                VALUES (?, ?, ?)""",
                (point_id, obligation_id, version_id),
            )


def list_point_obligation_links(db: Connection, version_id: str) -> dict[str, list[str]]:
    rows = db.execute(
        """SELECT link.test_point_id, obligation.obligation_key
        FROM test_point_obligations AS link
        JOIN test_point_requirement_obligations AS obligation ON obligation.id = link.obligation_id
        WHERE link.requirement_version_id = ?
        ORDER BY link.test_point_id ASC, obligation.obligation_key ASC""",
        (version_id,),
    ).fetchall()
    links: dict[str, list[str]] = {}
    for row in rows:
        links.setdefault(row["test_point_id"], []).append(row["obligation_key"])
    return links


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
             preconditions_json, verification_points_json, source_refs_json, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                point["id"], project_id, document_id, version_id, run_id,
                point["point_key"], point["title"], point["module"], point["category"], point["priority"], point["description"],
                json.dumps(point["preconditions"], ensure_ascii=False),
                json.dumps(point["verification_points"], ensure_ascii=False), json.dumps(point["source_refs"], ensure_ascii=False),
                point["notes"],
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


def delete_point_obligation_links(db: Connection, point_id: str) -> None:
    db.execute("DELETE FROM test_point_obligations WHERE test_point_id = ?", (point_id,))
