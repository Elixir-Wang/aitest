"""需求分析 + 初步需求编辑 + 澄清问答 + 最终化（finalize）。

所有"用户与 Agent 结果的交互"逻辑集中在此，包括 13 个 markdown 修补 helper。
"""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Tuple

from app.agents.requirement_analysis.service import (
    load_run_input,
    normalize_analysis_output_markdown,
    run_requirement_analysis,
)
from app.agents.requirement_finalization.service import run_requirement_finalization
from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path, store_path
from app.repositories import (
    document_repo,
    requirement_clarification_answer_repo,
)
from app.schemas.document import (
    RequirementAnalysisFinalizeIn,
    RequirementClarificationAnswerIn,
    RequirementPreliminaryUpdateIn,
)
from app.services import operation_log_service

from ._common import content_hash, version_markdown_path
from ._constants import DOCUMENT_VERSIONED_STATUS
from .finalization_context import build_finalization_context
from .serdes import (
    serialize_requirement_analysis,
    serialize_requirement_clarification_answer,
    serialize_version,
)


# === Agent 调用入口 ==========================================================

async def analyze_requirement_with_agent(run_id: str):
    """从数据库加载 run 输入并运行需求分析 Agent。返回 RequirementAnalysisResult。"""
    return await run_requirement_analysis(load_run_input(run_id), run_id=run_id)


# === 阶段 1：编辑初步需求 ====================================================

def update_requirement_preliminary_markdown(
    project_id: str,
    document_id: str,
    analysis_id: str,
    payload: RequirementPreliminaryUpdateIn,
    actor,
) -> dict:
    markdown_content = payload.markdown_content.strip()
    if not markdown_content:
        raise api_error(422, "REQUIREMENT_PRELIMINARY_MARKDOWN_REQUIRED", "初步需求不能为空。")

    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        analysis = document_repo.find_requirement_analysis(db, analysis_id)
        if not analysis or analysis["project_id"] != project_id or analysis["document_id"] != document_id:
            raise api_error(404, "REQUIREMENT_ANALYSIS_NOT_FOUND", "需求分析结果不存在。")
        if analysis["finalized_version_id"]:
            raise api_error(409, "REQUIREMENT_ANALYSIS_FINALIZED", "该初步需求已转为最终需求，不能继续修改。")

        output = normalize_analysis_output_markdown(json.loads(analysis["output_json"]))
        previous_markdown = str(output.get("understanding_markdown") or "")
        output["understanding_markdown"] = markdown_content
        draft_content_hash = content_hash(markdown_content)
        document_repo.update_requirement_analysis_output(
            db,
            analysis_id=analysis_id,
            status=str(output.get("status") or analysis["status"]),
            analysis_summary=str(output.get("analysis_summary") or analysis["analysis_summary"]),
            output_json=output,
            quality_result=str(analysis["quality_result"]),
            testability_score=int(analysis["testability_score"] or 0),
            draft_content_hash=draft_content_hash,
        )
        updated_analysis = document_repo.find_requirement_analysis(db, analysis_id)

    summary = payload.change_summary.strip() or "编辑初步需求"
    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="update",
        object_type="requirement_analysis",
        object_id=analysis_id,
        object_name=document["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=summary,
        before={"understanding_markdown": previous_markdown},
        after={"understanding_markdown": markdown_content},
    )

    return {"analysis": serialize_requirement_analysis(updated_analysis)}


# === 阶段 2：澄清问答 ========================================================

def _resolve_clarification_answer(question: dict, payload: RequirementClarificationAnswerIn) -> Tuple[str, str, str]:
    if payload.answer_type == "defer":
        return "", "", ""
    if payload.answer_type == "custom":
        answer = payload.custom_answer.strip()
        if not answer:
            raise api_error(422, "REQUIREMENT_CLARIFICATION_CUSTOM_ANSWER_REQUIRED", "请填写自定义答复。")
        return answer, "", answer
    selected_option_id = payload.selected_option_id.strip()
    if not selected_option_id:
        raise api_error(422, "REQUIREMENT_CLARIFICATION_OPTION_REQUIRED", "请选择推荐选项。")

    question_id = str(question.get("id") or "")
    answer = _selected_option_text(question, question_id, selected_option_id)
    if answer is not None:
        if not answer:
            raise api_error(422, "REQUIREMENT_CLARIFICATION_OPTION_EMPTY", "推荐选项缺少可写入内容。")
        return answer, selected_option_id, ""

    raise api_error(404, "REQUIREMENT_CLARIFICATION_OPTION_NOT_FOUND", "推荐选项不存在。")


