from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_auxiliary_enhancement.schemas import (
    RequirementAuxiliaryEnhancementOutput,
)


SYSTEM_PROMPT = """
你是 AI 测试系统中的辅助文档增强智能体。

输入包含阶段一发现的问题列表，以及多个辅助文章 Markdown。你的任务是在这些辅助文章中寻找能回答问题的内容。

边界：
- 只处理输入 questions 中的问题。
- 只能引用输入 auxiliary_articles 中的内容。
- 不得引用输入之外的文件、常识或推测。
- 不重新分析完整主需求。
- 不输出完整 RequirementAnalysisOutput，只输出 RequirementAuxiliaryEnhancementOutput JSON。

输出要求：
- 如果辅助文章能直接回答问题，给出 recommended_options，answer_markdown 必须可直接写入初步需求。
- 如果辅助文章内容可补入初步需求，放入 applied_supplements，并附 evidence。
- 如果辅助文章与主需求或文章之间冲突，放入 new_conflicts。
- 如果找不到答案、证据弱或来源不清，记录 unchanged_question_ids 或 resolution=weak_evidence/not_found。
""".strip()


def auxiliary_enhancement_agent(model):
    return create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(RequirementAuxiliaryEnhancementOutput),
    )


async def run_auxiliary_enhancement_agent(
    model,
    user_content: str,
) -> RequirementAuxiliaryEnhancementOutput:
    agent = auxiliary_enhancement_agent(model)
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
        raise ValueError("辅助文档增强智能体未返回结构化结果。")
    return output
