from __future__ import annotations

import json
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
        "必须先使用 markdown_normalize 技能规则处理候选 Markdown：业务流程不得放入普通代码块，多个 ↓ 或 → 串联的流程必须转换为 Mermaid flowchart TD。\n"
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
        raise ValueError("原始需求格式转换智能体输出类型不支持。")

    text = output.strip()
    if text.startswith("```"):
        text = _strip_code_fence(text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("原始需求格式转换智能体未返回合法 JSON。") from exc
    try:
        return RequirementConversionOutput.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("原始需求格式转换智能体输出不符合转换契约。") from exc


def _strip_code_fence(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
