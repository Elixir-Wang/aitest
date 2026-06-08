from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_analysis.primary_analysis.schemas import RequirementAnalysisOutput


SYSTEM_PROMPT = """
你是 AI 测试系统中的主需求分析智能体。

只分析输入中的 primary_markdown_content，不读取、不引用、不推测任何辅助文档。

分析目标：
- 识别主需求的遗漏、歧义、冲突、不可测、规则缺失和验收标准缺失。
- 从测试视角反推角色、前置条件、操作步骤、预期结果、边界值和异常路径缺口。
- 生成基于主需求的 preliminary_requirement_markdown。
- 无法从主需求确认的问题进入 clarification_questions 或 conflicts。

输出要求：
- 返回 RequirementAnalysisOutput JSON。
- applied_supplements 必须为空数组。
- 不得引用辅助文件来源。
- preliminary_requirement_markdown 不能为空。
""".strip()


def primary_analysis_agent(model):
    return create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(RequirementAnalysisOutput),
    )


async def run_primary_analysis_agent(model, user_content: str) -> RequirementAnalysisOutput:
    agent = primary_analysis_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": user_content,
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("需求分析智能体未返回结构化结果。")
    return output
