from sqlite3 import Connection, Row


def upsert_answer(
    db: Connection,
    *,
    answer_id: str,
    project_id: str,
    document_id: str,
    analysis_id: str,
    question_id: str,
    answer_type: str,
    selected_option_id: str,
    answer_markdown: str,
    user_note: str,
    apply_status: str,
    insertion_anchor: str,
    failure_reason: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO requirement_clarification_answers
          (id, project_id, document_id, analysis_id, question_id, answer_type, selected_option_id,
           answer_markdown, user_note, apply_status, insertion_anchor, failure_reason, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(analysis_id, question_id) DO UPDATE SET
          answer_type = excluded.answer_type,
          selected_option_id = excluded.selected_option_id,
          answer_markdown = excluded.answer_markdown,
          user_note = excluded.user_note,
          apply_status = excluded.apply_status,
          insertion_anchor = excluded.insertion_anchor,
          failure_reason = excluded.failure_reason,
          updated_at = CURRENT_TIMESTAMP
        """,
        (
            answer_id,
            project_id,
            document_id,
            analysis_id,
            question_id,
            answer_type,
            selected_option_id,
            answer_markdown,
            user_note,
            apply_status,
            insertion_anchor,
            failure_reason,
            created_by,
        ),
    )


def find_answer(db: Connection, analysis_id: str, question_id: str) -> Row | None:
    return db.execute(
        """
        SELECT *
        FROM requirement_clarification_answers
        WHERE analysis_id = ? AND question_id = ?
        """,
        (analysis_id, question_id),
    ).fetchone()


def list_answers(db: Connection, analysis_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT *
        FROM requirement_clarification_answers
        WHERE analysis_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (analysis_id,),
    ).fetchall()
