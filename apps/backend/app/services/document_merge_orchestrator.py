from __future__ import annotations

import secrets
from pathlib import Path

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import project_requirement_dir, resolve_stored_path, store_path
from app.repositories import document_repo
from app.schemas.requirement_merge import (
    OutlineMergeConflict,
    RequirementMergeBaseVersion,
    RequirementMergeConflictOut,
    RequirementMergeSourceFile,
)
from app.services import (
    requirement_fragment_service,
    requirement_merge_outline_service,
    requirement_merge_artifact_service,
    requirement_merge_quality_service,
    requirement_merge_render_service,
    requirement_outline_assignment_service,
    requirement_section_merge_service,
    requirement_source_block_service,
    requirement_source_outline_service,
)

DOCUMENT_VERSIONED_STATUS = "versioned"
CONVERSION_SUCCESS_STATUS = "success"


async def merge_document_markdown(
    project_id: str,
    document_id: str,
    actor,
    *,
    force_rebuild: bool = False,
) -> dict:
    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        files = [
            row
            for row in document_repo.list_file_mappings(db, document_id)
            if row["conversion_status"] in {CONVERSION_SUCCESS_STATUS, "warning"} and row["mapping_status"] != "discarded"
        ]
        files = sorted(files, key=lambda row: (row["created_at"], row["id"]))
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
        source_blocks = requirement_source_block_service.build_source_blocks(source_files)
        legacy_source_fragments = requirement_fragment_service.build_source_fragments(source_files)

        resolved_conflicts = document_repo.list_conflicts(db, document_id, status="resolved")
        merge_mode = _detect_merge_mode(existing["current_version_id"], force_rebuild=force_rebuild)
        base_version_id = existing["current_version_id"] if merge_mode == "incremental" else None
        run_id = f"mergerun-{secrets.token_hex(8)}"
        document_repo.create_merge_run(
            db,
            run_id=run_id,
            project_id=project_id,
            document_id=document_id,
            base_version_id=base_version_id,
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
            source_fragments=legacy_source_fragments,
            source_blocks=source_blocks,
        )
        try:
            outline_output = await _run_outline_merge(
                project_id=project_id,
                document_id=document_id,
                document_name=existing["name"],
                run_id=run_id,
                source_files=source_files,
                machine_artifacts=machine_artifacts,
                resolved_conflicts=[
                    {
                        "title": row["title"],
                        "resolution": row["resolution"],
                        "resolution_type": row["resolution_type"],
                    }
                    for row in resolved_conflicts
                ],
            )
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
                source_blocks=source_blocks,
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
        machine_artifacts.update(outline_output["machine_artifacts"])
        coverage_items = outline_output["coverage_items"]
        if outline_output["status"] == "conflict":
            for conflict in outline_output["conflicts"]:
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
                merge_summary=outline_output["merge_summary"],
                diff_summary=outline_output["diff_summary"],
                affected_modules=outline_output["affected_modules"],
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
                "merge_summary": outline_output["merge_summary"],
                "diff_summary": outline_output["diff_summary"],
                "affected_modules": outline_output["affected_modules"],
                "source_file_ids": outline_output["source_file_ids"],
                "conflict_count": len(conflict_rows),
                "conflicts": [_serialize_conflict(row) for row in conflict_rows],
                "machine_artifacts": machine_artifacts,
            }

        if outline_output["status"] == "preview":
            artifact_tabs = requirement_merge_artifact_service.write_merge_artifacts(
                project_id,
                document_id,
                run_id,
                preview_markdown=outline_output["markdown_preview"],
                coverage_items=coverage_items,
                conflicts=[],
                merge_summary=outline_output["merge_summary"],
                diff_summary=outline_output["diff_summary"],
                affected_modules=outline_output["affected_modules"],
                source_files=source_files,
                source_blocks=source_blocks,
                quality_result=outline_output["quality_result"],
                blocking_issues=outline_output["quality_issues"],
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
                merge_summary=outline_output["merge_summary"],
                diff_summary=outline_output["diff_summary"],
                affected_modules=outline_output["affected_modules"],
                output_preview_path=artifact_tabs[0]["stored_path"],
            )
            return {
                "status": "preview",
                "preview_id": run_id,
                "markdown_preview": outline_output["markdown_preview"],
                "merge_summary": outline_output["merge_summary"],
                "diff_summary": outline_output["diff_summary"],
                "affected_modules": outline_output["affected_modules"],
                "source_file_ids": outline_output["source_file_ids"],
                "quality_result": outline_output["quality_result"],
                "artifact_tabs": requirement_merge_artifact_service.public_artifact_tabs(artifact_tabs),
                "machine_artifacts": machine_artifacts,
            }

        merged_markdown = outline_output["markdown_content"]
        quality_result = outline_output["quality_result"]
        blocking_issues = outline_output["quality_issues"]
        artifact_tabs = requirement_merge_artifact_service.write_merge_artifacts(
            project_id,
            document_id,
            run_id,
            preview_markdown=merged_markdown,
            coverage_items=coverage_items,
            conflicts=[],
            merge_summary=outline_output["merge_summary"],
            diff_summary=outline_output["diff_summary"],
            affected_modules=outline_output["affected_modules"],
            source_files=source_files,
            source_blocks=source_blocks,
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
                merge_summary=outline_output["merge_summary"],
                diff_summary=outline_output["diff_summary"],
                affected_modules=outline_output["affected_modules"],
                output_preview_path=artifact_tabs[0]["stored_path"],
            )
            return {
                "status": "preview",
                "preview_id": run_id,
                "markdown_preview": merged_markdown,
                "merge_summary": outline_output["merge_summary"],
                "diff_summary": outline_output["diff_summary"],
                "affected_modules": outline_output["affected_modules"],
                "source_file_ids": outline_output["source_file_ids"],
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
            change_summary=outline_output["merge_summary"],
            diff_summary=outline_output["diff_summary"] or f"归并 {len(source_files)} 个标准文件。",
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
            change_summary=outline_output["merge_summary"],
            diff_summary=outline_output["diff_summary"],
            affected_modules=outline_output["affected_modules"],
            source_mapping_ids=outline_output["source_file_ids"],
            created_by=actor["id"],
        )
        document_repo.mark_file_mappings_merged(db, document_id, version_id)
        document_repo.close_open_conflicts(db, document_id)
        document_repo.update_current_version(db, document_id, version_id, DOCUMENT_VERSIONED_STATUS)
        document_repo.update_merge_run_result(
            db,
            run_id=run_id,
            status="merged",
            merge_summary=outline_output["merge_summary"],
            diff_summary=outline_output["diff_summary"],
            affected_modules=outline_output["affected_modules"],
            output_version_id=version_id,
        )

    return {
        "status": "merged",
        "version_id": version_id,
        "version_no": version_no,
        "markdown_content": merged_markdown,
        "merge_summary": outline_output["merge_summary"],
        "diff_summary": outline_output["diff_summary"],
        "affected_modules": outline_output["affected_modules"],
        "source_file_ids": outline_output["source_file_ids"],
        "quality_result": quality_result,
        "artifact_tabs": requirement_merge_artifact_service.public_artifact_tabs(artifact_tabs),
        "machine_artifacts": machine_artifacts,
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


async def _run_outline_merge(
    *,
    project_id: str,
    document_id: str,
    document_name: str,
    run_id: str,
    source_files: list[RequirementMergeSourceFile],
    machine_artifacts: dict[str, str],
    resolved_conflicts: list[dict] | None = None,
) -> dict:
    _ = machine_artifacts
    source_documents = requirement_source_outline_service.build_source_outline(source_files)
    target_outline, outline_errors, outline_debug = _unpack_stage_result(await requirement_merge_outline_service.generate_target_outline(
        document_name,
        source_documents,
    ))
    if outline_errors:
        return _failed_outline_stage_output(
            project_id=project_id,
            document_id=document_id,
            document_name=document_name,
            run_id=run_id,
            source_files=source_files,
            source_documents=source_documents,
            target_outline=target_outline,
            assignments=[],
            section_results=[],
            stage_errors=outline_errors,
            debug_artifacts=_outline_debug_artifacts(outline_debug),
        )
    assignments, assignment_errors, assignment_debug = _unpack_stage_result(await requirement_outline_assignment_service.assign_source_outline_to_target(
        source_documents,
        target_outline,
    ))
    if assignment_errors:
        return _failed_outline_stage_output(
            project_id=project_id,
            document_id=document_id,
            document_name=document_name,
            run_id=run_id,
            source_files=source_files,
            source_documents=source_documents,
            target_outline=target_outline,
            assignments=assignments,
            section_results=[],
            stage_errors=assignment_errors,
            debug_artifacts=_outline_debug_artifacts(outline_debug, assignment_debug),
        )
    section_results, section_errors = await requirement_section_merge_service.merge_sections_by_target_outline(
        source_documents,
        target_outline,
        assignments,
    )
    if section_errors:
        return _failed_outline_stage_output(
            project_id=project_id,
            document_id=document_id,
            document_name=document_name,
            run_id=run_id,
            source_files=source_files,
            source_documents=source_documents,
            target_outline=target_outline,
            assignments=assignments,
            section_results=section_results,
            stage_errors=section_errors,
            debug_artifacts=_outline_debug_artifacts(outline_debug, assignment_debug),
        )
    stage_errors: list[str] = []
    outline_conflicts = requirement_merge_render_service.collect_outline_conflicts(section_results)
    if outline_conflicts and resolved_conflicts:
        outline_conflicts = _filter_resolved_outline_conflicts(outline_conflicts, resolved_conflicts)
        if not outline_conflicts:
            section_results = _drop_resolved_conflict_blocks(section_results)
    merged_markdown = requirement_merge_render_service.render_merged_markdown(
        document_name,
        source_documents,
        target_outline,
        section_results,
    )
    quality_result, quality_issues = requirement_merge_quality_service.evaluate_outline_merge_quality(
        source_documents=source_documents,
        target_outline=target_outline,
        assignments=assignments,
        section_results=section_results,
        conflicts=outline_conflicts,
        merged_markdown=merged_markdown,
        stage_errors=stage_errors,
    )
    outline_machine_artifacts = requirement_merge_artifact_service.write_outline_merge_machine_artifacts(
        project_id,
        document_id,
        run_id,
        source_documents=source_documents,
        target_outline=target_outline,
        assignments=assignments,
        section_results=section_results,
        quality_result=quality_result,
        quality_issues=quality_issues,
        stage_errors=stage_errors,
        debug_artifacts=_outline_debug_artifacts(outline_debug, assignment_debug),
    )
    coverage_items = _outline_coverage_items(source_documents, assignments, section_results)
    source_file_ids = [item.mapping_id for item in source_files]
    affected_modules = [section.title for section in requirement_merge_outline_service.assignable_target_sections(target_outline)]
    merge_summary = (
        f"按新大纲归并 {len(source_files)} 个标准文件、"
        f"{len(requirement_outline_assignment_service.assignable_source_nodes(source_documents))} 个旧大纲节点。"
    )
    diff_summary = "先生成统一目标大纲，再按旧大纲节点归属逐章合并。"
    if outline_conflicts or quality_result == "blocked":
        return {
            "status": "conflict",
            "markdown_content": "",
            "markdown_preview": "",
            "merge_summary": merge_summary,
            "diff_summary": diff_summary,
            "affected_modules": affected_modules,
            "source_file_ids": source_file_ids,
            "coverage_items": coverage_items,
            "conflicts": [_outline_conflict_to_legacy(conflict, source_documents) for conflict in outline_conflicts],
            "quality_result": quality_result,
            "quality_issues": quality_issues,
            "machine_artifacts": outline_machine_artifacts,
        }
    if quality_result == "failed":
        return {
            "status": "preview",
            "markdown_preview": merged_markdown,
            "merge_summary": merge_summary,
            "diff_summary": diff_summary,
            "affected_modules": affected_modules,
            "source_file_ids": source_file_ids,
            "coverage_items": coverage_items,
            "quality_result": quality_result,
            "quality_issues": quality_issues,
            "machine_artifacts": outline_machine_artifacts,
        }
    return {
        "status": "merged",
        "markdown_content": merged_markdown,
        "merge_summary": merge_summary,
        "diff_summary": diff_summary,
        "affected_modules": affected_modules,
        "source_file_ids": source_file_ids,
        "coverage_items": coverage_items,
        "quality_result": quality_result,
        "quality_issues": quality_issues,
        "machine_artifacts": outline_machine_artifacts,
    }


def _unpack_stage_result(result):
    if len(result) == 2:
        data, errors = result
        return data, errors, {}
    data, errors, debug = result
    return data, errors, debug or {}


def _failed_outline_stage_output(
    *,
    project_id: str,
    document_id: str,
    document_name: str,
    run_id: str,
    source_files: list[RequirementMergeSourceFile],
    source_documents,
    target_outline,
    assignments,
    section_results,
    stage_errors: list[str],
    debug_artifacts: dict[str, tuple[str, object]],
) -> dict:
    preview_markdown = requirement_merge_artifact_service.blocked_preview_markdown(
        document_name,
        "\n".join(f"- {error}" for error in stage_errors),
    )
    outline_machine_artifacts = requirement_merge_artifact_service.write_outline_merge_machine_artifacts(
        project_id,
        document_id,
        run_id,
        source_documents=source_documents,
        target_outline=target_outline,
        assignments=assignments,
        section_results=section_results,
        quality_result="failed",
        quality_issues=stage_errors,
        stage_errors=stage_errors,
        debug_artifacts=debug_artifacts,
    )
    return {
        "status": "preview",
        "markdown_preview": preview_markdown,
        "merge_summary": "需求归并阶段失败，未生成可写入版本的合并稿。",
        "diff_summary": "AI 大纲归并阶段失败，需排查后重新合并。",
        "affected_modules": [section.title for section in requirement_merge_outline_service.assignable_target_sections(target_outline)],
        "source_file_ids": [item.mapping_id for item in source_files],
        "coverage_items": _outline_coverage_items(source_documents, assignments, section_results),
        "quality_result": "failed",
        "quality_issues": stage_errors,
        "machine_artifacts": outline_machine_artifacts,
    }


def _outline_debug_artifacts(outline_debug: dict | None = None, assignment_debug: dict | None = None) -> dict[str, tuple[str, object]]:
    artifacts: dict[str, tuple[str, object]] = {}
    if outline_debug:
        artifacts["outline_stage_input_summary_path"] = ("outline-stage-input-summary", outline_debug.get("input_summary", {}))
        artifacts["target_outline_raw_path"] = ("target-outline-raw", outline_debug.get("raw_output", ""))
    if assignment_debug:
        artifacts["assignment_stage_input_summary_path"] = (
            "assignment-stage-input-summary",
            assignment_debug.get("input_summary", {}),
        )
        artifacts["outline_assignments_raw_path"] = ("outline-assignments-raw", assignment_debug.get("raw_output", ""))
        for batch in assignment_debug.get("batches", []) or []:
            batch_index = int(batch.get("batch_index") or 0)
            if not batch_index:
                continue
            suffix = f"assignment-batch-{batch_index:03d}"
            artifacts[f"assignment_batch_{batch_index:03d}_input_path"] = (f"{suffix}-input", batch.get("input", {}))
            artifacts[f"assignment_batch_{batch_index:03d}_raw_path"] = (f"{suffix}-raw", batch.get("raw_output", ""))
            artifacts[f"assignment_batch_{batch_index:03d}_result_path"] = (suffix, batch.get("assignments", []))
    return artifacts


def _outline_coverage_items(source_documents, assignments, section_results) -> list[dict]:
    nodes_by_id = {
        node.node_id: node
        for node in requirement_outline_assignment_service.assignable_source_nodes(source_documents)
    }
    assignments_by_node = {assignment.source_node_id: assignment for assignment in assignments}
    decisions_by_node = {}
    for result in section_results:
        for decision in result.decisions:
            decisions_by_node.setdefault(decision.source_node_id, []).append(decision)
    items: list[dict] = []
    for node_id, node in nodes_by_id.items():
        assignment = assignments_by_node.get(node_id)
        decisions = decisions_by_node.get(node_id, [])
        status = _coverage_status(assignment, decisions)
        target_module = decisions[0].target_heading if decisions else ""
        items.append(
            {
                "mapping_id": node.mapping_id,
                "source_block_id": node.node_id,
                "source_heading": " / ".join(node.heading_path),
                "source_excerpt": node.plain_text[:80] or node.title,
                "target_module": target_module,
                "target_heading": target_module,
                "coverage_status": status,
                "reason": "；".join(decision.reason for decision in decisions if decision.reason)
                or (assignment.reason if assignment else "旧大纲节点未处理。"),
            }
        )
    return items


def _coverage_status(assignment, decisions) -> str:
    statuses = {decision.status for decision in decisions}
    if "conflict" in statuses:
        return "conflict"
    if "pending_clarification" in statuses:
        return "pending_clarification"
    if statuses and statuses <= {"duplicate", "discarded"}:
        return "duplicate" if "duplicate" in statuses else "discarded"
    return "merged"


def _outline_conflict_to_legacy(conflict: OutlineMergeConflict, source_documents) -> RequirementMergeConflictOut:
    nodes_by_id = {
        node.node_id: node
        for node in requirement_outline_assignment_service.assignable_source_nodes(source_documents)
    }
    source_refs = []
    for node_id in conflict.source_node_ids:
        node = nodes_by_id.get(node_id)
        if node:
            source_refs.append({"source_node_id": node_id, "mapping_id": node.mapping_id, "filename": node.source_file})
    return RequirementMergeConflictOut(
        title=conflict.title,
        conflict_type=conflict.conflict_type,
        severity=conflict.severity,
        source_refs=source_refs,
        fragment_a=conflict.fragment_a,
        fragment_b=conflict.fragment_b,
        agent_suggestion=conflict.agent_suggestion,
    )


def _filter_resolved_outline_conflicts(conflicts: list[OutlineMergeConflict], resolved_conflicts: list[dict]) -> list[OutlineMergeConflict]:
    resolutions = [str(item.get("resolution") or "").strip() for item in resolved_conflicts if str(item.get("resolution") or "").strip()]
    if not resolutions:
        return conflicts
    remaining: list[OutlineMergeConflict] = []
    for conflict in conflicts:
        if any(resolution in conflict.fragment_a or resolution in conflict.fragment_b for resolution in resolutions):
            continue
        remaining.append(conflict)
    return remaining


def _drop_resolved_conflict_blocks(section_results):
    for result in section_results:
        result.blocks = [block for block in result.blocks if block.type != "conflict_ref"]
        resolved_node_ids = []
        for decision in result.decisions:
            if decision.status == "conflict":
                resolved_node_ids.append(decision.source_node_id)
                decision.status = "merged"
                decision.reason = f"{decision.reason} 已按人工冲突决策继续合并。"
                decision.conflict_id = ""
        existing_refs = {block.source_node_id for block in result.blocks if block.source_node_id}
        for node_id in resolved_node_ids:
            if node_id not in existing_refs:
                result.blocks.append(
                    requirement_section_merge_service.OutlineSectionBlock(
                        type="source_node_ref",
                        source_node_id=node_id,
                    )
                )
    return section_results


def _detect_merge_mode(current_version_id: str | None, *, force_rebuild: bool = False) -> str:
    if force_rebuild:
        return "rebuild"
    if current_version_id:
        return "incremental"
    return "initial"


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


def _version_markdown_path(project_id: str, document_id: str, version_no: int) -> Path:
    return project_requirement_dir(project_id, document_id) / "versions" / f"v{version_no}.md"
