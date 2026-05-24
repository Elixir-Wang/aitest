from __future__ import annotations

from sqlite3 import Connection, Row


BASE_SELECT = """
SELECT er.*, p.name AS project_name, pe.name AS environment_name, pe.site_url AS environment_site_url
FROM exploration_runs er
JOIN projects p ON p.id = er.project_id
JOIN project_environments pe ON pe.id = er.environment_id
"""


def list_by_project(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        f"""
        {BASE_SELECT}
        WHERE er.project_id = ?
        ORDER BY er.updated_at DESC, er.created_at DESC
        """,
        (project_id,),
    ).fetchall()


def list_visible(db: Connection, actor: Row) -> list[Row]:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return db.execute(
            f"""
            {BASE_SELECT}
            WHERE p.status != 'archived'
            ORDER BY er.updated_at DESC, er.created_at DESC
            """
        ).fetchall()

    return db.execute(
        f"""
        {BASE_SELECT}
        WHERE p.status != 'archived' AND p.name = ?
        ORDER BY er.updated_at DESC, er.created_at DESC
        """,
        (actor["project_scope"],),
    ).fetchall()


def find_by_id(db: Connection, run_id: str) -> Row | None:
    return db.execute(f"{BASE_SELECT} WHERE er.id = ?", (run_id,)).fetchone()


def create(
    db: Connection,
    *,
    run_id: str,
    project_id: str,
    environment_id: str,
    title: str,
    scope: str,
    forbidden_paths: str,
    login_strategy: str,
    description: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO exploration_runs
          (id, project_id, environment_id, title, scope, forbidden_paths, login_strategy, description, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, project_id, environment_id, title, scope, forbidden_paths, login_strategy, description, created_by),
    )


def delete(db: Connection, run_id: str) -> None:
    db.execute("DELETE FROM exploration_runs WHERE id = ?", (run_id,))


def update_run_state(
    db: Connection,
    run_id: str,
    *,
    status: str,
    artifact_root: str | None = None,
    result_summary: str | None = None,
    started: bool = False,
    finished: bool = False,
) -> None:
    assignments = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    values: list[object] = [status]
    if artifact_root is not None:
        assignments.append("artifact_root = ?")
        values.append(artifact_root)
    if result_summary is not None:
        assignments.append("result_summary = ?")
        values.append(result_summary)
    if started:
        assignments.append("started_at = COALESCE(started_at, CURRENT_TIMESTAMP)")
    if finished:
        assignments.append("finished_at = CURRENT_TIMESTAMP")
    values.append(run_id)
    db.execute(f"UPDATE exploration_runs SET {', '.join(assignments)} WHERE id = ?", values)


def clear_run_outputs(db: Connection, run_id: str) -> None:
    for table in (
        "exploration_document_versions",
        "exploration_artifacts",
        "exploration_blockers",
        "exploration_elements",
        "exploration_pages",
        "exploration_module_coverages",
    ):
        db.execute(f"DELETE FROM {table} WHERE exploration_run_id = ?", (run_id,))


def create_module_coverage(
    db: Connection,
    *,
    coverage_id: str,
    exploration_run_id: str,
    module_key: str,
    module_name: str,
    entry_path: str,
    planned_page_count: int,
    explored_page_count: int,
    blocked_page_count: int,
    action_count: int,
    field_count: int,
    state_transition_count: int,
    completion_status: str,
    completion_summary: str,
) -> None:
    db.execute(
        """
        INSERT INTO exploration_module_coverages
          (id, exploration_run_id, module_key, module_name, entry_path, planned_page_count, explored_page_count,
           blocked_page_count, action_count, field_count, state_transition_count, completion_status, completion_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            coverage_id,
            exploration_run_id,
            module_key,
            module_name,
            entry_path,
            planned_page_count,
            explored_page_count,
            blocked_page_count,
            action_count,
            field_count,
            state_transition_count,
            completion_status,
            completion_summary,
        ),
    )


def create_page(
    db: Connection,
    *,
    page_id: str,
    exploration_run_id: str,
    module_key: str,
    title: str,
    url: str,
    entry_path: str,
    structure_summary: str,
    screenshot_path: str = "",
    snapshot_path: str = "",
    trace_path: str = "",
) -> None:
    db.execute(
        """
        INSERT INTO exploration_pages
          (id, exploration_run_id, module_key, title, url, entry_path, structure_summary, screenshot_path, snapshot_path, trace_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (page_id, exploration_run_id, module_key, title, url, entry_path, structure_summary, screenshot_path, snapshot_path, trace_path),
    )


def create_element(
    db: Connection,
    *,
    element_id: str,
    exploration_run_id: str,
    page_id: str | None,
    module_key: str,
    element_name: str,
    element_type: str,
    recommended_locator: str,
    fallback_locator: str,
    stability_note: str,
    source_ref: str,
) -> None:
    db.execute(
        """
        INSERT INTO exploration_elements
          (id, exploration_run_id, page_id, module_key, element_name, element_type, recommended_locator,
           fallback_locator, stability_note, source_ref)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            element_id,
            exploration_run_id,
            page_id,
            module_key,
            element_name,
            element_type,
            recommended_locator,
            fallback_locator,
            stability_note,
            source_ref,
        ),
    )


def create_blocker(
    db: Connection,
    *,
    blocker_id: str,
    exploration_run_id: str,
    module_key: str,
    page_ref: str,
    reason_type: str,
    reason: str,
    evidence_path: str,
    impact_scope: str,
    suggested_action: str,
    is_blocking: bool = True,
) -> None:
    db.execute(
        """
        INSERT INTO exploration_blockers
          (id, exploration_run_id, module_key, page_ref, reason_type, reason, evidence_path, impact_scope, suggested_action, is_blocking)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            blocker_id,
            exploration_run_id,
            module_key,
            page_ref,
            reason_type,
            reason,
            evidence_path,
            impact_scope,
            suggested_action,
            1 if is_blocking else 0,
        ),
    )


def create_artifact(
    db: Connection,
    *,
    artifact_id: str,
    exploration_run_id: str,
    artifact_type: str,
    file_path: str,
    title: str,
    summary: str,
) -> None:
    db.execute(
        """
        INSERT INTO exploration_artifacts
          (id, exploration_run_id, artifact_type, file_path, title, summary)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (artifact_id, exploration_run_id, artifact_type, file_path, title, summary),
    )


def create_document_version(
    db: Connection,
    *,
    version_id: str,
    exploration_run_id: str,
    version_no: int,
    markdown_path: str,
    change_summary: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO exploration_document_versions
          (id, exploration_run_id, version_no, markdown_path, change_summary, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (version_id, exploration_run_id, version_no, markdown_path, change_summary, created_by),
    )
