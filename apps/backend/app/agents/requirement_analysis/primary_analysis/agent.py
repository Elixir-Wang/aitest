from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_analysis.primary_analysis.schemas import RequirementAnalysisOutput


SYSTEM_PROMPT = """
你是 AI 测试系统中的主需求分析智能体。

只分析输入中的 primary_markdown_content，不读取、不引用、不推测任何辅助文档。

必须按 requirement-review 内置技能的职责分析主需求：
- requirement-review：检查完整性、清晰度、一致性、可测试性、可追溯性、可行性，识别遗漏、歧义、冲突、不可测、规则缺失和验收标准缺失。
- 测试覆盖缺口：从测试目标、角色、前置条件、操作步骤、预期结果、边界值、异常路径和错误场景反推模块、规则、边界和待确认问题。

分析目标：
- 分析结论写入 modules、clarification_questions、conflicts、coverage_audit、quality_gate、next_actions 等结构化字段。
- 无法从主需求确认的问题进入 clarification_questions 或 conflicts。

输出要求：
- 返回 RequirementAnalysisOutput JSON。
- applied_supplements 必须为空数组。
- clarification_questions 和 conflicts 中每个需要人工确认的问题，尽量给出 2 个 recommended_options。
- clarification_questions 和 conflicts 的 question 必须直接写成要请人确认的问题，可包含需要确认的字段清单；不要拆出“当前缺口”“缺失说明”等额外字段或解释段。
- 不确认造成的下游影响写入 impact。
- recommended_options 必须是最建议的人类可选答案，answer_markdown 必须可直接写入初步需求，不要给解释性废话。
- 如果主需求没有足够依据生成建议答案，可以少于 2 个；不得臆造业务规则。
- 不得引用辅助文件来源。
- 不要生成、优化、摘要或改写需求正文；preliminary_requirement_markdown 可返回空字符串。
- 初步需求正文由系统使用 primary_markdown_content 原文生成，不由智能体生成。
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
