import json
from pathlib import Path

from app.agents.requirement_finalization.schemas import HandledClarification, RequirementFinalizationInput
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path
from app.repositories import document_repo, requirement_clarification_answer_repo

HANDLED_APPLY_STATUS = "applied"
NO_OP_APPLY_STATUS = "not_applicable"
REQUIRED_PRIORITIES = {"P0", "P1"}


def build_finalization_context(db, *, project_id: str, document_id: str, analysis) -> RequirementFinalizationInput:
    document = document_repo.find_by_project_and_id(db, project_id, document_id)
    if not document:
        raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

    output = _analysis_output(analysis)
    preliminary_markdown = str(output.get("understanding_markdown") or "").strip()
    if not preliminary_markdown:
        raise api_error(409, "REQUIREMENT_ANALYSIS_EMPTY_DRAFT", "需求理解为空，不能转为最终需求。")

    answers = {
        row["question_id"]: row
        for row in requirement_clarification_answer_repo.list_answers(db, analysis["id"])
    }
    handled_clarifications: list[HandledClarification] = []
    open_required: list[str] = []

    for question in output.get("clarification_items") or []:
        priority = str(question.get("priority") or "P2").upper()
        answer = answers.get(str(question.get("id") or ""))
        apply_status = answer["apply_status"] if answer else ""
        if apply_status == HANDLED_APPLY_STATUS:
            handled_clarifications.append(_handled_clarification(question, answer, priority))
            continue
        if apply_status == NO_OP_APPLY_STATUS:
            continue
        if priority in REQUIRED_PRIORITIES:
            open_required.append(str(question.get("id") or question.get("question") or "未命名澄清项"))

    if open_required:
        raise api_error(
            409,
            "REQUIREMENT_ANALYSIS_REQUIRED_CLARIFICATIONS_OPEN",
            "P0 / P1 澄清项处理完成后才能转为最终需求。",
        )

    primary_file = document_repo.find_file_mapping(db, analysis["primary_mapping_id"]) if analysis["primary_mapping_id"] else None
    if not primary_file:
        primary_file = document_repo.find_primary_file_mapping(db, document_id)
    if not primary_file or not primary_file["markdown_file_path"]:
        raise api_error(409, "DOCUMENT_PRIMARY_FILE_NOT_READY", "请先完成主需求标准文件转换后再转为最终需求。")

    return RequirementFinalizationInput(
        document_name=document["name"],
        standard_markdown=_read_markdown(primary_file["markdown_file_path"]),
        preliminary_markdown=preliminary_markdown,
        handled_clarifications=handled_clarifications,
    )


def _analysis_output(analysis) -> dict:
    try:
        output = json.loads(analysis["output_json"])
    except json.JSONDecodeError as exc:
        raise api_error(409, "REQUIREMENT_ANALYSIS_OUTPUT_INVALID", "需求分析结果格式异常，不能转为最终需求。") from exc
    return output if isinstance(output, dict) else {}


def _handled_clarification(question: dict, answer, priority: str) -> HandledClarification:
    return HandledClarification(
        question_id=str(question.get("id") or answer["question_id"]),
        priority=priority,
        question=str(question.get("question") or question.get("decision_point") or ""),
        answer_markdown=str(answer["answer_markdown"] or ""),
        insertion_anchor=str(answer["insertion_anchor"] or ""),
        module_name=str(question.get("module_name") or question.get("module") or ""),
        module_key=str(question.get("module_key") or ""),
        source_excerpt=str(question.get("source_excerpt") or question.get("primary_excerpt") or ""),
        impact=str(question.get("impact") or question.get("test_impact") or ""),
    )


def _read_markdown(path_value: str) -> str:
    markdown_path = resolve_stored_path(path_value) or Path(path_value)
    if not markdown_path.exists():
        raise api_error(404, "DOCUMENT_MARKDOWN_MISSING", "需求标准文件不存在。")
    return markdown_path.read_text(encoding="utf-8")


__all__ = ["build_finalization_context"]
