import json
import secrets
from sqlite3 import Connection, Row
from typing import Any


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def loads_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def create_document(
    db: Connection,
    *,
    document_id: str,
    project_id: str,
    name: str,
    source_type: str,
    source_url: str,
    file_path: str,
    version: str,
    endpoint_count: int,
    created_by: str,
    status: str = "parsed",
    error_message: str = "",
) -> str:
    db.execute(
        """
        INSERT INTO api_documents (
          id, project_id, name, source_type, source_url, file_path, version,
          status, endpoint_count, error_message, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            project_id,
            name,
            source_type,
            source_url,
            file_path,
            version,
            status,
            endpoint_count,
            error_message,
            created_by,
        ),
    )
    return document_id


def update_document_status(
    db: Connection,
    document_id: str,
    *,
    status: str,
    endpoint_count: int,
    error_message: str = "",
) -> None:
    db.execute(
        """
        UPDATE api_documents
        SET status = ?,
            endpoint_count = ?,
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, endpoint_count, error_message, document_id),
    )


def find_document(db: Connection, document_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_documents WHERE id = ?", (document_id,)).fetchone()


def upsert_endpoint(
    db: Connection,
    *,
    endpoint_id: str,
    project_id: str,
    document_id: str | None,
    method: str,
    path: str,
    normalized_path: str,
    summary: str,
    description: str,
    tags: list[dict[str, Any]] | list[str],
    parameters: list[dict[str, Any]],
    request_body: dict[str, Any],
    responses: dict[str, Any],
    auth: dict[str, Any],
    source: dict[str, Any],
    created_by: str,
) -> str:
    existing = db.execute(
        """
        SELECT id
        FROM api_endpoints
        WHERE project_id = ? AND method = ? AND normalized_path = ?
        """,
        (project_id, method.upper(), normalized_path),
    ).fetchone()
    if existing:
        db.execute(
            """
            UPDATE api_endpoints
            SET document_id = ?,
                path = ?,
                summary = ?,
                description = ?,
                tags_json = ?,
                parameters_json = ?,
                request_body_json = ?,
                responses_json = ?,
                auth_json = ?,
                source_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                document_id,
                path,
                summary,
                description,
                dumps_json(tags),
                dumps_json(parameters),
                dumps_json(request_body),
                dumps_json(responses),
                dumps_json(auth),
                dumps_json(source),
                existing["id"],
            ),
        )
        return str(existing["id"])

    db.execute(
        """
        INSERT INTO api_endpoints (
          id, project_id, document_id, method, path, normalized_path, summary,
          description, tags_json, parameters_json, request_body_json,
          responses_json, auth_json, source_json, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            endpoint_id,
            project_id,
            document_id,
            method.upper(),
            path,
            normalized_path,
            summary,
            description,
            dumps_json(tags),
            dumps_json(parameters),
            dumps_json(request_body),
            dumps_json(responses),
            dumps_json(auth),
            dumps_json(source),
            created_by,
        ),
    )
    return endpoint_id


def list_endpoints(
    db: Connection,
    project_id: str,
    *,
    method: str = "",
    tag: str = "",
    search: str = "",
) -> list[Row]:
    clauses = ["project_id = ?"]
    values: list[Any] = [project_id]
    if method:
        clauses.append("method = ?")
        values.append(method.upper())
    if tag:
        clauses.append("tags_json LIKE ?")
        values.append(f'%"{tag}"%')
    if search:
        clauses.append("(path LIKE ? OR summary LIKE ? OR description LIKE ?)")
        keyword = f"%{search}%"
        values.extend([keyword, keyword, keyword])
    return db.execute(
        f"""
        SELECT *
        FROM api_endpoints
        WHERE {" AND ".join(clauses)}
        ORDER BY path ASC, method ASC
        """,
        tuple(values),
    ).fetchall()


def find_endpoint(db: Connection, endpoint_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_endpoints WHERE id = ?", (endpoint_id,)).fetchone()


def delete_endpoint(db: Connection, endpoint_id: str) -> None:
    db.execute("DELETE FROM api_endpoints WHERE id = ?", (endpoint_id,))


def create_generation_run(
    db: Connection,
    *,
    run_id: str,
    task_id: str,
    project_id: str,
    api_environment_id: str | None,
    endpoint_ids: list[str],
    source_test_case_ids: list[str],
    generation_goal: str,
    options: dict[str, Any],
    created_by: str,
    status: str = "queued",
) -> str:
    db.execute(
        """
        INSERT INTO api_generation_runs (
          id, project_id, api_environment_id, task_id, status,
          endpoint_ids_json, source_test_case_ids_json, generation_goal,
          options_json, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            project_id,
            api_environment_id,
            task_id,
            status,
            dumps_json(endpoint_ids),
            dumps_json(source_test_case_ids),
            generation_goal,
            dumps_json(options),
            created_by,
        ),
    )
    return run_id


def update_generation_run(
    db: Connection,
    run_id: str,
    *,
    status: str,
    result_summary: dict[str, Any] | None = None,
    error_message: str = "",
    finished: bool | None = None,
) -> None:
    finished_sql = "" if finished is None else ", finished_at = CURRENT_TIMESTAMP" if finished else ", finished_at = NULL"
    db.execute(
        f"""
        UPDATE api_generation_runs
        SET status = ?,
            result_summary_json = COALESCE(?, result_summary_json),
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP
            {finished_sql}
        WHERE id = ?
        """,
        (status, dumps_json(result_summary) if result_summary is not None else None, error_message, run_id),
    )


def find_generation_run(db: Connection, run_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_generation_runs WHERE id = ?", (run_id,)).fetchone()


def list_generation_runs(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM api_generation_runs
        WHERE project_id = ?
        ORDER BY updated_at DESC, created_at DESC
        """,
        (project_id,),
    ).fetchall()


def create_generation_items(db: Connection, run_id: str, endpoint_ids: list[str]) -> None:
    db.executemany(
        """
        INSERT OR IGNORE INTO api_generation_items (id, generation_run_id, endpoint_id)
        VALUES (?, ?, ?)
        """,
        ((f"apigenitem-{secrets.token_hex(8)}", run_id, endpoint_id) for endpoint_id in endpoint_ids),
    )


def find_generation_item(db: Connection, item_id: str) -> Row | None:
    return db.execute(
        """
        SELECT item.*, endpoint.method, endpoint.path
        FROM api_generation_items AS item
        JOIN api_endpoints AS endpoint ON endpoint.id = item.endpoint_id
        WHERE item.id = ?
        """,
        (item_id,),
    ).fetchone()


def list_generation_items(db: Connection, run_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT item.*, endpoint.method, endpoint.path
        FROM api_generation_items AS item
        JOIN api_endpoints AS endpoint ON endpoint.id = item.endpoint_id
        WHERE item.generation_run_id = ?
        ORDER BY item.rowid
        """,
        (run_id,),
    ).fetchall()


def list_failed_generation_items(db: Connection, run_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT item.*, endpoint.method, endpoint.path
        FROM api_generation_items AS item
        JOIN api_endpoints AS endpoint ON endpoint.id = item.endpoint_id
        WHERE item.generation_run_id = ? AND item.status = 'failed'
        ORDER BY item.rowid
        """,
        (run_id,),
    ).fetchall()


def reset_failed_generation_items(db: Connection, run_id: str) -> None:
    db.execute(
        """
        UPDATE api_generation_items
        SET status = 'queued',
            error_message = '',
            started_at = NULL,
            finished_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE generation_run_id = ? AND status = 'failed'
        """,
        (run_id,),
    )


def start_generation_item_attempt(db: Connection, item_id: str, attempt_id: str) -> None:
    db.execute(
        """
        UPDATE api_generation_items
        SET status = 'running',
            attempt_count = attempt_count + 1,
            error_message = '',
            started_at = CURRENT_TIMESTAMP,
            finished_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (item_id,),
    )
    db.execute(
        """
        INSERT INTO api_generation_item_attempts (id, generation_item_id, attempt_no, status)
        SELECT ?, id, attempt_count, 'running'
        FROM api_generation_items
        WHERE id = ?
        """,
        (attempt_id, item_id),
    )


def finish_generation_item_attempt(
    db: Connection,
    item_id: str,
    attempt_id: str,
    *,
    status: str,
    generated_case_count: int = 0,
    error_message: str = "",
) -> None:
    db.execute(
        """
        UPDATE api_generation_item_attempts
        SET status = ?, generated_case_count = ?, error_message = ?, finished_at = CURRENT_TIMESTAMP
        WHERE id = ? AND generation_item_id = ?
        """,
        (status, generated_case_count, error_message, attempt_id, item_id),
    )
    db.execute(
        """
        UPDATE api_generation_items
        SET status = ?,
            generated_case_count = ?,
            error_message = ?,
            finished_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, generated_case_count, error_message, item_id),
    )


def list_generation_item_attempts(db: Connection, item_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM api_generation_item_attempts
        WHERE generation_item_id = ?
        ORDER BY attempt_no
        """,
        (item_id,),
    ).fetchall()


def create_api_test_case_set(
    db: Connection,
    *,
    set_id: str,
    project_id: str,
    name: str,
    notes: str,
    created_by: str,
) -> str:
    db.execute(
        """
        INSERT INTO api_test_case_sets (id, project_id, name, notes, created_by)
        VALUES (?, ?, ?, ?, ?)
        """,
        (set_id, project_id, name, notes, created_by),
    )
    return set_id


def list_api_test_case_sets(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT case_set.*,
               (SELECT COUNT(*)
                FROM api_endpoints AS endpoint
                WHERE endpoint.project_id = case_set.project_id) AS endpoint_count
        FROM api_test_case_sets AS case_set
        WHERE case_set.project_id = ?
        ORDER BY case_set.updated_at DESC, case_set.created_at DESC
        """,
        (project_id,),
    ).fetchall()


def find_api_test_case_set(db: Connection, set_id: str) -> Row | None:
    return db.execute(
        """
        SELECT case_set.*,
               (SELECT COUNT(*)
                FROM api_endpoints AS endpoint
                WHERE endpoint.project_id = case_set.project_id) AS endpoint_count
        FROM api_test_case_sets AS case_set
        WHERE case_set.id = ?
        """,
        (set_id,),
    ).fetchone()


def update_api_test_case_set(db: Connection, set_id: str, *, name: str, notes: str) -> None:
    db.execute(
        """
        UPDATE api_test_case_sets
        SET name = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (name, notes, set_id),
    )


def create_api_test_case(
    db: Connection,
    *,
    case_id: str,
    project_id: str,
    endpoint_id: str | None,
    source_test_case_id: str | None,
    generation_run_id: str | None,
    title: str,
    priority: str,
    coverage: str,
    source: str,
    preconditions: list[str],
    request: dict[str, Any],
    test_data: dict[str, Any],
    expected: dict[str, Any],
    assertions: list[dict[str, Any]],
    variables: dict[str, Any],
    data_origin: dict[str, Any],
    data_file_path: str,
    notes: str,
    created_by: str,
    test_description: str = "",
    generation_item_id: str | None = None,
    generation_attempt_id: str | None = None,
    test_point_key: str = "",
    oracle_status: str = "confirmed",
) -> str:
    db.execute(
        """
        INSERT INTO api_test_cases (
          id, project_id, endpoint_id, source_test_case_id, generation_run_id,
          generation_item_id, generation_attempt_id,
          title, test_point_key, oracle_status, test_description, priority, coverage, source, preconditions_json,
          request_json, test_data_json, expected_json, assertions_json, variables_json, data_origin_json,
          data_file_path, notes, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case_id,
            project_id,
            endpoint_id,
            source_test_case_id,
            generation_run_id,
            generation_item_id,
            generation_attempt_id,
            title,
            test_point_key,
            oracle_status,
            test_description,
            priority,
            coverage or "positive",
            source,
            dumps_json(preconditions),
            dumps_json(request),
            dumps_json(test_data),
            dumps_json(expected),
            dumps_json(assertions),
            dumps_json(variables),
            dumps_json(data_origin),
            data_file_path,
            notes,
            created_by,
        ),
    )
    return case_id


def list_api_test_cases(
    db: Connection,
    project_id: str,
    *,
    endpoint_id: str = "",
) -> list[Row]:
    clauses = ["project_id = ?"]
    values: list[Any] = [project_id]
    if endpoint_id:
        clauses.append("endpoint_id = ?")
        values.append(endpoint_id)
    return db.execute(
        f"""
        SELECT *
        FROM api_test_cases
        WHERE {" AND ".join(clauses)}
        ORDER BY created_at ASC, id ASC
        """,
        tuple(values),
    ).fetchall()


def find_api_test_case(db: Connection, case_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_test_cases WHERE id = ?", (case_id,)).fetchone()


def delete_api_test_case(db: Connection, case_id: str) -> None:
    db.execute("DELETE FROM api_test_cases WHERE id = ?", (case_id,))


def update_api_test_case(db: Connection, case_id: str, **fields: Any) -> None:
    if not fields:
        return
    json_fields = {
        "preconditions": "preconditions_json",
        "request": "request_json",
        "test_data": "test_data_json",
        "expected": "expected_json",
        "assertions": "assertions_json",
        "variables": "variables_json",
        "data_origin": "data_origin_json",
    }
    assignments = []
    values = []
    for key, value in fields.items():
        column = json_fields.get(key, key)
        assignments.append(f"{column} = ?")
        values.append(dumps_json(value) if key in json_fields else value)
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(case_id)
    db.execute(
        f"""
        UPDATE api_test_cases
        SET {", ".join(assignments)}
        WHERE id = ?
        """,
        tuple(values),
    )


def create_api_test_case_version(
    db: Connection,
    *,
    version_id: str,
    case_id: str,
    version: int,
    snapshot: dict[str, Any],
    change_source: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO api_test_case_versions (
          id, case_id, version, snapshot_json, change_source, created_by
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (version_id, case_id, version, dumps_json(snapshot), change_source, created_by),
    )


def list_api_test_case_versions(db: Connection, case_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM api_test_case_versions WHERE case_id = ? ORDER BY version",
        (case_id,),
    ).fetchall()


def create_oracle_proposal(
    db: Connection,
    *,
    proposal_id: str,
    project_id: str,
    endpoint_id: str,
    case_id: str,
    run_id: str,
    test_point_key: str,
    current_snapshot: dict[str, Any],
    proposed_snapshot: dict[str, Any],
    reasoning: str,
    confidence: float,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO api_oracle_proposals (
          id, project_id, endpoint_id, case_id, run_id, test_point_key,
          current_snapshot_json, proposed_snapshot_json, reasoning, confidence, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            proposal_id,
            project_id,
            endpoint_id,
            case_id,
            run_id,
            test_point_key,
            dumps_json(current_snapshot),
            dumps_json(proposed_snapshot),
            reasoning,
            confidence,
            created_by,
        ),
    )


def find_oracle_proposal(db: Connection, proposal_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_oracle_proposals WHERE id = ?", (proposal_id,)).fetchone()


def find_oracle_proposal_by_run_case(db: Connection, run_id: str, case_id: str) -> Row | None:
    return db.execute(
        "SELECT * FROM api_oracle_proposals WHERE run_id = ? AND case_id = ?",
        (run_id, case_id),
    ).fetchone()


def list_oracle_proposals(db: Connection, project_id: str, *, status: str = "") -> list[Row]:
    if status:
        return db.execute(
            "SELECT * FROM api_oracle_proposals WHERE project_id = ? AND status = ? ORDER BY created_at DESC",
            (project_id, status),
        ).fetchall()
    return db.execute(
        "SELECT * FROM api_oracle_proposals WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()


def review_oracle_proposal(
    db: Connection,
    proposal_id: str,
    *,
    status: str,
    review_scope: str,
    review_comment: str,
    reviewed_by: str,
) -> None:
    db.execute(
        """
        UPDATE api_oracle_proposals
        SET status = ?, review_scope = ?, review_comment = ?, reviewed_by = ?,
            reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, review_scope, review_comment, reviewed_by, proposal_id),
    )


def upsert_endpoint_oracle_fact(
    db: Connection,
    *,
    fact_id: str,
    endpoint_id: str,
    test_point_key: str,
    assertions: list[dict[str, Any]],
    evidence_run_ids: list[str],
    approved_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO api_endpoint_oracle_facts (
          id, endpoint_id, test_point_key, assertions_json, evidence_run_ids_json, approved_by
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(endpoint_id, test_point_key) DO UPDATE SET
          assertions_json = excluded.assertions_json,
          evidence_run_ids_json = excluded.evidence_run_ids_json,
          approved_by = excluded.approved_by,
          approved_at = CURRENT_TIMESTAMP,
          updated_at = CURRENT_TIMESTAMP
        """,
        (
            fact_id,
            endpoint_id,
            test_point_key,
            dumps_json(assertions),
            dumps_json(evidence_run_ids),
            approved_by,
        ),
    )


def list_endpoint_oracle_facts(db: Connection, endpoint_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM api_endpoint_oracle_facts WHERE endpoint_id = ? ORDER BY created_at",
        (endpoint_id,),
    ).fetchall()


def create_script(
    db: Connection,
    *,
    script_id: str,
    project_id: str,
    endpoint_id: str | None,
    api_test_case_id: str | None,
    test_case_id: str | None,
    generation_run_id: str | None,
    name: str,
    status: str,
    suite_path: str,
    test_file_path: str,
    data_file_path: str,
    notes: str,
    created_by: str,
) -> str:
    db.execute(
        """
        INSERT INTO api_test_scripts (
          id, project_id, endpoint_id, api_test_case_id, test_case_id,
          generation_run_id, name, status, suite_path, test_file_path,
          data_file_path, notes, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            script_id,
            project_id,
            endpoint_id,
            api_test_case_id,
            test_case_id,
            generation_run_id,
            name,
            status,
            suite_path,
            test_file_path,
            data_file_path,
            notes,
            created_by,
        ),
    )
    return script_id


def find_script(db: Connection, script_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_test_scripts WHERE id = ?", (script_id,)).fetchone()


def find_script_by_endpoint(db: Connection, project_id: str, endpoint_id: str) -> Row | None:
    return db.execute(
        "SELECT * FROM api_test_scripts WHERE project_id = ? AND endpoint_id = ?",
        (project_id, endpoint_id),
    ).fetchone()


def list_scripts(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT scripts.*, endpoints.method, endpoints.path, endpoints.summary AS endpoint_summary
        FROM api_test_scripts AS scripts
        LEFT JOIN api_endpoints AS endpoints ON endpoints.id = scripts.endpoint_id
        WHERE scripts.project_id = ?
        ORDER BY COALESCE(endpoints.path, scripts.name), scripts.name
        """,
        (project_id,),
    ).fetchall()


def count_scripts(db: Connection, project_id: str) -> int:
    return db.execute(
        "SELECT COUNT(*) AS total FROM api_test_scripts WHERE project_id = ?",
        (project_id,),
    ).fetchone()["total"]


def delete_script(db: Connection, script_id: str) -> None:
    db.execute("DELETE FROM api_test_scripts WHERE id = ?", (script_id,))


def upsert_script(
    db: Connection,
    *,
    script_id: str,
    project_id: str,
    endpoint_id: str,
    api_test_case_id: str | None,
    test_case_id: str | None,
    generation_run_id: str | None,
    name: str,
    status: str,
    suite_path: str,
    test_file_path: str,
    data_file_path: str,
    source_hash: str,
    case_count: int,
    created_by: str,
) -> tuple[str, str]:
    existing = find_script_by_endpoint(db, project_id, endpoint_id)
    if existing:
        db.execute(
            """
            UPDATE api_test_scripts
            SET api_test_case_id = ?, test_case_id = ?, generation_run_id = ?,
                name = ?, status = ?, suite_path = ?, test_file_path = ?, data_file_path = ?,
                source_hash = ?, case_count = ?, manual_modified = 0,
                updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                api_test_case_id,
                test_case_id,
                generation_run_id,
                name,
                status,
                suite_path,
                test_file_path,
                data_file_path,
                source_hash,
                case_count,
                created_by,
                existing["id"],
            ),
        )
        return str(existing["id"]), "updated"

    create_script(
        db,
        script_id=script_id,
        project_id=project_id,
        endpoint_id=endpoint_id,
        api_test_case_id=api_test_case_id,
        test_case_id=test_case_id,
        generation_run_id=generation_run_id,
        name=name,
        status=status,
        suite_path=suite_path,
        test_file_path=test_file_path,
        data_file_path=data_file_path,
        notes="",
        created_by=created_by,
    )
    db.execute(
        "UPDATE api_test_scripts SET source_hash = ?, case_count = ? WHERE id = ?",
        (source_hash, case_count, script_id),
    )
    return script_id, "created"


def update_scripts_last_run(db: Connection, script_ids: list[str], status: str) -> None:
    if not script_ids:
        return
    placeholders = ",".join("?" for _ in script_ids)
    db.execute(
        f"""
        UPDATE api_test_scripts
        SET last_run_status = ?, last_run_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id IN ({placeholders})
        """,
        (status, *script_ids),
    )


def create_api_run(
    db: Connection,
    *,
    run_id: str,
    task_id: str,
    project_id: str,
    api_environment_id: str | None,
    script_ids: list[str],
    command_summary: str,
    created_by: str,
    execution_snapshot: dict[str, Any] | None = None,
    target_type: str = "scripts",
    target_ids: list[str] | None = None,
    status: str = "queued",
    parent_run_id: str | None = None,
    source_repair_attempt_id: str | None = None,
) -> str:
    db.execute(
        """
        INSERT INTO api_automation_runs (
          id, project_id, api_environment_id, task_id, status,
          script_ids_json, target_type, target_ids_json, execution_snapshot_json, command_summary,
          parent_run_id, source_repair_attempt_id, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            project_id,
            api_environment_id,
            task_id,
            status,
            dumps_json(script_ids),
            target_type,
            dumps_json(target_ids or []),
            dumps_json(execution_snapshot or {}),
            command_summary,
            parent_run_id,
            source_repair_attempt_id,
            created_by,
        ),
    )
    return run_id


def create_repair_session(
    db: Connection,
    *,
    session_id: str,
    project_id: str,
    source_run_id: str,
    current_run_id: str,
    created_by: str,
) -> str:
    db.execute(
        """
        INSERT INTO api_repair_sessions (
          id, project_id, source_run_id, current_run_id, status, current_revision, created_by
        ) VALUES (?, ?, ?, ?, 'active', 0, ?)
        """,
        (session_id, project_id, source_run_id, current_run_id, created_by),
    )
    return session_id


def find_repair_session(db: Connection, session_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_repair_sessions WHERE id = ?", (session_id,)).fetchone()


def find_active_repair_session_for_run(db: Connection, project_id: str, run_id: str) -> Row | None:
    return db.execute(
        """
        SELECT * FROM api_repair_sessions
        WHERE project_id = ? AND source_run_id = ? AND status = 'active'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (project_id, run_id),
    ).fetchone()


def update_repair_session(
    db: Connection,
    session_id: str,
    *,
    status: str | None = None,
    current_run_id: str | None = None,
    current_revision: int | None = None,
) -> None:
    db.execute(
        """
        UPDATE api_repair_sessions
        SET status = COALESCE(?, status),
            current_run_id = COALESCE(?, current_run_id),
            current_revision = COALESCE(?, current_revision),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, current_run_id, current_revision, session_id),
    )


def create_repair_attempt(
    db: Connection,
    *,
    attempt_id: str,
    session_id: str,
    attempt_number: int,
    base_run_id: str,
    base_revision: int,
    user_context: str = "",
) -> str:
    db.execute(
        """
        INSERT INTO api_repair_attempts (
          id, session_id, attempt_number, base_run_id, base_revision, status, user_context
        ) VALUES (?, ?, ?, ?, ?, 'queued', ?)
        """,
        (attempt_id, session_id, attempt_number, base_run_id, base_revision, user_context),
    )
    return attempt_id


def find_repair_attempt(db: Connection, attempt_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_repair_attempts WHERE id = ?", (attempt_id,)).fetchone()


def list_repair_attempts(db: Connection, session_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM api_repair_attempts WHERE session_id = ? ORDER BY attempt_number ASC",
        (session_id,),
    ).fetchall()


def update_repair_attempt(
    db: Connection,
    attempt_id: str,
    *,
    status: str | None = None,
    diagnosis: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    decision: str | None = None,
    applied_run_id: str | None = None,
    error_message: str | None = None,
) -> None:
    db.execute(
        """
        UPDATE api_repair_attempts
        SET status = COALESCE(?, status),
            diagnosis_json = COALESCE(?, diagnosis_json),
            validation_json = COALESCE(?, validation_json),
            decision = COALESCE(?, decision),
            applied_run_id = COALESCE(?, applied_run_id),
            error_message = COALESCE(?, error_message),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            status,
            dumps_json(diagnosis) if diagnosis is not None else None,
            dumps_json(validation) if validation is not None else None,
            decision,
            applied_run_id,
            error_message,
            attempt_id,
        ),
    )


def find_api_run(db: Connection, run_id: str) -> Row | None:
    return db.execute(
        """
        SELECT runs.*, users.nickname AS created_by_nickname, users.username AS created_by_username
        FROM api_automation_runs AS runs
        LEFT JOIN users ON users.id = runs.created_by
        WHERE runs.id = ?
        """,
        (run_id,),
    ).fetchone()


def list_api_runs(
    db: Connection,
    project_id: str,
    *,
    page: int,
    page_size: int,
    status: str = "",
    environment_id: str = "",
    keyword: str = "",
) -> tuple[list[Row], int]:
    conditions = ["runs.project_id = ?"]
    params: list[Any] = [project_id]
    if status:
        conditions.append("runs.status = ?")
        params.append(status)
    if environment_id:
        conditions.append("runs.api_environment_id = ?")
        params.append(environment_id)
    if keyword:
        conditions.append("(runs.id LIKE ? OR runs.execution_snapshot_json LIKE ?)")
        pattern = f"%{keyword}%"
        params.extend([pattern, pattern])
    where_clause = " AND ".join(conditions)
    total = int(
        db.execute(f"SELECT COUNT(*) FROM api_automation_runs AS runs WHERE {where_clause}", params).fetchone()[0]
    )
    offset = (page - 1) * page_size
    rows = db.execute(
        f"""
        SELECT runs.*, users.nickname AS created_by_nickname, users.username AS created_by_username
        FROM api_automation_runs AS runs
        LEFT JOIN users ON users.id = runs.created_by
        WHERE {where_clause}
        ORDER BY runs.created_at DESC, runs.id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, page_size, offset),
    ).fetchall()
    return rows, total


def delete_api_run(db: Connection, run_id: str) -> None:
    db.execute("DELETE FROM api_automation_runs WHERE id = ?", (run_id,))


def update_api_run(
    db: Connection,
    run_id: str,
    *,
    status: str,
    stdout_path: str = "",
    stderr_path: str = "",
    json_report_path: str = "",
    scenario_result_path: str = "",
    observation_result_path: str = "",
    summary: dict[str, Any] | None = None,
    error_message: str = "",
    finished: bool = False,
) -> None:
    db.execute(
        f"""
        UPDATE api_automation_runs
        SET status = ?,
            stdout_path = COALESCE(NULLIF(?, ''), stdout_path),
            stderr_path = COALESCE(NULLIF(?, ''), stderr_path),
            json_report_path = COALESCE(NULLIF(?, ''), json_report_path),
            scenario_result_path = COALESCE(NULLIF(?, ''), scenario_result_path),
            observation_result_path = COALESCE(NULLIF(?, ''), observation_result_path),
            summary_json = COALESCE(?, summary_json),
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP
            {", finished_at = CURRENT_TIMESTAMP" if finished else ""}
        WHERE id = ?
        """,
        (
            status,
            stdout_path,
            stderr_path,
            json_report_path,
            scenario_result_path,
            observation_result_path,
            dumps_json(summary) if summary is not None else None,
            error_message,
            run_id,
        ),
    )


def create_api_environment(
    db: Connection,
    *,
    environment_id: str,
    project_id: str,
    linked_ui_environment_id: str | None,
    name: str,
    api_base_url: str,
    username: str,
    password_encrypted: str,
    password_hash: str,
    auth_type: str,
    auth_config: dict[str, Any],
    variables: dict[str, Any],
    default_headers: dict[str, Any],
    timeout_seconds: int,
    verify_ssl: bool,
    auth_state_ttl_seconds: int,
    description: str,
    created_by: str,
) -> str:
    db.execute(
        """
        INSERT INTO api_test_environments (
          id, project_id, linked_ui_environment_id, name, api_base_url,
          username, password_encrypted, password_hash, auth_type,
          auth_config_json, variables_json, default_headers_json,
          timeout_seconds, verify_ssl, auth_state_ttl_seconds, description,
          created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            environment_id,
            project_id,
            linked_ui_environment_id,
            name,
            api_base_url,
            username,
            password_encrypted,
            password_hash,
            auth_type,
            dumps_json(auth_config),
            dumps_json(variables),
            dumps_json(default_headers),
            timeout_seconds,
            1 if verify_ssl else 0,
            auth_state_ttl_seconds,
            description,
            created_by,
        ),
    )
    return environment_id


def list_api_environments(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM api_test_environments
        WHERE project_id = ?
        ORDER BY created_at ASC, name ASC
        """,
        (project_id,),
    ).fetchall()


def find_api_environment(db: Connection, environment_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_test_environments WHERE id = ?", (environment_id,)).fetchone()


def update_api_environment(db: Connection, environment_id: str, **fields: Any) -> None:
    if not fields:
        return
    json_fields = {
        "auth_config": "auth_config_json",
        "variables": "variables_json",
        "default_headers": "default_headers_json",
    }
    assignments = []
    values = []
    for key, value in fields.items():
        column = json_fields.get(key, key)
        assignments.append(f"{column} = ?")
        if key in json_fields:
            values.append(dumps_json(value))
        elif key == "verify_ssl":
            values.append(1 if value else 0)
        else:
            values.append(value)
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(environment_id)
    db.execute(
        f"""
        UPDATE api_test_environments
        SET {", ".join(assignments)}
        WHERE id = ?
        """,
        tuple(values),
    )


def delete_api_environment(db: Connection, environment_id: str) -> None:
    db.execute("DELETE FROM api_test_environments WHERE id = ?", (environment_id,))


def create_script_generation_run(
    db: Connection,
    *,
    run_id: str,
    project_id: str,
    task_id: str,
    endpoint_ids: list[str],
    api_environment_id: str | None,
    force: bool,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO api_script_generation_runs (
          id, project_id, task_id, status, endpoint_ids_json,
          api_environment_id, force, created_by
        ) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)
        """,
        (run_id, project_id, task_id, dumps_json(endpoint_ids), api_environment_id, 1 if force else 0, created_by),
    )


def find_script_generation_run(db: Connection, run_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_script_generation_runs WHERE id = ?", (run_id,)).fetchone()


def update_script_generation_run(db: Connection, run_id: str, **fields: Any) -> None:
    if not fields:
        return
    json_fields = {"endpoint_ids": "endpoint_ids_json", "changed_files": "changed_files_json", "result_summary": "result_summary_json"}
    assignments = []
    values = []
    for key, value in fields.items():
        column = json_fields.get(key, key)
        assignments.append(f"{column} = ?")
        values.append(dumps_json(value) if key in json_fields else value)
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(run_id)
    db.execute(f"UPDATE api_script_generation_runs SET {', '.join(assignments)} WHERE id = ?", tuple(values))
