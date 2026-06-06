import json

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.requirement_analysis.agent import requirement_analysis_agent
from app.schemas.requirement_analysis import RequirementAnalysisInput, RequirementAnalysisOutput


CAPABILITY_ID = "requirement_analysis"


async def analyze_requirement(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    agent = requirement_analysis_agent(model)
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
    if not output.preliminary_requirement_markdown.strip():
        raise ValueError("需求分析智能体未返回初步需求内容。")
    return output


def _build_requirement_analysis_input(input_data: RequirementAnalysisInput) -> str:
    return "\n".join(
        [
            "请执行主需求锚定的需求分析。返回 RequirementAnalysisOutput 结构化结果。",
            "",
            "input_json:",
            json.dumps(input_data.model_dump(), ensure_ascii=False, indent=2),
        ]
    )
