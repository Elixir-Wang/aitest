import json

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.requirement_merge.agent import requirement_merge_outline_agent, requirement_merge_section_agent
from app.agents.requirement_merge.schemas import (
    RequirementMergeOutlineInput,
    RequirementMergeOutlineOutput,
    RequirementMergeSectionInput,
    RequirementMergeSectionOutput,
)


CAPABILITY_ID = "requirement_merge"


async def generate_outline_and_placements(input_data: RequirementMergeOutlineInput) -> RequirementMergeOutlineOutput:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    agent = requirement_merge_outline_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(input_data.model_dump(), ensure_ascii=False, indent=2),
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("需求归并智能体未返回结构化大纲结果。")
    return output


async def merge_requirement_section(input_data: RequirementMergeSectionInput) -> RequirementMergeSectionOutput:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    agent = requirement_merge_section_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(input_data.model_dump(), ensure_ascii=False, indent=2),
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("需求归并智能体未返回结构化模块合并结果。")
    return output
