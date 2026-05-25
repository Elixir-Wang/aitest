from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.agents.runtime import run_agent
from app.schemas.requirement_conversion import RequirementConversionInput, RequirementConversionOutput
from app.services.requirement_markdown_normalizer import normalize_requirement_markdown

RAW_REQUIREMENT_FORMAT_CONVERTER_AGENT_ID = "raw_requirement_format_converter"


async def convert_raw_requirement_format(input_data: RequirementConversionInput) -> RequirementConversionOutput:
    result = await run_agent(RAW_REQUIREMENT_FORMAT_CONVERTER_AGENT_ID, _build_agent_prompt(input_data))
    return _parse_agent_output(result.output)


def _build_agent_prompt(input_data: RequirementConversionInput) -> str:
    payload = input_data.model_copy(
        update={"candidate_markdown": normalize_requirement_markdown(input_data.candidate_markdown)}
    ).model_dump()
    return (
        "请校验并标准化以下原始需求文件转换得到的候选 Markdown。\n"
        "你只负责格式转换质量检查和 Markdown 标准化，不得创造、补充或推断业务需求。\n"
        "保留原文中已有的需求、标题、列表、表格、链接和图片引用；删除明显的转换噪声、页码、重复页眉页脚。\n"
        "如果 file_format=pdf，必须按 pdf_to_markdown 技能规则根据内容生成合适的 Markdown 标题、章节和列表；首个像文档名称、产品需求标题、说明书标题的内容必须作为一级标题 `# ...`，`1. 项目概述` 这类章节必须转为 `## ...`，`1.1 项目背景` 这类子章节必须转为 `### ...`，不能把 PDF 标准文件继续输出成纯文本墙。\n"
        "必须先使用 markdown_normalize 技能规则处理候选 Markdown：业务流程不得放入普通代码块；只有明确的跨步骤流程链路才可转换为 Mermaid flowchart TD；业务逻辑、规则说明、条件判断、字段取值和 action 映射应保持普通 Markdown 列表/段落/表格，不要仅因多个 ↓ 或 → 转换为 Mermaid。\n"
        "如果候选内容不足以形成可读 Markdown，也要如实返回 warnings，不要编造内容。\n"
        "只返回一个 JSON 对象，不要 Markdown 代码块，不要解释文字。\n"
        "JSON 必须符合字段：markdown_content, conversion_summary, quality_score, warnings。\n\n"
        f"输入：\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _parse_agent_output(output: Any) -> RequirementConversionOutput:
    if isinstance(output, RequirementConversionOutput):
        return output
    if isinstance(output, dict):
        return RequirementConversionOutput.model_validate(output)
    if not isinstance(output, str):
        raise ValueError("格式转换智能体输出类型不支持。")

    text = _extract_json_text(output)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        partial_output = _parse_partial_agent_output(text)
        if partial_output is not None:
            return partial_output
        raise ValueError("格式转换智能体未返回合法 JSON。") from exc
    try:
        return RequirementConversionOutput.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("格式转换智能体输出不符合转换契约。") from exc


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


def _parse_partial_agent_output(text: str) -> RequirementConversionOutput | None:
    markdown_content = _extract_json_string_field(text, "markdown_content")
    if not markdown_content:
        return None

    conversion_summary = _extract_json_string_field(text, "conversion_summary") or "智能体已返回 Markdown 内容，但附加字段不是合法 JSON，已保留正文。"
    quality_score = _extract_json_int_field(text, "quality_score") or 80
    warnings = _extract_json_string_array_field(text, "warnings")
    if warnings is None:
        warnings = ["智能体输出不是完整合法 JSON，已从 markdown_content 字段恢复正文。"]

    return RequirementConversionOutput(
        markdown_content=markdown_content,
        conversion_summary=conversion_summary,
        quality_score=quality_score,
        warnings=warnings,
    )


def _extract_json_string_field(text: str, field_name: str) -> str | None:
    match = re.search(rf'"{re.escape(field_name)}"\s*:\s*"((?:\\.|[^"\\])*)"', text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return None


def _extract_json_int_field(text: str, field_name: str) -> int | None:
    match = re.search(rf'"{re.escape(field_name)}"\s*:\s*(\d+)', text)
    if not match:
        return None
    return int(match.group(1))


def _extract_json_string_array_field(text: str, field_name: str) -> list[str] | None:
    match = re.search(rf'"{re.escape(field_name)}"\s*:\s*(\[(?:.|\n)*?\])', text, flags=re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return value
