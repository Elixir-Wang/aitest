from langchain.agents import create_agent

from app.agents.knowledge_chat.schemas import KnowledgeQueryOutput


BASE_SYSTEM_PROMPT = """
你是 AI 测试系统的项目知识库 AI。

默认情况下，你可以像普通助手一样进行多轮对话。
以下情况不要调用 search_project_knowledge：
- 问候、闲聊、确认在线状态。
- 介绍你能做什么。
- 普通写作、改写、翻译、总结用户刚输入的文本。
- 只讨论对话本身，不需要项目事实。

以下情况必须调用 search_project_knowledge：
- 用户询问当前项目的需求、业务规则、模块范围、页面、流程、接口、测试风险。
- 用户要求基于最终需求文档或探索记录回答。
- 用户要求来源、依据、引用、文档位置。
- 用户追问上一轮中已经涉及的项目事实。

不得凭常识编造项目事实。
如果问题需要项目事实，要调用工具；如果工具没有找到依据，要说明缺口。
如果没有调用工具，source_refs、used_requirement_versions、used_exploration_runs 必须为空，knowledge_queried 必须为 false。
如果调用了工具，knowledge_queried 必须为 true，并保留工具返回的来源和使用记录。
""".strip()

STRUCTURED_OUTPUT_INSTRUCTION = """
输出必须符合 KnowledgeQueryOutput 结构化结果。
""".strip()

STREAM_OUTPUT_INSTRUCTION = """
直接输出用户可见的自然语言答案，不要输出 JSON。
来源引用和使用记录由系统根据工具结果单独处理，不要在正文里伪造来源元数据。
""".strip()


def knowledge_chat_agent(model, tools, *, structured_output: bool = True):
    system_prompt = "\n\n".join(
        [
            BASE_SYSTEM_PROMPT,
            STRUCTURED_OUTPUT_INSTRUCTION if structured_output else STREAM_OUTPUT_INSTRUCTION,
        ]
    )
    kwargs = {
        "model": model,
        "tools": tools,
        "system_prompt": system_prompt,
    }
    if structured_output:
        kwargs["response_format"] = KnowledgeQueryOutput
    return create_agent(**kwargs)
