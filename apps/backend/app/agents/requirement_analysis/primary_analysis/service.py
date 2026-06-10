import json
from typing import Any

from app.agents.requirement_analysis_codex.runner import run_requirement_analysis_with_codex
from app.agents.requirement_analysis.primary_analysis.schemas import RequirementAnalysisInput, RequirementAnalysisOutput


CAPABILITY_ID = "requirement_analysis"


async def analyze_requirement(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    output = await run_requirement_analysis_with_codex(input_data)
    primary_markdown = input_data.primary_markdown_content.strip()
    if not primary_markdown:
        raise ValueError("主需求标准文件为空，无法生成初步需求。")
    if not output.preliminary_requirement_markdown.strip():
        output.preliminary_requirement_markdown = primary_markdown
    return output


def _build_requirement_analysis_input(input_data: RequirementAnalysisInput) -> str:
    return "\n".join(
        [
            "请只基于主需求执行需求分析，返回 RequirementAnalysisOutput。",
            "必须按 requirement-review 技能分析，并包含测试覆盖缺口视角。",
            "只输出分析结论；不要生成、优化、摘要或改写需求正文。",
            "preliminary_requirement_markdown 可返回空字符串，系统会直接使用 primary_markdown_content 原文作为初步需求。",
            "分析发现的问题写入结构化字段。",
            "clarification_questions/conflicts 的 question 只写直接待确认问题，可把需要确认的字段直接问出来，不要拆出“当前缺口”“缺失说明”等额外字段或解释段。",
            "不确认的影响写入 impact。",
            "",
            "input_json:",
            json.dumps(_primary_visible_input(input_data), ensure_ascii=False, indent=2),
        ]
    )


def _primary_visible_input(input_data: RequirementAnalysisInput) -> dict[str, Any]:
    return {
        "project_id": input_data.project_id,
        "document_id": input_data.document_id,
        "document_name": input_data.document_name,
        "primary_mapping_id": input_data.primary_mapping_id,
        "primary_filename": input_data.primary_filename,
        "primary_markdown_content": input_data.primary_markdown_content,
    }
