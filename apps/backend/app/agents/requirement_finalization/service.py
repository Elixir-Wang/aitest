import json

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.requirement_finalization.agent import requirement_finalization_agent
from app.agents.requirement_finalization.schemas import (
    RequirementFinalizationInput,
    RequirementFinalizationOutput,
)

CAPABILITY_ID = "requirement_analysis"


async def run_requirement_finalization(input_data: RequirementFinalizationInput) -> RequirementFinalizationOutput:
    content = "\n\n".join(
        [
            f"需求名称：{input_data.document_name}",
            "## 标准需求 Markdown\n" + input_data.standard_markdown,
            "## 初步需求 Markdown\n" + input_data.preliminary_markdown,
            "## 已处理澄清答复\n"
            + json.dumps(
                [item.model_dump() for item in input_data.handled_clarifications],
                ensure_ascii=False,
                indent=2,
            ),
            "请基于标准需求 Markdown 的章节骨架生成最终需求 Markdown。",
        ]
    )
    model = build_agent_model(resolve_model_selection(CAPABILITY_ID))
    agent = requirement_finalization_agent(model)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": content}]})
    if not isinstance(result, dict):
        raise ValueError("最终需求智能体输出格式不正确。")
    structured = result.get("structured_response")
    if isinstance(structured, RequirementFinalizationOutput):
        return structured
    if isinstance(structured, dict):
        return RequirementFinalizationOutput.model_validate(structured)
    if isinstance(structured, str):
        return RequirementFinalizationOutput.model_validate_json(structured)
    raise ValueError("最终需求智能体未返回结构化结果。")


__all__ = ["run_requirement_finalization"]
