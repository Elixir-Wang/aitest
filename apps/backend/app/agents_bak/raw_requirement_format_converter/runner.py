import json
import re
from typing import Any

from pydantic import ValidationError

from app.agents.raw_requirement_format_converter.prompts import build_requirement_conversion_input
from app.agents.runtime import run_agent
from app.schemas.requirement_conversion import RequirementConversionInput, RequirementConversionOutput


AGENT_ID = "raw_requirement_format_converter"


async def convert_raw_requirement_format(input_data: RequirementConversionInput) -> RequirementConversionOutput:
    result = await run_agent(AGENT_ID, build_requirement_conversion_input(input_data))
    return parse_requirement_conversion_output(result.output)


def parse_requirement_conversion_output(output: Any) -> RequirementConversionOutput:
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
