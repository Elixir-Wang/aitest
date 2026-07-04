"""document 子包序列化器。

集中所有 ``_serialize_*`` 工具，与业务流解耦，方便后续在 router / 异步流中复用。
"""
from __future__ import annotations

import json

from app.agents.requirement_analysis.service import normalize_analysis_output_markdown


def serialize_requirement_analysis(row) -> dict:
    output = normalize_analysis_output_markdown(json.loads(row["output_json"]))
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "document_id": row["document_id"],
        "version_id": row["version_id"],
        "primary_mapping_id": row["primary_mapping_id"],
        "status": row["status"],
        "analysis_summary": row["analysis_summary"],
        "quality_result": row["quality_result"],
        "draft_content_hash": row["draft_content_hash"],
        "finalized_version_id": row["finalized_version_id"],
        "finalized_at": row["finalized_at"],
        "finalized_by": row["finalized_by"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "output": output,
    }


def serialize_requirement_analysis_run(row) -> dict:
    output = analysis_run_output(row)
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "document_id": row["document_id"],
        "analysis_id": row["analysis_id"],
        "status": row["status"],
        "summary": row["summary"],
        "failure_reason": row["failure_reason"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "has_understanding": bool(str(output.get("understanding_markdown") or "").strip()),
    }


def analysis_run_output(row) -> dict:
    raw_output = row["analysis_output_json"] if "analysis_output_json" in row.keys() else ""
    if not raw_output:
        return {}
    try:
        output = json.loads(raw_output)
    except json.JSONDecodeError:
        return {}
    return normalize_analysis_output_markdown(output) if isinstance(output, dict) else {}


def serialize_requirement_clarification_answer(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "document_id": row["document_id"],
        "analysis_id": row["analysis_id"],
        "question_id": row["question_id"],
        "answer_type": row["answer_type"],
        "selected_option_id": row["selected_option_id"],
        "answer_markdown": row["answer_markdown"],
        "user_note": row["user_note"],
        "apply_status": row["apply_status"],
        "insertion_anchor": row["insertion_anchor"],
        "failure_reason": row["failure_reason"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_version(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "version_no": row["version_no"],
        "file_path": row["file_path"],
        "source_action": row["source_action"],
        "change_summary": row["change_summary"],
        "diff_summary": row["diff_summary"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }