from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.agents.requirement_standardization.agent import requirement_standardization_agent
from app.agents.requirement_standardization.schemas import RequirementConversionInput, RequirementConversionOutput


CAPABILITY_ID = "requirement_standardization"


async def convert_requirement_file(input_data: RequirementConversionInput) -> RequirementConversionOutput:
    if not input_data.markdown_content.strip():
        raise ValueError("候选 Markdown 为空，无法标准化。")

    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    agent = requirement_standardization_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": _build_conversion_input(input_data),
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("需求标准化智能体未返回结构化结果。")
    if not output.markdown_content.strip():
        raise ValueError("需求标准化智能体返回的 Markdown 为空。")
    return output


def _build_conversion_input(input_data: RequirementConversionInput) -> str:
    lines = [
        f"filename: {input_data.filename}",
        "",
        "candidate_markdown:",
        input_data.markdown_content,
    ]
    return "\n".join(lines)
