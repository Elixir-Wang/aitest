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


def find_set_by_id(db: Connection, set_id: str) -> Row | None:
    return db.execute(f"{BASE_SET_SELECT} WHERE tcs.id = ?", (set_id,)).fetchone()


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
