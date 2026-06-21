"""测试用例生成服务层"""

import secrets

from app.agents.model_selection import build_agent_model, resolve_model_selection
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

    # 添加公司知识库标记
    if input_data.include_company_knowledge:
        content_parts.append("")
        content_parts.append("注意: 需要结合公司测试规范和最佳实践。")

    content_parts.append("\n请使用 test-case-generation skill 生成测试用例集。")
    content = "\n".join(content_parts)

    # 调用 Agent
    model = build_agent_model(resolve_model_selection(CAPABILITY_ID))
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
