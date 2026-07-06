from sqlite3 import Connection, Row


BASE_SET_SELECT = """
SELECT tcs.*,
       p.name AS project_name,
       d.name AS requirement_doc_title
FROM test_case_sets tcs
JOIN projects p ON p.id = tcs.project_id
JOIN source_documents d ON d.id = tcs.requirement_doc_id
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


def list_cases_by_set(db: Connection, test_case_set_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM test_cases
        WHERE test_case_set_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (test_case_set_id,),
    ).fetchall()


def find_case_by_id(db: Connection, case_id: str) -> Row | None:
    return db.execute("SELECT * FROM test_cases WHERE id = ?", (case_id,)).fetchone()


def update_case_review(
    db: Connection,
    *,
    case_id: str,
    status: str,
    review_feedback: str,
    reviewed_by: str,
    preconditions: str | None = None,
    steps_json: str | None = None,
    expected_result: str | None = None,
) -> None:
    content_assignments = []
    content_params = []
    if preconditions is not None:
        content_assignments.append("preconditions = ?")
        content_params.append(preconditions)
    if steps_json is not None:
        content_assignments.append("steps_json = ?")
        content_params.append(steps_json)
    if expected_result is not None:
        content_assignments.append("expected_result = ?")
        content_params.append(expected_result)
    content_sql = ""
    if content_assignments:
        content_sql = ",\n                " + ",\n                ".join(content_assignments)

    if status == "ready_for_review":
        db.execute(
            f"""
            UPDATE test_cases
            SET status = 'ready_for_review',
                review_feedback = '',
                reviewed_by = '',
                reviewed_at = NULL,
                updated_at = CURRENT_TIMESTAMP
                {content_sql}
            WHERE id = ?
            """,
            (*content_params, case_id),
        )
        return

    db.execute(
        f"""
        UPDATE test_cases
        SET status = ?,
            review_feedback = ?,
            reviewed_by = ?,
            reviewed_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
            {content_sql}
        WHERE id = ?
        """,
        (status, review_feedback if status == "rejected" else "", reviewed_by, *content_params, case_id),
    )


def review_stats_by_set(db: Connection, test_case_set_id: str) -> dict:
    row = db.execute(
        """
        SELECT
          COUNT(*) AS case_count,
          SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved_count,
          SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected_count,
          SUM(CASE WHEN status = 'ready_for_review' THEN 1 ELSE 0 END) AS pending_count
        FROM test_cases
        WHERE test_case_set_id = ?
        """,
        (test_case_set_id,),
    ).fetchone()
    case_count = int(row["case_count"] or 0)
    approved_count = int(row["approved_count"] or 0)
    rejected_count = int(row["rejected_count"] or 0)
    pending_count = int(row["pending_count"] or 0)
    reviewed_count = approved_count + rejected_count
    return {
        "case_count": case_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "pending_count": pending_count,
        "reviewed_count": reviewed_count,
        "adoption_rate": approved_count / reviewed_count if reviewed_count else 0,
        "review_progress": reviewed_count / case_count if case_count else 0,
    }


def list_rejected_case_feedback_by_set(db: Connection, test_case_set_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT id, title, module, priority, preconditions, steps_json, expected_result, review_feedback
        FROM test_cases
        WHERE test_case_set_id = ?
          AND status = 'rejected'
        ORDER BY updated_at DESC, id ASC
        """,
        (test_case_set_id,),
    ).fetchall()


def find_generation_run(db: Connection, run_id: str) -> Row | None:
    return db.execute(
        """
        SELECT r.*, s.project_id, s.requirement_doc_id, s.name AS test_case_set_name,
               s.generation_scope_type, s.generation_scope_text
        FROM test_case_generation_runs r
        JOIN test_case_sets s ON s.id = r.test_case_set_id
        WHERE r.id = ?
        """,
        (run_id,),
    ).fetchone()


def list_active_generation_runs(db: Connection) -> list[Row]:
    return db.execute(
        """
        SELECT r.*, s.project_id, s.requirement_doc_id, s.name AS test_case_set_name,
               s.generation_scope_type, s.generation_scope_text
        FROM test_case_generation_runs r
        JOIN test_case_sets s ON s.id = r.test_case_set_id
        WHERE r.status IN ('queued', 'running')
        """
    ).fetchall()


def has_active_generation_run(db: Connection, test_case_set_id: str) -> bool:
    row = db.execute(
        """
        SELECT 1
        FROM test_case_generation_runs
        WHERE test_case_set_id = ?
          AND status IN ('queued', 'running')
        LIMIT 1
        """,
        (test_case_set_id,),
    ).fetchone()
    return row is not None


def delete_set(db: Connection, set_id: str) -> None:
    db.execute("DELETE FROM test_case_sets WHERE id = ?", (set_id,))


def create_set(
    db: Connection,
    *,
    set_id: str,
    project_id: str,
    name: str,
    requirement_doc_id: str,
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
            "",
            0,
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


def update_set_status(db: Connection, set_id: str, *, status: str) -> None:
    db.execute(
        """
        UPDATE test_case_sets
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, set_id),
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


