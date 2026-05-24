from __future__ import annotations

from sqlite3 import Connection

from app.core.storage import expose_stored_path

CONVERSION_FAILED_STATUS = "failed"


def serialize_document(row, actor_role: str) -> dict:
    current_version = None
    if row["version_id"]:
        current_version = {
            "id": row["version_id"],
            "version_no": row["version_no"],
            "file_path": expose_stored_path(row["markdown_file_path"]) or row["markdown_file_path"],
            "source_action": row["source_action"],
            "change_summary": row["change_summary"],
            "diff_summary": row["diff_summary"],
            "created_by": row["version_created_by"],
            "created_at": row["version_created_at"],
        }

    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "document_type": row["document_type"],
        "file_count": row["file_count"] if "file_count" in row.keys() else 0,
        "current_version_id": row["current_version_id"],
        "status": row["status"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "current_version": current_version,
        "available_actions": ["read", "create", "update", "delete"] if actor_role == "admin" else ["read", "create"],
    }


def serialize_file_mapping(row) -> dict:
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "version_id": row["version_id"],
        "version_no": row["version_no"] if "version_no" in row.keys() else None,
        "original_filename": row["original_filename"],
        "file_format": row["file_format"],
        "source_file_path": expose_stored_path(row["source_file_path"]) or row["source_file_path"],
        "markdown_file_path": expose_stored_path(row["markdown_file_path"]) or row["markdown_file_path"],
        "preview_file_path": expose_stored_path(row["preview_file_path"]) if "preview_file_path" in row.keys() else None,
        "conversion_status": row["conversion_status"],
        "mapping_status": row["mapping_status"],
        "conversion_summary": row["conversion_summary"],
        "conversion_quality": row["conversion_quality"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


def standard_file_status(row) -> str:
    if row["conversion_status"] == CONVERSION_FAILED_STATUS:
        return "failed"
    if not row["markdown_file_path"]:
        return "generating"
    summary = row["conversion_summary"] or ""
    if "人工修订" in summary:
        return "edited"
    return "ready"


def serialize_document_from_db(db: Connection, document_id: str, actor_role: str) -> dict:
    row = db.execute(
        """
        SELECT d.*,
               COUNT(m.id) AS file_count,
               v.id AS version_id,
               v.version_no AS version_no,
               v.file_path AS markdown_file_path,
               v.source_action AS source_action,
               v.change_summary AS change_summary,
               v.diff_summary AS diff_summary,
               v.created_by AS version_created_by,
               v.created_at AS version_created_at
        FROM source_documents d
        LEFT JOIN source_document_versions v ON v.id = d.current_version_id
        LEFT JOIN source_document_file_mappings m ON m.document_id = d.id
        WHERE d.id = ?
        GROUP BY d.id
        """,
        (document_id,),
    ).fetchone()
    return serialize_document(row, actor_role)
