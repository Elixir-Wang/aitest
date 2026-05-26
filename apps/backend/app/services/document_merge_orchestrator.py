from __future__ import annotations

import json
import secrets
from pathlib import Path

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import project_requirement_dir, resolve_stored_path, store_path
from app.repositories import document_repo
from app.schemas.requirement_merge import (
    RequirementMergeBaseVersion,
    RequirementMergeResolvedConflict,
    RequirementMergeSourceFile,
)
from app.services import requirement_fragment_service, requirement_merge_artifact_service, requirement_merge_service

DOCUMENT_VERSIONED_STATUS = "versioned"
CONVERSION_SUCCESS_STATUS = "success"


async def merge_document_markdown(
    project_id: str,
    document_id: str,
    actor,
    *,
    confirm_preview_id: str = "",
    force_rebuild: bool = False,
) -> dict:
    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        if confirm_preview_id.strip():
            return _confirm_merge_preview(db, project_id, document_id, confirm_preview_id.strip(), actor)
        files = [
            row
            for row in document_repo.list_file_mappings(db, document_id)
            if row["conversion_status"] in {CONVERSION_SUCCESS_STATUS, "warning"} and row["mapping_status"] != "discarded"
        ]
        if not files:
            raise api_error(409, "DOCUMENT_MERGE_NO_FILES", "暂无可合并的标准文件。")

        open_conflicts = document_repo.list_conflicts(db, document_id, status="open")
        if open_conflicts:
            return {
                "status": "conflict",
                "conflict_count": len(open_conflicts),
                "conflicts": [_serialize_conflict(row) for row in open_conflicts],
            }

        source_files: list[RequirementMergeSourceFile] = []
        for file_row in files:
            markdown_path_value = file_row["markdown_file_path"]
            if not markdown_path_value:
                continue
            markdown_path = resolve_stored_path(markdown_path_value) or Path(markdown_path_value)
            if not markdown_path.exists():
                continue
            source_files.append(
                RequirementMergeSourceFile(
                    mapping_id=file_row["id"],
                    original_filename=file_row["original_filename"],
                    markdown_content=markdown_path.read_text(encoding="utf-8"),
                    conversion_status=file_row["conversion_status"],
                    mapping_status=file_row["mapping_status"],
                )
            )
        if not source_files:
            raise api_error(409, "DOCUMENT_MERGE_NO_FILES", "暂无可合并的标准文件。")
        source_fragments = requirement_fragment_service.build_source_fragments(source_files)

        base_version = _current_merge_base_version(existing)
        resolved_conflicts = document_repo.list_conflicts(db, document_id, status="resolved")
        merge_mode = requirement_merge_service.detect_merge_mode(existing["current_version_id"], force_rebuild=force_rebuild)
        merge_input = requirement_merge_service.build_merge_input(
            project_id=project_id,
            document_id=document_id,
            document_name=existing["name"],
            merge_mode=merge_mode,
            base_version=base_version,
            source_files=source_files,
            resolved_conflicts=[
                RequirementMergeResolvedConflict(
                    id=row["id"],
                    title=row["title"],
                    resolution=row["resolution"],
                    resolution_type=row["resolution_type"],
                )
                for row in resolved_conflicts
            ],
        )
        run_id = f"mergerun-{secrets.token_hex(8)}"
        document_repo.create_merge_run(
            db,
            run_id=run_id,
            project_id=project_id,
            document_id=document_id,
            base_version_id=existing["current_version_id"],
            merge_mode=merge_mode,
            status="running",
            input_mapping_ids=[item.mapping_id for item in source_files],
            resolved_conflict_ids=[row["id"] for row in resolved_conflicts],
            created_by=actor["id"],
        )
        machine_artifacts = requirement_merge_artifact_service.write_merge_machine_artifacts(
            project_id,
            document_id,
            run_id,
            source_fragments=source_fragments,
        )
        try:
            merge_output = await requirement_merge_service.run_requirement_merge(merge_input)
        except Exception as exc:
            failure_message = f"需求归并智能体运行失败：{exc}"
            failure_preview = requirement_merge_artifact_service.blocked_preview_markdown(
                existing["name"],
                failure_message,
            )
            artifact_tabs = requirement_merge_artifact_service.write_merge_artifacts(
                project_id,
                document_id,
                run_id,
                preview_markdown=failure_preview,
                coverage_items=[],
                conflicts=[],
                merge_summary=failure_message,
                diff_summary="智能体运行失败，未生成合并需求稿。",
                affected_modules=[],
                source_files=source_files,
                quality_result="failed",
                blocking_issues=[failure_message],
            )
            document_repo.update_merge_run_result(
                db,
                run_id=run_id,
                status="failed",
                merge_summary=failure_message,
                diff_summary="智能体运行失败，未生成合并需求稿。",
                affected_modules=[],
                output_preview_path=artifact_tabs[0]["stored_path"],
            )
            return {
                "status": "preview",
                "preview_id": run_id,
                "markdown_preview": failure_preview,
                "merge_summary": failure_message,
                "diff_summary": "智能体运行失败，未生成合并需求稿。",
                "affected_modules": [],
                "source_file_ids": [item.mapping_id for item in source_files],
                "quality_result": "failed",
                "artifact_tabs": requirement_merge_artifact_service.public_artifact_tabs(artifact_tabs),
                "machine_artifacts": machine_artifacts,
            }
        coverage_items = [item.model_dump() for item in merge_output.coverage_items]
        if merge_output.status == "conflict":
            for conflict in merge_output.conflicts:
                source_file_names = "、".join(
                    Path(str(ref.get("filename", ""))).stem for ref in conflict.source_refs if ref.get("filename")
                )
                document_repo.create_conflict(
                    db,
                    conflict_id=f"conflict-{secrets.token_hex(8)}",
                    run_id=run_id,
                    document_id=document_id,
                    title=conflict.title,
                    conflict_type=conflict.conflict_type,
                    severity=conflict.severity,
                    source_refs=conflict.source_refs,
                    source_file_names=source_file_names,
                    fragment_a=conflict.fragment_a,
                    fragment_b=conflict.fragment_b,
                    agent_suggestion=conflict.agent_suggestion,
                )
            document_repo.update_merge_run_result(
                db,
                run_id=run_id,
                status="conflict",
                merge_summary=merge_output.merge_summary,
                diff_summary=merge_output.diff_summary,
                affected_modules=merge_output.affected_modules,
            )
            conflict_rows = document_repo.list_conflicts(db, document_id, status="open")
            document_repo.create_source_coverage_items(
                db,
                run_id=run_id,
                document_id=document_id,
                version_id=None,
                items=coverage_items,
            )
            return {
                "status": "conflict",
                "run_id": run_id,
                "merge_summary": merge_output.merge_summary,
                "diff_summary": merge_output.diff_summary,
                "affected_modules": merge_output.affected_modules,
                "source_file_ids": merge_output.source_file_ids,
                "conflict_count": len(conflict_rows),
                "conflicts": [_serialize_conflict(row) for row in conflict_rows],
                "machine_artifacts": machine_artifacts,
            }

        if merge_output.status == "preview":
            quality_result, blocking_issues = requirement_merge_artifact_service.evaluate_merge_quality(
                coverage_items,
                [],
                merge_output.markdown_preview,
                source_files,
                merge_output.merge_summary,
            )
            artifact_tabs = requirement_merge_artifact_service.write_merge_artifacts(
                project_id,
                document_id,
                run_id,
                preview_markdown=merge_output.markdown_preview,
                coverage_items=coverage_items,
                conflicts=[],
                merge_summary=merge_output.merge_summary,
                diff_summary=merge_output.diff_summary,
                affected_modules=merge_output.affected_modules,
                source_files=source_files,
                quality_result=quality_result,
                blocking_issues=blocking_issues,
            )
            document_repo.create_source_coverage_items(
                db,
                run_id=run_id,
                document_id=document_id,
                version_id=None,
                items=coverage_items,
            )
            document_repo.update_merge_run_result(
                db,
                run_id=run_id,
                status="preview",
                merge_summary=merge_output.merge_summary,
                diff_summary=merge_output.diff_summary,
                affected_modules=merge_output.affected_modules,
                output_preview_path=artifact_tabs[0]["stored_path"],
            )
            return {
                "status": "preview",
                "preview_id": run_id,
                "markdown_preview": merge_output.markdown_preview,
                "merge_summary": merge_output.merge_summary,
                "diff_summary": merge_output.diff_summary,
                "affected_modules": merge_output.affected_modules,
                "source_file_ids": merge_output.source_file_ids,
                "quality_result": artifact_tabs[3]["quality_result"],
                "artifact_tabs": requirement_merge_artifact_service.public_artifact_tabs(artifact_tabs),
                "machine_artifacts": machine_artifacts,
            }

        merged_markdown = merge_output.markdown_content
        quality_result, blocking_issues = requirement_merge_artifact_service.evaluate_merge_quality(
            coverage_items,
            [],
            merged_markdown,
            source_files,
            merge_output.merge_summary,
        )
        artifact_tabs = requirement_merge_artifact_service.write_merge_artifacts(
            project_id,
            document_id,
            run_id,
            preview_markdown=merged_markdown,
            coverage_items=coverage_items,
            conflicts=[],
            merge_summary=merge_output.merge_summary,
            diff_summary=merge_output.diff_summary,
            affected_modules=merge_output.affected_modules,
            source_files=source_files,
            quality_result=quality_result,
            blocking_issues=blocking_issues,
        )
        if quality_result == "failed":
            document_repo.create_source_coverage_items(
                db,
                run_id=run_id,
                document_id=document_id,
                version_id=None,
                items=coverage_items,
            )
            document_repo.update_merge_run_result(
                db,
                run_id=run_id,
                status="preview",
                merge_summary=merge_output.merge_summary,
                diff_summary=merge_output.diff_summary,
                affected_modules=merge_output.affected_modules,
                output_preview_path=artifact_tabs[0]["stored_path"],
            )
            return {
                "status": "preview",
                "preview_id": run_id,
                "markdown_preview": merged_markdown,
                "merge_summary": merge_output.merge_summary,
                "diff_summary": merge_output.diff_summary,
                "affected_modules": merge_output.affected_modules,
                "source_file_ids": merge_output.source_file_ids,
                "quality_result": quality_result,
                "artifact_tabs": requirement_merge_artifact_service.public_artifact_tabs(artifact_tabs),
                "machine_artifacts": machine_artifacts,
            }
        version_id = f"docver-{secrets.token_hex(8)}"
        version_no = document_repo.next_version_no(db, document_id)
        markdown_path = _version_markdown_path(project_id, document_id, version_no)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(merged_markdown, encoding="utf-8")
        document_repo.create_version(
            db,
            version_id=version_id,
            document_id=document_id,
            version_no=version_no,
            file_path=store_path(markdown_path) or str(markdown_path),
            source_action="merge",
            change_summary=merge_output.merge_summary,
            diff_summary=merge_output.diff_summary or f"归并 {len(source_files)} 个标准文件。",
            created_by=actor["id"],
        )
        document_repo.create_source_coverage_items(
            db,
            run_id=run_id,
            document_id=document_id,
            version_id=version_id,
            items=coverage_items,
        )
        document_repo.create_document_version_change_log(
            db,
            log_id=f"changelog-{secrets.token_hex(8)}",
            document_id=document_id,
            version_id=version_id,
            source_action="merge",
            change_summary=merge_output.merge_summary,
            diff_summary=merge_output.diff_summary,
            affected_modules=merge_output.affected_modules,
            source_mapping_ids=merge_output.source_file_ids,
            created_by=actor["id"],
        )
        document_repo.mark_file_mappings_merged(db, document_id, version_id)
        document_repo.close_open_conflicts(db, document_id)
        document_repo.update_current_version(db, document_id, version_id, DOCUMENT_VERSIONED_STATUS)
        document_repo.update_merge_run_result(
            db,
            run_id=run_id,
            status="merged",
            merge_summary=merge_output.merge_summary,
            diff_summary=merge_output.diff_summary,
            affected_modules=merge_output.affected_modules,
            output_version_id=version_id,
        )

    return {
        "status": "merged",
        "version_id": version_id,
        "version_no": version_no,
        "markdown_content": merged_markdown,
        "merge_summary": merge_output.merge_summary,
        "diff_summary": merge_output.diff_summary,
        "affected_modules": merge_output.affected_modules,
        "source_file_ids": merge_output.source_file_ids,
        "quality_result": quality_result,
        "artifact_tabs": requirement_merge_artifact_service.public_artifact_tabs(artifact_tabs),
        "machine_artifacts": machine_artifacts,
    }


