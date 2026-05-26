from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.agents.runtime import run_agent
from app.schemas.requirement_merge import (
    RequirementMergeBaseVersion,
    RequirementMergeInput,
    RequirementMergeOutput,
    RequirementMergeResolvedConflict,
    RequirementMergeSourceFile,
)

REQUIREMENT_MERGE_AGENT_ID = "requirement_merge"


def detect_merge_mode(current_version_id: str | None, *, force_rebuild: bool = False) -> str:
    if force_rebuild:
        return "rebuild"
    if current_version_id:
        return "incremental"
    return "initial"


def build_merge_input(
    *,
    project_id: str,
    document_id: str,
    document_name: str,
    merge_mode: str,
    base_version: RequirementMergeBaseVersion | None,
    source_files: list[RequirementMergeSourceFile],
    resolved_conflicts: list[RequirementMergeResolvedConflict],
) -> RequirementMergeInput:
    return RequirementMergeInput(
        project_id=project_id,
        document_id=document_id,
        document_name=document_name,
        merge_mode=merge_mode,
        base_version=base_version,
        source_files=source_files,
        resolved_conflicts=resolved_conflicts,
    )


async def run_requirement_merge(input_data: RequirementMergeInput) -> RequirementMergeOutput:
    return await run_requirement_merge_agent(input_data)


async def run_requirement_merge_agent(input_data: RequirementMergeInput) -> RequirementMergeOutput:
    result = await run_agent(REQUIREMENT_MERGE_AGENT_ID, _build_agent_prompt(input_data))
    return _parse_agent_output(result.output)


def _build_agent_prompt(input_data: RequirementMergeInput) -> str:
    payload = input_data.model_dump()
    return (
        "请分析并归并以下多个标准 Markdown 需求文件。\n"
        "必须按业务模块重组需求，不允许按文件简单拼接，不允许创造未确认需求。\n"
        "最终 markdown_content/markdown_preview 是给业务和研发阅读的正式需求工作稿，正文结构中禁止展示源文件名、原始文档标题、mapping_id 或“来源文档/源文档”分组。\n"
        "源文件追溯只能放在 coverage_items、conflicts.source_refs、source_file_ids 中，不得污染正式需求正文。\n"
        "正文只能包含已归并后的需求模块、可验收需求、待澄清问题；背景材料、阅读建议、附件提示、目录页和纯说明性内容必须从正文剔除或放入 coverage_items 标记为 not_testable/discarded。\n"
        "如果来源之间存在互斥或矛盾，返回 status=conflict，且不要输出最终 markdown_content。\n"
        "如果是 incremental 模式，返回 status=preview，并把候选结果放入 markdown_preview，不要假装已经写入版本。\n"
        "必须为每个来源要点输出 coverage_items，说明 merged、duplicate、conflict、pending_clarification、not_testable 或 discarded。\n"
        "只返回一个 JSON 对象，不要 Markdown 代码块，不要解释文字。\n"
        "JSON 必须符合字段：status, markdown_content, markdown_preview, merge_summary, diff_summary, "
        "affected_modules, source_file_ids, coverage_items, conflicts。\n\n"
        f"输入：\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _parse_agent_output(output: Any) -> RequirementMergeOutput:
    if isinstance(output, RequirementMergeOutput):
        return output
    if isinstance(output, dict):
        return RequirementMergeOutput.model_validate(output)
    if not isinstance(output, str):
        raise ValueError("需求归并智能体输出类型不支持。")

    text = _extract_json_text(output)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("需求归并智能体未返回合法 JSON。") from exc
    try:
        return RequirementMergeOutput.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("需求归并智能体输出不符合归并契约。") from exc


def _strip_code_fence(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()

def _extract_json_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = _strip_code_fence(stripped)
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        return stripped[start : end + 1].strip()

    return stripped
