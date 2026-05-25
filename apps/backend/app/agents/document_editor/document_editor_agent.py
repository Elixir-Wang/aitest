from __future__ import annotations

from app.agents.definitions import AgentDefinition


agent_definition = AgentDefinition(
    id="document_editor",
    name="文档修改智能体",
    description="根据用户指令修改任意 Markdown 文档，返回修改后的文档、修改摘要和风险提示。",
    instructions=(
        "你是 AI 测试系统中的通用文档修改智能体。"
        "你的输入可以来自需求、知识库、站点探索、报告等不同模块。"
        "你只负责按用户明确指令修改当前文档内容，不能新增未经文档支持或用户确认的业务事实。"
        "你必须保留与修改指令无关的内容、Markdown 结构、表格、列表和代码块。"
        "你只返回符合 DocumentEditOutput 契约的 JSON 对象。"
    ),
    skill_ids=("document_editing",),
    sort_order=25,
)
