import json
from typing import Any

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.requirement_analysis.primary_analysis.agent import primary_analysis_agent
from app.agents.requirement_analysis.primary_analysis.schemas import RequirementAnalysisInput, RequirementAnalysisOutput


CAPABILITY_ID = "requirement_analysis"


async def analyze_requirement(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    agent = primary_analysis_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": _build_requirement_analysis_input(input_data),
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("需求分析智能体未返回结构化结果。")
    if output.applied_supplements:
        output.applied_supplements = []
    if not output.preliminary_requirement_markdown.strip():
        raise ValueError("需求分析智能体未返回初步需求内容。")
    return output


def _build_requirement_analysis_input(input_data: RequirementAnalysisInput) -> str:
    return "\n".join(
        [
            "请只基于主需求执行需求分析，返回 RequirementAnalysisOutput。",
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