def _confirm_merge_preview(db, project_id: str, document_id: str, run_id: str, actor) -> dict:
    merge_run = document_repo.find_merge_run(db, run_id)
    if not merge_run or merge_run["document_id"] != document_id:
        raise api_error(404, "DOCUMENT_MERGE_PREVIEW_NOT_FOUND", "归并预览不存在。")
    if merge_run["status"] != "preview":
        raise api_error(409, "DOCUMENT_MERGE_PREVIEW_INVALID", "归并预览状态不可确认。")
    preview_path_value = merge_run["output_preview_path"]
    if not preview_path_value:
        raise api_error(404, "DOCUMENT_MERGE_PREVIEW_NOT_FOUND", "归并预览文件不存在。")
    preview_path = resolve_stored_path(preview_path_value) or Path(preview_path_value)
    if not preview_path.exists():
        raise api_error(404, "DOCUMENT_MERGE_PREVIEW_NOT_FOUND", "归并预览文件不存在。")

    merged_markdown = preview_path.read_text(encoding="utf-8")
    version_id = f"docver-{secrets.token_hex(8)}"
    version_no = document_repo.next_version_no(db, document_id)
    markdown_path = _version_markdown_path(project_id, document_id, version_no)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(merged_markdown, encoding="utf-8")

    change_summary = merge_run["merge_summary"]
    diff_summary = merge_run["diff_summary"]
    affected_modules = _json_list(merge_run["affected_modules"])
    source_mapping_ids = _json_list(merge_run["input_mapping_ids"])
    document_repo.create_version(
        db,
        version_id=version_id,
        document_id=document_id,
        version_no=version_no,
        file_path=store_path(markdown_path) or str(markdown_path),
        source_action="merge",
        change_summary=change_summary,
        diff_summary=diff_summary,
        created_by=actor["id"],
    )
    document_repo.create_document_version_change_log(
        db,
        log_id=f"changelog-{secrets.token_hex(8)}",
        document_id=document_id,
        version_id=version_id,
        source_action="merge",
        change_summary=change_summary,
        diff_summary=diff_summary,
        affected_modules=affected_modules,
        source_mapping_ids=source_mapping_ids,
        created_by=actor["id"],
    )
    document_repo.mark_file_mappings_merged(db, document_id, version_id)
    document_repo.update_current_version(db, document_id, version_id, DOCUMENT_VERSIONED_STATUS)
    document_repo.update_merge_run_result(
        db,
        run_id=run_id,
        status="merged",
        merge_summary=change_summary,
        diff_summary=diff_summary,
        affected_modules=affected_modules,
        output_version_id=version_id,
        output_preview_path=preview_path_value,
    )
    return {
        "status": "merged",
        "version_id": version_id,
        "version_no": version_no,
        "markdown_content": merged_markdown,
        "merge_summary": change_summary,
        "diff_summary": diff_summary,
        "affected_modules": affected_modules,
        "source_file_ids": source_mapping_ids,
    }


