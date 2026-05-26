from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.agents.runtime import run_agent
from app.schemas.requirement_merge import (
    RequirementCoverageItem,
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
    merge_output = _parse_agent_output(result.output)
    _complete_source_file_coverage(merge_output, input_data)
    return normalize_merge_output(merge_output, input_data)


def normalize_merge_output(output: RequirementMergeOutput, input_data: RequirementMergeInput) -> RequirementMergeOutput:
    source_names = {item.mapping_id: Path(item.original_filename).stem for item in input_data.source_files}
    for item in output.coverage_items:
        if item.mapping_id in source_names:
            item.source_heading = _source_display_name(item.source_heading, item.mapping_id, source_names[item.mapping_id])
        if item.coverage_status == "discarded" and not item.reason.strip():
            item.reason = "已丢弃，智能体未提供具体原因。"

    for conflict in output.conflicts:
        normalized_refs = []
        for ref in conflict.source_refs:
            next_ref = dict(ref)
            mapping_id = str(next_ref.get("mapping_id", ""))
            if mapping_id in source_names:
                next_ref["filename"] = source_names[mapping_id]
            elif next_ref.get("filename"):
                next_ref["filename"] = Path(str(next_ref["filename"])).stem
            normalized_refs.append(next_ref)
        conflict.source_refs = normalized_refs

    if output.status == "conflict":
        output.markdown_content = ""
        output.markdown_preview = ""

    duplicate_count = sum(1 for item in output.coverage_items if item.coverage_status == "duplicate")
    if duplicate_count and not re.search(r"重复去重\s*\d+\s*处", output.merge_summary):
        output.merge_summary = f"{output.merge_summary.rstrip('。')}，重复去重 {duplicate_count} 处。"

    _validate_merge_output(output, input_data)
    return output


def _build_agent_prompt(input_data: RequirementMergeInput) -> str:
    payload = input_data.model_dump()
    return (
        "请分析并归并以下多个标准 Markdown 需求文件。\n"
        "必须按业务模块重组需求，不允许按文件简单拼接，不允许创造未确认需求。\n"
        "必须确保所有来源文件都被处理：可合入则合入，重复则标 duplicate，互斥则标 conflict，待业务确认则标 pending_clarification，明确不进入需求稿的背景材料、阅读建议、附件提示、目录页和纯说明性内容标 discarded 且必须写原因。\n"
        "最终 markdown_content/markdown_preview 是给业务和研发阅读的正式需求工作稿，正文结构中禁止展示源文件名、原始文档标题、mapping_id 或“来源文档/源文档”分组。\n"
        "源文件追溯只能放在 coverage_items、conflicts.source_refs、source_file_ids 中，不得污染正式需求正文。\n"
        "coverage_items.source_heading 可以写业务章节；映射明细展示来源文件时必须使用 original_filename 去掉扩展名后的文件名，不得使用 docmap 或 mapping_id 当来源文件名。\n"
        "正文只能包含已归并后的需求模块、可验收需求、待澄清问题；背景材料、阅读建议、附件提示、目录页和纯说明性内容必须从正文剔除，并在 coverage_items 标记为 discarded。\n"
        "如果来源之间存在互斥或矛盾，返回 status=conflict，且 markdown_content 和 markdown_preview 必须为空；明显冲突只进入 conflicts，不能生成合并需求稿和质量报告。\n"
        "如果是 incremental 模式，返回 status=preview，并把候选结果放入 markdown_preview，不要假装已经写入版本。\n"
        "coverage_items 必须覆盖每个有效需求片段，不是只覆盖每个文件；可测试需求、接口字段、状态流转、安全约束、验收标准等独有信息都必须合入、标重复、标冲突、标待澄清或标丢弃并说明原因。\n"
        "coverage_items 用于证明来源内容已完整处理，不能把整段 Markdown、完整章节或长列表塞入 source_excerpt；source_excerpt 必须简短，不超过 80 个中文字符。有重复语句或等价表达时，merge_summary 必须包含“重复去重 N 处”。\n"
        "正式合并稿可以重组和去重，但不得摘要化导致需求、接口、字段、状态、错误码、验收点等独有内容大面积丢失。\n"
        "必须保留有效 Markdown 表达形式：来源中的 Mermaid 流程图、sequenceDiagram、接口/字段/错误码/验收表格、JSON/SQL/HTTP/curl 等代码围栏如果承载需求信息，合并稿中必须以原 Markdown 结构保留或合并到对应业务模块；不得改写成普通段落或项目符号。\n"
        "当多个来源存在等价表格或流程图时，可以去重或合并列/行，但仍必须输出 Markdown 表格或 fenced code block；只有纯目录、阅读建议、无需求信息的示例才可丢弃并在 coverage_items 写明原因。\n"
        "没有明显冲突时，才可以生成合并需求稿和质量报告。\n"
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
        repaired_text = _repair_markdown_json_string_fields(text)
        try:
            parsed = json.loads(repaired_text)
        except json.JSONDecodeError as repaired_exc:
            completed_text = _complete_truncated_merge_json(repaired_text)
            if completed_text == repaired_text:
                raise ValueError("需求归并智能体未返回合法 JSON。") from exc
            try:
                parsed = json.loads(completed_text)
            except json.JSONDecodeError:
                raise ValueError("需求归并智能体未返回合法 JSON。") from repaired_exc
    try:
        parsed = _complete_partial_merge_payload(parsed)
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


def _repair_markdown_json_string_fields(text: str) -> str:
    repaired = text
    for field_name in ("markdown_content", "markdown_preview"):
        repaired = _repair_json_string_field(repaired, field_name)
    return repaired


def _complete_partial_merge_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    markdown_content = str(payload.get("markdown_content") or "")
    markdown_preview = str(payload.get("markdown_preview") or "")
    if not markdown_content.strip() and not markdown_preview.strip():
        return payload

    if not payload.get("merge_summary"):
        payload["merge_summary"] = "智能体已生成归并候选稿，未返回归并摘要。"
    payload.setdefault("diff_summary", "")
    payload.setdefault("affected_modules", [])
    payload.setdefault("conflicts", [])

    source_file_ids = payload.get("source_file_ids")
    if not isinstance(source_file_ids, list):
        source_file_ids = []
        payload["source_file_ids"] = source_file_ids

    coverage_items = payload.get("coverage_items")
    if not isinstance(coverage_items, list):
        coverage_items = []
        payload["coverage_items"] = coverage_items

    covered_ids = {str(item.get("mapping_id")) for item in coverage_items if isinstance(item, dict)}
    for mapping_id in source_file_ids:
        if mapping_id in covered_ids:
            continue
        coverage_items.append(
            {
                "mapping_id": str(mapping_id),
                "source_excerpt": "智能体未返回覆盖摘要，已按来源文件补齐覆盖记录。",
                "coverage_status": "merged",
                "reason": "智能体已生成归并候选稿，服务端补齐来源覆盖记录。",
            }
        )
    return payload


def _complete_source_file_coverage(output: RequirementMergeOutput, input_data: RequirementMergeInput) -> None:
    if output.status == "conflict":
        return
    if not output.source_file_ids:
        output.source_file_ids = [item.mapping_id for item in input_data.source_files]
    covered_ids = {item.mapping_id for item in output.coverage_items}
    for source_file in input_data.source_files:
        if source_file.mapping_id in covered_ids:
            continue
        output.coverage_items.append(
            RequirementCoverageItem(
                mapping_id=source_file.mapping_id,
                source_excerpt=f"{Path(source_file.original_filename).stem} 已参与归并。",
                coverage_status="merged",
                reason="智能体已生成归并候选稿，服务端补齐来源覆盖记录。",
            )
        )


def _complete_truncated_merge_json(text: str) -> str:
    if _is_balanced_json_container(text):
        return text

    coverage_pos = text.find('"coverage_items"')
    if coverage_pos == -1:
        return text
    array_pos = text.find("[", coverage_pos)
    if array_pos == -1:
        return text

    last_complete_item_end = _last_complete_array_item_end(text, array_pos)
    if last_complete_item_end == -1:
        return text
    prefix = text[: last_complete_item_end + 1].rstrip()
    return f"{prefix}\n  ]\n}}"


def _is_balanced_json_container(text: str) -> bool:
    stack: list[str] = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char == "}":
            if not stack or stack.pop() != "{":
                return False
        elif char == "]":
            if not stack or stack.pop() != "[":
                return False
    return not stack and not in_string


def _last_complete_array_item_end(text: str, array_pos: int) -> int:
    stack: list[str] = []
    in_string = False
    escaped = False
    last_end = -1
    for idx in range(array_pos + 1, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char == "}":
            if not stack or stack[-1] != "{":
                return last_end
            stack.pop()
            if not stack:
                last_end = idx
        elif char == "]":
            if not stack:
                return idx
            if stack[-1] != "[":
                return last_end
            stack.pop()
    return last_end


def _repair_json_string_field(text: str, field_name: str) -> str:
    marker = f'"{field_name}"'
    cursor = 0
    chunks: list[str] = []
    changed = False
    while True:
        field_pos = text.find(marker, cursor)
        if field_pos == -1:
            chunks.append(text[cursor:])
            break
        colon_pos = text.find(":", field_pos + len(marker))
        if colon_pos == -1:
            chunks.append(text[cursor:])
            break
        quote_pos = colon_pos + 1
        while quote_pos < len(text) and text[quote_pos].isspace():
            quote_pos += 1
        if quote_pos >= len(text) or text[quote_pos] != '"':
            chunks.append(text[cursor : quote_pos])
            cursor = quote_pos
            continue

        value_start = quote_pos + 1
        idx = value_start
        escaped = False
        value_chars: list[str] = []
        while idx < len(text):
            char = text[idx]
            if escaped:
                value_chars.append(char)
                escaped = False
                idx += 1
                continue
            if char == "\\":
                value_chars.append(char)
                escaped = True
                idx += 1
                continue
            if char == '"':
                next_idx = idx + 1
                while next_idx < len(text) and text[next_idx].isspace():
                    next_idx += 1
                if next_idx >= len(text) or text[next_idx] in ",}]":
                    chunks.append(text[cursor:value_start])
                    chunks.append("".join(value_chars))
                    cursor = idx
                    break
                value_chars.append('\\"')
                changed = True
                idx += 1
                continue
            value_chars.append(char)
            idx += 1
        else:
            chunks.append(text[cursor:])
            cursor = len(text)
            break

    return "".join(chunks) if changed else text


def _source_display_name(source_heading: str, mapping_id: str, source_name: str) -> str:
    heading = source_heading.strip()
    if not heading or heading == mapping_id or heading.startswith("docmap-"):
        return source_name
    return heading


def _validate_merge_output(output: RequirementMergeOutput, input_data: RequirementMergeInput) -> None:
    if output.status == "conflict":
        if not output.conflicts:
            raise ValueError("需求归并智能体返回冲突状态但未提供明显冲突明细。")
        if output.markdown_content.strip() or output.markdown_preview.strip():
            raise ValueError("存在明显冲突时不能生成合并需求稿。")
    if output.status == "merged" and not output.markdown_content.strip():
        raise ValueError("需求归并智能体返回 merged 但未提供合并需求稿。")
    if output.status == "preview" and not output.markdown_preview.strip():
        raise ValueError("需求归并智能体返回 preview 但未提供合并候选稿。")
    if not output.coverage_items:
        raise ValueError("需求归并智能体未返回段落映射，无法证明所有来源段落已处理。")

    source_ids = {item.mapping_id for item in input_data.source_files}
    covered_ids = {item.mapping_id for item in output.coverage_items}
    missing_ids = sorted(source_ids - covered_ids)
    if missing_ids:
        raise ValueError(f"需求归并智能体未覆盖来源文件：{', '.join(missing_ids)}。")
    for item in output.coverage_items:
        if item.coverage_status == "discarded" and not item.reason.strip():
            raise ValueError("已丢弃的段落映射必须提供原因。")
