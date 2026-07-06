"""测试用例生成服务层"""

import secrets

from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.agents.test_case_generation.agent import test_case_generation_agent
from app.agents.test_case_generation.schemas import (
    TestCaseGenerationInput,
    TestCaseGenerationResult,
)


CAPABILITY_ID = "test_case_generation"


async def generate_test_cases(input_data: TestCaseGenerationInput) -> TestCaseGenerationResult:
    """
    测试用例生成核心函数

    Args:
        input_data: 测试用例生成输入

    Returns:
        测试用例生成结果

    Raises:
        ValueError: 需求内容为空或 Agent 未返回结构化结果
    """
    # 验证输入
    if not input_data.requirement_content.strip():
        raise ValueError("需求内容为空，无法生成测试用例。")

    # 构建输入内容
    content_parts = [
        f"需求名称: {input_data.requirement_name}",
        "",
        "最终需求文档:",
        input_data.requirement_content,
    ]

    # 添加生成范围
    if input_data.generation_scope:
        content_parts.append("")
        content_parts.append(f"生成范围: {input_data.generation_scope}")

    if input_data.rejected_case_feedback:
        content_parts.append("")
        content_parts.append("历史不采纳用例反馈（重新生成时必须参考，避免再次生成同类问题；反馈为空时不得编造拒绝原因）:")
        for index, feedback in enumerate(input_data.rejected_case_feedback, 1):
            content_parts.append(f"{index}. 标题: {feedback.title}")
            if feedback.module:
                content_parts.append(f"   模块: {feedback.module}")
            if feedback.priority:
                content_parts.append(f"   优先级: {feedback.priority}")
            if feedback.preconditions:
                content_parts.append(f"   前置条件: {feedback.preconditions}")
            if feedback.steps:
                content_parts.append("   步骤:")
                for step_index, step in enumerate(feedback.steps, 1):
                    content_parts.append(f"   {step_index}) {step.action}")
                    content_parts.append(f"      该步预期: {step.expected_result}")
            if feedback.expected_result:
                content_parts.append(f"   预期结果: {feedback.expected_result}")
            content_parts.append(f"   不采纳原因: {feedback.review_feedback or '用户未填写原因'}")

    content_parts.append("\n请使用 test-case-generation skill 生成测试用例集。")
    content = "\n".join(content_parts)

    # 调用 Agent
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    agent = test_case_generation_agent(model)

    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": content}]
    })

    # 提取结构化输出
    if not isinstance(result, dict):
        raise ValueError("测试用例生成智能体输出格式不正确。")

    generation_result = result.get("structured_response")

    if not generation_result:
        raise ValueError("测试用例生成智能体未返回结构化结果。")

    # 处理多种返回类型
    if isinstance(generation_result, TestCaseGenerationResult):
        return generation_result
    elif isinstance(generation_result, dict):
        return TestCaseGenerationResult.model_validate(generation_result)
    elif isinstance(generation_result, str):
        return TestCaseGenerationResult.model_validate_json(generation_result)
    else:
        raise ValueError(f"测试用例生成智能体输出类型不支持: {type(generation_result).__name__}")


def next_generation_id() -> str:
    """生成下一个测试用例生成 ID"""
    return f"tcgen-{secrets.token_hex(8)}"


__all__ = [
    "generate_test_cases",
    "next_generation_id",
]
