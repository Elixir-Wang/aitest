from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.requirement_analysis.prompts import build_requirement_analysis_input
from app.agents.runtime import run_agent
from app.schemas.requirement_analysis import RequirementAnalysisInput, RequirementAnalysisOutput


AGENT_ID = "requirement_analysis"


async def run_requirement_analysis(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    result = await run_agent(AGENT_ID, build_requirement_analysis_input(input_data))
    return parse_requirement_analysis_output(result.output)


def parse_requirement_analysis_output(output: Any) -> RequirementAnalysisOutput:
    if isinstance(output, RequirementAnalysisOutput):
        return output
    if isinstance(output, dict):
        return RequirementAnalysisOutput.model_validate(output)
    if not isinstance(output, str):
        raise ValueError("需求分析智能体输出类型不支持。")

    text = output.strip()
    if text.startswith("```"):
        text = _strip_code_fence(text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("需求分析智能体未返回合法 JSON。") from exc
    try:
        return RequirementAnalysisOutput.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("需求分析智能体输出不符合分析契约。") from exc


def _strip_code_fence(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