def _selected_option_text(question: dict, question_id: str, selected_option_id: str) -> str | None:
    if not question_id:
        return None
    if selected_option_id == f"{question_id}_option_a":
        return str(question.get("option_a") or "").strip()
    if selected_option_id == f"{question_id}_option_b":
        return str(question.get("option_b") or "").strip()
    return None


def _apply_clarification_answer_to_markdown(
    markdown_content: str,
    *,
    question: dict,
    answer_markdown: str,
) -> Tuple[str, str]:
    module_name = str(question.get("module_name") or "").strip()
    module_key = str(question.get("module_key") or "").strip()
    block = _clarification_answer_markdown_block(question, answer_markdown)
    without_old_block = _remove_existing_clarification_answer(markdown_content, question)
    insertion_anchor = module_name or module_key or "人工确认补充"
    if module_name or module_key:
        updated = _append_to_matching_section(without_old_block, block, [module_name, module_key])
        if updated != without_old_block:
            return updated, insertion_anchor
    separator = "\n\n" if without_old_block.strip() else ""
    return f"{without_old_block.rstrip()}{separator}## 需求补充\n\n{block}\n", "需求补充"


def _clarification_answer_markdown_block(question: dict, answer_markdown: str) -> str:
    answer = _normalize_clarification_answer_markdown(answer_markdown)
    if _starts_with_markdown_structure(answer):
        return answer
    return f"### {_clarification_answer_heading(question)}\n\n{answer}"


def _replace_or_remove_clarification_block(markdown_content: str, question_id: str, *, replacement: str) -> str:
    pattern = re.compile(
        rf"\n*<!-- clarification-answer:{re.escape(question_id)}:start -->.*?<!-- clarification-answer:{re.escape(question_id)}:end -->\n*",
        re.DOTALL,
    )
    return pattern.sub(f"\n\n{replacement}\n\n" if replacement else "\n", markdown_content).strip()


def _remove_existing_clarification_answer(markdown_content: str, question: dict) -> str:
    question_id = str(question.get("id") or "")
    cleaned = _replace_or_remove_clarification_block(markdown_content, question_id, replacement="")
    previous_answer = str((question.get("answer") or {}).get("answer_markdown") or "").strip()
    if not previous_answer:
        return cleaned
    for previous_block in {
        _normalize_clarification_answer_markdown(previous_answer),
        _clarification_answer_markdown_block({**question, "answer": {}}, previous_answer),
    }:
        cleaned = _remove_exact_markdown_block(cleaned, previous_block)
    return _remove_empty_requirement_supplement_section(cleaned)


def _normalize_clarification_answer_markdown(answer_markdown: str) -> str:
    answer = answer_markdown.strip()
    if not answer:
        return ""
    if _starts_with_markdown_structure(answer):
        return answer
    return "\n".join(f"- {line.strip()}" for line in answer.splitlines() if line.strip())


def _starts_with_markdown_structure(markdown: str) -> bool:
    first_line = markdown.lstrip().splitlines()[0] if markdown.strip() else ""
    return bool(re.match(r"^(#{1,6}\s+|[-*+]\s+|\d+\.\s+|\>\s+|\|)", first_line))


def _clarification_answer_heading(question: dict) -> str:
    decision_point = str(question.get("decision_point") or "").strip()
    if decision_point:
        return _trim_heading(decision_point)
    question_text = str(question.get("question") or question.get("title") or "").strip()
    if "验证码" in question_text:
        return "验证码规则"
    if "导出" in question_text:
        return "导出规则"
    if "权限" in question_text:
        return "权限规则"
    module_name = str(question.get("module_name") or "").strip()
    return f"{module_name}补充规则" if module_name else "补充规则"


def _trim_heading(text: str) -> str:
    cleaned = re.sub(r"[？?。；;：:，,].*$", "", text).strip()
    return cleaned[:40] or "补充规则"


