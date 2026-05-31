from __future__ import annotations

from agents import Agent

from app.ai_agents.document_editor.guardrails import document_edit_output_guardrail
from app.schemas.document_editor import DocumentEditOutput


DOCUMENT_EDITOR_INSTRUCTIONS = """
你是 AI 测试系统中的通用文档修改智能体。
你的输入可以来自需求、知识库、站点探索、报告等不同模块。
你只负责按用户明确指令修改当前文档内容，不能新增未经文档支持或用户确认的业务事实。
如果用户指令要求新增事实，但当前文档没有依据，你必须在 warnings 中说明。
你必须保留与修改指令无关的内容、标题层级、Markdown 表格、代码块、列表和整体结构。
输出必须符合 DocumentEditOutput 契约。
status 只能是 edited 或 unchanged。
""".strip()


document_editor_agent = Agent(
    name="文档修改智能体",
    instructions=DOCUMENT_EDITOR_INSTRUCTIONS,
    output_type=DocumentEditOutput,
    output_guardrails=[document_edit_output_guardrail],
)