def list_document_conflicts(project_id: str, document_id: str, actor) -> list[dict]:
    _ = actor
    with connect() as db:
        if not document_repo.find_by_project_and_id(db, project_id, document_id):
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        return [_serialize_conflict(row) for row in document_repo.list_conflicts(db, document_id, status="open")]


def resolve_document_conflict(
    project_id: str,
    document_id: str,
    conflict_id: str,
    *,
    resolution: str,
    resolution_type: str,
    actor,
) -> dict:
    _ = actor
    with connect() as db:
        if not document_repo.find_by_project_and_id(db, project_id, document_id):
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        document_repo.resolve_conflict(db, conflict_id, resolution.strip(), resolution_type)
        open_conflicts = document_repo.list_conflicts(db, document_id, status="open")
        return {"success": True, "has_open_conflicts": len(open_conflicts) > 0}


def _current_merge_base_version(row) -> RequirementMergeBaseVersion | None:
    if not row["current_version_id"]:
        return None
    version_id = row["current_version_id"]
    version_no = row["version_no"] if "version_no" in row.keys() and row["version_no"] else 0
    file_path = row["markdown_file_path"] if "markdown_file_path" in row.keys() else ""
    markdown_content = ""
    if file_path:
        path = resolve_stored_path(file_path) or Path(file_path)
        if path.exists():
            markdown_content = path.read_text(encoding="utf-8")
    return RequirementMergeBaseVersion(id=version_id, version_no=version_no, markdown_content=markdown_content)


def _serialize_conflict(row) -> dict:
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "title": row["title"],
        "conflict_type": row["conflict_type"] if "conflict_type" in row.keys() else "contradiction",
        "severity": row["severity"] if "severity" in row.keys() else "medium",
        "source_refs": row["source_refs"] if "source_refs" in row.keys() else "[]",
        "source_file_names": row["source_file_names"],
        "fragment_a": row["fragment_a"],
        "fragment_b": row["fragment_b"],
        "agent_suggestion": row["agent_suggestion"] if "agent_suggestion" in row.keys() else "",
        "resolution": row["resolution"],
        "resolution_type": row["resolution_type"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _version_markdown_path(project_id: str, document_id: str, version_no: int) -> Path:
    return project_requirement_dir(project_id, document_id) / "versions" / f"v{version_no}.md"