def _remove_exact_markdown_block(markdown_content: str, block: str) -> str:
    block = block.strip()
    if not block:
        return markdown_content
    pattern = re.compile(rf"\n*{re.escape(block)}\n*", re.MULTILINE)
    return pattern.sub("\n", markdown_content).strip() + ("\n" if markdown_content.strip() else "")


def _remove_empty_requirement_supplement_section(markdown_content: str) -> str:
    lines = markdown_content.splitlines()
    result: list = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not re.match(r"^##\s+需求补充\s*$", line):
            result.append(line)
            index += 1
            continue
        next_index = index + 1
        content_lines: list = []
        while next_index < len(lines) and not re.match(r"^##\s+.+", lines[next_index]):
            content_lines.append(lines[next_index])
            next_index += 1
        if any(content_line.strip() for content_line in content_lines):
            result.append(line)
            result.extend(content_lines)
        index = next_index
    return "\n".join(result).strip() + ("\n" if result else "")


def _append_to_matching_section(markdown_content: str, block: str, candidates) -> str:
    lines = markdown_content.splitlines()
    heading_index = None
    heading_level = None
    normalized_candidates = [candidate for candidate in candidates if candidate]
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        title = match.group(2)
        if any(candidate in title for candidate in normalized_candidates):
            heading_index = index
            heading_level = len(match.group(1))
            break
    if heading_index is None or heading_level is None:
        return markdown_content
    insert_at = len(lines)
    for index in range(heading_index + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+.+?\s*$", lines[index])
        if match and len(match.group(1)) <= heading_level:
            insert_at = index
            break
    next_lines = [*lines[:insert_at], "", block, "", *lines[insert_at:]]
    return "\n".join(next_lines).strip() + "\n"


def _find_requirement_analysis_question(output: dict, question_id: str):
    for bucket in ("clarification_items",):
        items = output.get(bucket) or []
        for index, item in enumerate(items):
            if item.get("id") == question_id:
                return item, bucket, index
    return None, None, None


def save_requirement_clarification_answer(
    project_id: str,
    document_id: str,
    analysis_id: str,
    payload: RequirementClarificationAnswerIn,
    actor,
) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        analysis = document_repo.find_requirement_analysis(db, analysis_id)
        if not analysis or analysis["project_id"] != project_id or analysis["document_id"] != document_id:
            raise api_error(404, "REQUIREMENT_ANALYSIS_NOT_FOUND", "需求分析结果不存在。")
        if analysis["finalized_version_id"]:
            raise api_error(409, "REQUIREMENT_ANALYSIS_FINALIZED", "该初步需求已转为最终需求，不能继续修改。")

        output = normalize_analysis_output_markdown(json.loads(analysis["output_json"]))
        question, question_bucket, question_index = _find_requirement_analysis_question(output, payload.question_id)
        if question is None or question_bucket is None or question_index is None:
            raise api_error(404, "REQUIREMENT_CLARIFICATION_QUESTION_NOT_FOUND", "待确认问题不存在。")

        answer_markdown, selected_option_id, user_note = _resolve_clarification_answer(question, payload)
        apply_status = "not_applicable" if payload.answer_type == "defer" else "applied"
        insertion_anchor = ""
        failure_reason = ""
        understanding_markdown = str(output.get("understanding_markdown") or "").strip()
        if not understanding_markdown:
            raise api_error(409, "REQUIREMENT_ANALYSIS_EMPTY_DRAFT", "需求理解为空，不能写入答复。")

        if apply_status == "applied":
            understanding_markdown, insertion_anchor = _apply_clarification_answer_to_markdown(
                understanding_markdown,
                question=question,
                answer_markdown=answer_markdown,
            )
            output["understanding_markdown"] = understanding_markdown
        else:
            output["understanding_markdown"] = _remove_existing_clarification_answer(understanding_markdown, question)

        answer_id = f"reqanswer-{secrets.token_hex(8)}"
        answer_snapshot = {
            "id": answer_id,
            "question_id": payload.question_id,
            "answer_type": payload.answer_type,
            "selected_option_id": selected_option_id,
            "answer_markdown": answer_markdown,
            "user_note": user_note,
            "apply_status": apply_status,
            "insertion_anchor": insertion_anchor,
            "failure_reason": failure_reason,
        }
        output[question_bucket][question_index] = {
            **question,
            "answer": answer_snapshot,
        }

        draft_content_hash = content_hash(str(output.get("understanding_markdown") or ""))
        document_repo.update_requirement_analysis_output(
            db,
            analysis_id=analysis_id,
            status=str(output.get("status") or analysis["status"]),
            analysis_summary=str(output.get("analysis_summary") or analysis["analysis_summary"]),
            output_json=output,
            quality_result=str(analysis["quality_result"]),
            testability_score=int(analysis["testability_score"] or 0),
            draft_content_hash=draft_content_hash,
        )
        requirement_clarification_answer_repo.upsert_answer(
            db,
            answer_id=answer_id,
            project_id=project_id,
            document_id=document_id,
            analysis_id=analysis_id,
            question_id=payload.question_id,
            answer_type=payload.answer_type,
            selected_option_id=selected_option_id,
            answer_markdown=answer_markdown,
            user_note=user_note,
            apply_status=apply_status,
            insertion_anchor=insertion_anchor,
            failure_reason=failure_reason,
            created_by=actor["id"],
        )
        saved_answer = requirement_clarification_answer_repo.find_answer(db, analysis_id, payload.question_id)
        updated_analysis = document_repo.find_requirement_analysis(db, analysis_id)

    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="answer_requirement_clarification",
        object_type="requirement_analysis",
        object_id=analysis_id,
        object_name=document["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"答复待确认问题：{question.get('question', payload.question_id)}",
        before={"question_id": payload.question_id},
        after={
            "question_id": payload.question_id,
            "answer_type": payload.answer_type,
            "apply_status": apply_status,
            "insertion_anchor": insertion_anchor,
        },
    )

    return {
        "answer": serialize_requirement_clarification_answer(saved_answer),
        "analysis": serialize_requirement_analysis(updated_analysis),
    }


# === 阶段 3：最终化 ===========================================================

async def finalize_requirement_analysis(
    project_id: str,
    document_id: str,
    payload: RequirementAnalysisFinalizeIn,
    actor,
) -> dict:
    finalization_input = None
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        analysis = document_repo.find_requirement_analysis(db, payload.analysis_id)
        if not analysis or analysis["project_id"] != project_id or analysis["document_id"] != document_id:
            raise api_error(404, "REQUIREMENT_ANALYSIS_NOT_FOUND", "需求分析结果不存在。")

        latest = document_repo.find_latest_requirement_analysis(db, document_id)
        if not latest or latest["id"] != analysis["id"]:
            raise api_error(409, "REQUIREMENT_ANALYSIS_STALE", "该需求分析不是最新结果，请刷新后重试。")
        latest_run = document_repo.find_latest_requirement_analysis_run(db, document_id)
        if latest_run and latest_run["analysis_id"] != analysis["id"]:
            raise api_error(409, "REQUIREMENT_ANALYSIS_STALE", "该需求分析不是最新结果，请刷新后重试。")

        output = normalize_analysis_output_markdown(json.loads(analysis["output_json"]))
        preliminary_markdown = str(output.get("understanding_markdown") or "").strip()
        if not preliminary_markdown:
            raise api_error(409, "REQUIREMENT_ANALYSIS_EMPTY_DRAFT", "需求理解为空，不能转为最终需求。")

        current_hash = content_hash(preliminary_markdown)
        stored_hash = analysis["draft_content_hash"] or current_hash
        finalized_version_id = analysis["finalized_version_id"]
        if finalized_version_id:
            if stored_hash != current_hash:
                raise api_error(409, "REQUIREMENT_ANALYSIS_DRAFT_CHANGED", "初步需求内容已变化，请重新执行需求分析。")
            finalized_version = document_repo.find_version(db, finalized_version_id)
            if finalized_version:
                finalized_path = resolve_stored_path(finalized_version["file_path"]) or Path(finalized_version["file_path"])
                markdown_content = finalized_path.read_text(encoding="utf-8") if finalized_path.exists() else preliminary_markdown
                return {
                    "analysis": serialize_requirement_analysis(analysis),
                    "version": serialize_version(finalized_version),
                    "document": {
                        "id": document["id"],
                        "current_version_id": document["current_version_id"],
                    },
                    "markdown_content": markdown_content,
                }

        if analysis["status"] == "blocked" or analysis["quality_result"] == "blocked":
            raise api_error(409, "REQUIREMENT_ANALYSIS_BLOCKED", "存在阻塞问题，不能转为最终需求。")

        primary_mapping_id = analysis["primary_mapping_id"] or ""
        if primary_mapping_id:
            current_primary = document_repo.find_primary_file_mapping(db, document_id)
            if not current_primary or current_primary["id"] != primary_mapping_id:
                raise api_error(409, "REQUIREMENT_ANALYSIS_PRIMARY_CHANGED", "主需求文件已变更，请重新执行需求分析。")

        finalization_input = build_finalization_context(
            db,
            project_id=project_id,
            document_id=document_id,
            analysis=analysis,
        )

    try:
        finalization_output = await run_requirement_finalization(finalization_input)
    except Exception as exc:
        raise api_error(502, "REQUIREMENT_FINALIZATION_AGENT_FAILED", f"最终需求智能体运行失败：{exc}") from exc

    final_markdown = finalization_output.final_requirement_markdown.strip()
    if not final_markdown:
        raise api_error(502, "REQUIREMENT_FINALIZATION_EMPTY_OUTPUT", "最终需求智能体返回内容为空。")

    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        analysis = document_repo.find_requirement_analysis(db, payload.analysis_id)
        if not analysis or analysis["project_id"] != project_id or analysis["document_id"] != document_id:
            raise api_error(404, "REQUIREMENT_ANALYSIS_NOT_FOUND", "需求分析结果不存在。")

        version_id = f"docver-{secrets.token_hex(8)}"
        version_no = document_repo.next_version_no(db, document_id)
        version_path = version_markdown_path(project_id, document_id, version_no)
        version_path.parent.mkdir(parents=True, exist_ok=True)
        version_path.write_text(final_markdown + "\n", encoding="utf-8")
        handled_count = len(finalization_input.handled_clarifications)
        diff_summary = finalization_output.change_summary or f"由最终需求智能体生成最终需求，回填已处理澄清 {handled_count} 项。"

        document_repo.create_version(
            db,
            version_id=version_id,
            document_id=document_id,
            version_no=version_no,
            file_path=store_path(version_path) or str(version_path),
            source_action="requirement_analysis_finalize",
            change_summary="初步需求转为最终需求",
            diff_summary=diff_summary,
            created_by=actor["id"],
        )
        document_repo.update_current_version(db, document_id, version_id, DOCUMENT_VERSIONED_STATUS)
        document_repo.mark_requirement_analysis_finalized(
            db,
            analysis_id=analysis["id"],
            version_id=version_id,
            finalized_by=actor["id"],
        )
        document_repo.create_document_version_change_log(
            db,
            log_id=f"doclog-{secrets.token_hex(8)}",
            document_id=document_id,
            version_id=version_id,
            source_action="requirement_analysis_finalize",
            change_summary="初步需求转为最终需求",
            diff_summary=diff_summary,
            affected_modules=[],
            source_mapping_ids=[primary_mapping_id] if primary_mapping_id else [],
            created_by=actor["id"],
        )
        if primary_mapping_id:
            document_repo.link_file_mapping_to_version(db, primary_mapping_id, version_id)

        finalized_analysis = document_repo.find_requirement_analysis(db, analysis["id"])
        version = document_repo.find_version(db, version_id)

    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="finalize_requirement_analysis",
        object_type="requirement_analysis",
        object_id=payload.analysis_id,
        object_name=document["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"初步需求转为最终需求：{document['name']}",
        before={"current_version_id": document["current_version_id"], "analysis_id": payload.analysis_id},
        after={"current_version_id": version_id, "version_no": version_no},
    )

    return {
        "analysis": serialize_requirement_analysis(finalized_analysis),
        "version": serialize_version(version),
        "document": {
            "id": document_id,
            "current_version_id": version_id,
        },
        "markdown_content": final_markdown + "\n",
    }
