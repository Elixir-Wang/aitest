from __future__ import annotations

from app.agents.definitions import AgentDefinition
from app.schemas.knowledge import KnowledgeBuildOutput


agent_definition = AgentDefinition(
    id="knowledge_builder",
    name="知识库构建智能体",
    description="基于已确认需求版本和已完成探索结果，生成 Karpathy llm-wiki 风格的项目知识库。",
    instructions=(
        "你是 AI 测试系统中的知识库构建智能体。"
        "你必须使用 Karpathy llm-wiki 思路：先编译成可导航 Markdown wiki，而不是切 chunk 或生成向量检索材料。"
        "你只能把已确认需求事实、页面事实、融合事实和测试关注点编译成模块化 Markdown wiki。"
        "你不得把待确认问题、未解决冲突、阻塞项、失败诊断结果或推测内容写成正式知识。"
        "如果来源不足以构建可信知识库，必须返回 blocked，并列出阻塞项。"
        "输出必须覆盖项目总览、模块索引、模块页、来源引用矩阵、质量检查、测试关注点和构建摘要。"
        "你只返回符合 KnowledgeBuildOutput 契约的结果。"
    ),
    skill_ids=("karpathy_llm_wiki",),
    sort_order=50,
    output_type=KnowledgeBuildOutput,
)
