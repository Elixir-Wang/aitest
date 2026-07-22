from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.agents.test_point_generation.obligation_agent import requirement_obligation_agent
from app.agents.test_point_generation.schemas import (
    RequirementObligationExtractionResult,
    TestPointGenerationInput,
)


CAPABILITY_ID = "test_point_generation"


async def extract_requirement_obligations(
    input_data: TestPointGenerationInput,
) -> RequirementObligationExtractionResult:
    if not input_data.requirement_content.strip():
        raise ValueError("最终需求内容为空，无法提取测试义务。")
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    result = await requirement_obligation_agent(model).ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "\n".join(
                        [
                            f"需求名称: {input_data.requirement_name}",
                            f"最终需求版本 ID: {input_data.requirement_version_id}",
                            "",
                            "最终需求文档:",
                            input_data.requirement_content,
                            "",
                            "请仅基于上述最终需求提取完整、可追踪的测试义务。",
                        ]
                    ),
                }
            ]
        }
    )
    structured = result.get("structured_response") if isinstance(result, dict) else None
    if structured is None:
        raise ValueError("测试义务提取智能体未返回结构化结果。")
    return (
        structured
        if isinstance(structured, RequirementObligationExtractionResult)
        else RequirementObligationExtractionResult.model_validate(structured)
    )


__all__ = ["extract_requirement_obligations"]
