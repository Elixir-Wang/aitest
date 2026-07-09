import json

from app.agents.api_automation.agent import api_automation_generation_agent
from app.agents.api_automation.schemas import ApiAutomationGenerationInput, ApiAutomationGenerationResult
from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body


CAPABILITY_ID = "api_test_generation"


async def generate_api_test_cases(input_data: ApiAutomationGenerationInput) -> ApiAutomationGenerationResult:
    if not input_data.endpoints:
        raise ValueError("接口列表为空，无法生成接口自动化用例。")

    content_parts = [
        f"项目ID: {input_data.project_id}",
        "",
        "接口定义（来自 OpenAPI/手工维护，是接口事实来源）:",
        json.dumps(input_data.endpoints, ensure_ascii=False, indent=2),
    ]

    if input_data.environment_summary:
        content_parts.extend(
            [
                "",
                "接口环境摘要（只用于生成可执行请求，不得输出敏感明文）:",
                json.dumps(input_data.environment_summary, ensure_ascii=False, indent=2),
            ]
        )

    if input_data.source_test_cases:
        content_parts.extend(
            [
                "",
                "可参考的需求测试用例或历史用例:",
                json.dumps(input_data.source_test_cases, ensure_ascii=False, indent=2),
            ]
        )

    if input_data.generation_goal:
        content_parts.extend(["", f"生成目标: {input_data.generation_goal}"])

    content_parts.extend(
        [
            "",
            f"是否生成安全类用例: {input_data.include_security_cases}",
            "",
            "请使用 api-automation-case-generation skill 生成接口自动化用例。",
        ]
    )

    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    agent = api_automation_generation_agent(model)

    result = await agent.ainvoke({"messages": [{"role": "user", "content": "\n".join(content_parts)}]})
    if not isinstance(result, dict):
        raise ValueError("接口自动化用例生成智能体输出格式不正确。")

    generation_result = result.get("structured_response")
    if not generation_result:
        raise ValueError("接口自动化用例生成智能体未返回结构化结果。")

    if isinstance(generation_result, ApiAutomationGenerationResult):
        return generation_result
    if isinstance(generation_result, dict):
        return ApiAutomationGenerationResult.model_validate(generation_result)
    if isinstance(generation_result, str):
        return ApiAutomationGenerationResult.model_validate_json(generation_result)
    raise ValueError(f"接口自动化用例生成智能体输出类型不支持: {type(generation_result).__name__}")
