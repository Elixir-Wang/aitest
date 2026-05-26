from __future__ import annotations

import json
from sqlite3 import Connection, Row


def list_builds(db: Connection, project_id: str) -> list[Row]:
    return db.execute(
        """
        SELECT kb.*,
               COUNT(DISTINCT wp.id) AS page_count,
               COUNT(DISTINCT ki.id) AS item_count,
               COUNT(DISTINCT li.id) AS lint_count
        FROM knowledge_builds kb
        LEFT JOIN wiki_pages wp ON wp.build_id = kb.id
        LEFT JOIN knowledge_items ki ON ki.build_id = kb.id
        LEFT JOIN wiki_lint_issues li ON li.build_id = kb.id
        WHERE kb.project_id = ?
        GROUP BY kb.id
        ORDER BY kb.created_at DESC
        """,
        (project_id,),
    ).fetchall()


def find_build(db: Connection, project_id: str, build_id: str) -> Row | None:
    return db.execute(
        "SELECT * FROM knowledge_builds WHERE project_id = ? AND id = ?",
        (project_id, build_id),
    ).fetchone()


def next_build_no(db: Connection, project_id: str) -> str:
    row = db.execute(
        "SELECT COUNT(*) + 1 AS next_no FROM knowledge_builds WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    return f"KB-{int(row['next_no']):03d}"


def create_build(
    db: Connection,
    *,
    build_id: str,
    project_id: str,
    build_no: str,
    status: str,
    build_type: str,
    source_document_version_ids: list[str],
    exploration_run_ids: list[str],
    output_dir: str,
    summary: str,
    change_summary: str,
    blockers: list[str],
    affected_modules: list[str],
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO knowledge_builds
          (id, project_id, build_no, status, build_type, source_document_version_ids, exploration_run_ids,
           output_dir, summary, change_summary, blockers_json, affected_modules_json, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            build_id,
            project_id,
            build_no,
            status,
            build_type,
            json.dumps(source_document_version_ids, ensure_ascii=False),
            json.dumps(exploration_run_ids, ensure_ascii=False),
            output_dir,
            summary,
            change_summary,
            json.dumps(blockers, ensure_ascii=False),
            json.dumps(affected_modules, ensure_ascii=False),
            created_by,
        ),
    )


def publish_build(db: Connection, project_id: str, build_id: str) -> None:
    db.execute(
        """
        UPDATE knowledge_builds
        SET status = 'published', published_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE project_id = ? AND id = ?
        """,
        (project_id, build_id),
    )


def list_pages(db: Connection, build_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM wiki_pages WHERE build_id = ? ORDER BY sort_order ASC, relative_path ASC",
        (build_id,),
    ).fetchall()


def find_page(db: Connection, build_id: str, page_id: str) -> Row | None:
    return db.execute(
        "SELECT * FROM wiki_pages WHERE build_id = ? AND id = ?",
        (build_id, page_id),
    ).fetchone()


def create_page(
    db: Connection,
    *,
    page_id: str,
    build_id: str,
    title: str,
    relative_path: str,
    page_type: str,
    module_key: str,
    summary: str,
    file_path: str,
    source_refs: list[dict],
    sort_order: int,
) -> None:
    db.execute(
        """
        INSERT INTO wiki_pages
          (id, build_id, title, relative_path, page_type, module_key, summary, file_path, source_refs_json, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            page_id,
            build_id,
            title,
            relative_path,
            page_type,
            module_key,
            summary,
            file_path,
            json.dumps(source_refs, ensure_ascii=False),
            sort_order,
        ),
    )


def create_item(
    db: Connection,
    *,
    item_id: str,
    build_id: str,
    module_key: str,
    module_name: str,
    knowledge_type: str,
    content: str,
    source_refs: list[dict],
) -> None:
    db.execute(
        """
        INSERT INTO knowledge_items
          (id, build_id, module_key, module_name, knowledge_type, content, source_refs_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (item_id, build_id, module_key, module_name, knowledge_type, content, json.dumps(source_refs, ensure_ascii=False)),
    )


def list_lint_issues(db: Connection, build_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM wiki_lint_issues WHERE build_id = ? ORDER BY created_at ASC",
        (build_id,),
    ).fetchall()


def create_lint_issue(
    db: Connection,
    *,
    issue_id: str,
    build_id: str,
    severity: str,
    title: str,
    detail: str,
    page_id: str,
) -> None:
    db.execute(
        """
        INSERT INTO wiki_lint_issues (id, build_id, severity, title, detail, page_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (issue_id, build_id, severity, title, detail, page_id),
    )


def list_source_references(db: Connection, build_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM source_references WHERE build_id = ? ORDER BY source_type ASC, source_title ASC",
        (build_id,),
    ).fetchall()


def create_source_reference(
    db: Connection,
    *,
    ref_id: str,
    build_id: str,
    source_type: str,
    source_id: str,
    source_title: str,
    location: str,
    excerpt: str,
) -> None:
    db.execute(
        """
        INSERT INTO source_references
          (id, build_id, source_type, source_id, source_title, location, excerpt)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (ref_id, build_id, source_type, source_id, source_title, location, excerpt),
    )
