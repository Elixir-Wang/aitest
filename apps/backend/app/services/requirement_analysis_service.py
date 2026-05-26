from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.runtime import run_agent
from app.schemas.requirement_analysis import RequirementAnalysisInput, RequirementAnalysisOutput

REQUIREMENT_ANALYSIS_AGENT_ID = "requirement_analysis"


async def run_requirement_analysis(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    result = await run_agent(REQUIREMENT_ANALYSIS_AGENT_ID, _build_agent_prompt(input_data))
    return _parse_agent_output(result.output)


def _build_agent_prompt(input_data: RequirementAnalysisInput) -> str:
    payload = input_data.model_dump()
    return (
        "请分析以下已经归并完成的需求 Markdown 工作稿。\n"
        "你只负责需求分析、澄清问题、覆盖审计和质量门禁。\n"
        "你必须先判断需求成熟度，识别关键缺口和未验证假设，再生成待澄清问题。\n"
        "当业务目标、角色、边界、规则、验收标准或约束缺失时，必须输出待澄清内容，不得自行补全。\n"
        "不得重新归并来源文件，不得生成知识库，不得生成测试用例，不得创造未确认需求。\n"
        "只返回一个 JSON 对象，不要 Markdown 代码块，不要解释文字。\n"
        "JSON 必须符合字段：status, analysis_summary, maturity_assessment, key_gaps, assumptions, "
        "modules, clarification_questions, "
        "coverage_audit, quality_gate, next_actions。\n\n"
        f"输入：\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _parse_agent_output(output: Any) -> RequirementAnalysisOutput:
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
