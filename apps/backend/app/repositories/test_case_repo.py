from sqlite3 import Connection, Row


BASE_SET_SELECT = """
SELECT tcs.*,
       p.name AS project_name,
       d.name AS requirement_doc_title,
       COALESCE(er.title, '') AS exploration_run_title
FROM test_case_sets tcs
JOIN projects p ON p.id = tcs.project_id
JOIN source_documents d ON d.id = tcs.requirement_doc_id
LEFT JOIN exploration_runs er ON er.id = tcs.exploration_run_id
"""


def list_by_project(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        f"""
        {BASE_SET_SELECT}
        WHERE tcs.project_id = ?
        ORDER BY tcs.updated_at DESC, tcs.created_at DESC
        """,
        (project_id,),
    ).fetchall()


def list_by_requirement_document(db: Connection, requirement_doc_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT id, name, status
        FROM test_case_sets
        WHERE requirement_doc_id = ?
        ORDER BY updated_at DESC, created_at DESC
        """,
        (requirement_doc_id,),
    ).fetchall()


def find_set_by_id(db: Connection, set_id: str) -> Row | None:
    return db.execute(f"{BASE_SET_SELECT} WHERE tcs.id = ?", (set_id,)).fetchone()


def find_generation_run(db: Connection, run_id: str) -> Row | None:
    return db.execute(
        """
        SELECT r.*, s.project_id, s.requirement_doc_id, s.exploration_run_id, s.name AS test_case_set_name,
               s.include_company_knowledge, s.generation_scope_type, s.generation_scope_text
        FROM test_case_generation_runs r
        JOIN test_case_sets s ON s.id = r.test_case_set_id
        WHERE r.id = ?
        """,
        (run_id,),
    ).fetchone()


def list_active_generation_runs(db: Connection) -> list[Row]:
    return db.execute(
        """
        SELECT r.*, s.project_id, s.requirement_doc_id, s.exploration_run_id, s.name AS test_case_set_name,
               s.include_company_knowledge, s.generation_scope_type, s.generation_scope_text
        FROM test_case_generation_runs r
        JOIN test_case_sets s ON s.id = r.test_case_set_id
        WHERE r.status IN ('queued', 'running')
        """
    ).fetchall()


def delete_set(db: Connection, set_id: str) -> None:
    db.execute("DELETE FROM test_case_sets WHERE id = ?", (set_id,))


def create_set(
    db: Connection,
    *,
    set_id: str,
    project_id: str,
    name: str,
    requirement_doc_id: str,
    exploration_run_id: str,
    include_company_knowledge: bool,
    generation_scope_type: str,
    generation_scope_text: str,
    notes: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO test_case_sets
          (id, project_id, name, requirement_doc_id, exploration_run_id, include_company_knowledge,
           generation_scope_type, generation_scope_text, notes, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'generating', ?)
        """,
        (
            set_id,
            project_id,
            name,
            requirement_doc_id,
            exploration_run_id,
            1 if include_company_knowledge else 0,
            generation_scope_type,
            generation_scope_text,
            notes,
            created_by,
        ),
    )


def create_generation_run(
    db: Connection,
    *,
    run_id: str,
    test_case_set_id: str,
    task_id: str,
    input_json: str,
) -> None:
    db.execute(
        """
        INSERT INTO test_case_generation_runs
          (id, test_case_set_id, task_id, status, input_json)
        VALUES (?, ?, ?, 'queued', ?)
        """,
        (run_id, test_case_set_id, task_id, input_json),
    )


def update_generation_run_status(db: Connection, run_id: str, *, status: str, error_message: str = "") -> None:
    finished_expr = "CURRENT_TIMESTAMP" if status in {"completed", "failed"} else "NULL"
    db.execute(
        f"""
        UPDATE test_case_generation_runs
        SET status = ?,
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP,
            finished_at = {finished_expr}
        WHERE id = ?
        """,
        (status, error_message, run_id),
    )


def replace_cases(db: Connection, *, test_case_set_id: str, project_id: str, cases: list[dict]) -> None:
    db.execute("DELETE FROM test_cases WHERE test_case_set_id = ?", (test_case_set_id,))
    for case in cases:
        db.execute(
            """
            INSERT INTO test_cases
              (id, test_case_set_id, project_id, title, module, priority, preconditions,
               steps_json, expected_result, source_requirement_refs, source_exploration_refs, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready_for_review')
            """,
            (
                case["id"],
                test_case_set_id,
                project_id,
                case["title"],
                case["module"],
                case["priority"],
                case["preconditions"],
                case["steps_json"],
                case["expected_result"],
                case["source_requirement_refs"],
                case["source_exploration_refs"],
            ),
        )


def update_set_generation_result(db: Connection, set_id: str, *, status: str, case_count: int) -> None:
    db.execute(
        """
        UPDATE test_case_sets
        SET status = ?, case_count = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, case_count, set_id),
    )


def latest_generation_run(db: Connection, test_case_set_id: str) -> Row | None:
    return db.execute(
        """
        SELECT *
        FROM test_case_generation_runs
        WHERE test_case_set_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (test_case_set_id,),
    ).fetchone()


def latest_related_exploration(db: Connection, project_id: str, requirement_doc_id: str) -> Row | None:
    return db.execute(
        """
        SELECT id, title, status
        FROM exploration_runs
        WHERE project_id = ?
          AND requirement_doc_id = ?
          AND status IN ('completed', 'partial')
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
        """,
        (project_id, requirement_doc_id),
    ).fetchone()
