from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.agents.manual_test_case_generation.agent import manual_test_case_generation_agent
from app.agents.manual_test_case_generation.schemas import (
    ManualTestCaseGenerationInput,
    ManualTestCaseGenerationResult,
)


CAPABILITY_ID = "test_case_generation"


def _build_prompt(input_data: ManualTestCaseGenerationInput) -> str:
    parts = ["【测试目标】", input_data.description]
    context = input_data.exploration_context
    if context:
        parts.extend(["", "【探索上下文】"])
        for page in context.pages:
            parts.append(f"页面：{page.display_name or page.title} 路径：{page.entry_path}")
            if page.breadcrumb:
                parts.append(f"面包屑：{' / '.join(page.breadcrumb)}")
            if page.structure_summary:
                parts.append(f"结构摘要：{page.structure_summary}")
            for element in page.elements:
                parts.append(
                    f"元素：{element.name or element.text} 角色={element.role} 动作={element.action_type}"
                )
        if context.warnings:
            parts.extend(["", "【上下文说明】", *context.warnings])
    parts.extend(
        [
            "",
            "请生成一条手工测试用例，只返回结构化结果。每个步骤必须包含一个清晰动作和一个可验证的预期结果。",
        ]
    )
    return "\n".join(parts)


async def generate_manual_test_case(input_data: ManualTestCaseGenerationInput) -> ManualTestCaseGenerationResult:
    if not input_data.description.strip():
        raise ValueError("测试描述为空，无法生成测试用例。")

    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    agent = manual_test_case_generation_agent(model)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": _build_prompt(input_data)}]})

    if not isinstance(result, dict) or not result.get("structured_response"):
        raise ValueError("手工测试用例生成智能体未返回结构化结果。")

    structured = result["structured_response"]
    if isinstance(structured, ManualTestCaseGenerationResult):
        return structured
    if isinstance(structured, dict):
        return ManualTestCaseGenerationResult.model_validate(structured)
    if isinstance(structured, str):
        return ManualTestCaseGenerationResult.model_validate_json(structured)
    raise ValueError(f"手工测试用例生成智能体输出类型不支持: {type(structured).__name__}")
