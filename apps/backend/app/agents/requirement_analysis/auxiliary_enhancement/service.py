import json

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.requirement_analysis.auxiliary_enhancement.agent import auxiliary_enhancement_agent
from app.agents.requirement_analysis.auxiliary_enhancement.schemas import (
    RequirementAuxiliaryEnhancementInput,
    RequirementAuxiliaryEnhancementOutput,
)


CAPABILITY_ID = "requirement_analysis"


async def enhance_requirement_with_auxiliary_articles(
    input_data: RequirementAuxiliaryEnhancementInput,
) -> RequirementAuxiliaryEnhancementOutput:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    agent = auxiliary_enhancement_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": _build_auxiliary_enhancement_input(input_data),
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("辅助文档增强智能体未返回结构化结果。")
    return output


def _build_auxiliary_enhancement_input(input_data: RequirementAuxiliaryEnhancementInput) -> str:
    return "\n".join(
        [
            "请基于 questions 和 auxiliary_articles 查找答案，返回 RequirementAuxiliaryEnhancementOutput。",
            "",
            "input_json:",
            json.dumps(input_data.model_dump(), ensure_ascii=False, indent=2),
        ]
    )
