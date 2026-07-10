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
        SELECT *
        FROM api_test_case_sets
        WHERE project_id = ?
        ORDER BY updated_at DESC, created_at DESC
        """,
        (project_id,),
    ).fetchall()


def find_api_test_case_set(db: Connection, set_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_test_case_sets WHERE id = ?", (set_id,)).fetchone()


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
    tags: list[str],
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
    generation_item_id: str | None = None,
    generation_attempt_id: str | None = None,
) -> str:
    db.execute(
        """
        INSERT INTO api_test_cases (
          id, project_id, endpoint_id, source_test_case_id, generation_run_id,
          generation_item_id, generation_attempt_id,
          title, priority, coverage, source, tags_json, preconditions_json,
          request_json, test_data_json, expected_json, assertions_json, variables_json, data_origin_json,
          data_file_path, notes, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            priority,
            coverage or "positive",
            source,
            dumps_json(tags),
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
        "tags": "tags_json",
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
    status: str = "queued",
) -> str:
    db.execute(
        """
        INSERT INTO api_automation_runs (
          id, project_id, api_environment_id, task_id, status,
          script_ids_json, command_summary, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            project_id,
            api_environment_id,
            task_id,
            status,
            dumps_json(script_ids),
            command_summary,
            created_by,
        ),
    )
    return run_id


def find_api_run(db: Connection, run_id: str) -> Row | None:
    return db.execute("SELECT * FROM api_automation_runs WHERE id = ?", (run_id,)).fetchone()


def update_api_run(
    db: Connection,
    run_id: str,
    *,
    status: str,
    stdout_path: str = "",
    stderr_path: str = "",
    json_report_path: str = "",
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
