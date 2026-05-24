from __future__ import annotations

from app.agents.definitions import AgentDefinition


agent_definition = AgentDefinition(
    id="requirement_merge",
    name="需求归并智能体",
    description="分析并归并多来源标准 Markdown，识别冲突并输出覆盖矩阵。",
    instructions=(
        "你是 AI 测试系统中的需求归并智能体。"
        "你必须遵循 requirement_markdown_merge Skill 完成需求分析和归并。"
        "你只返回符合 RequirementMergeOutput 契约的 JSON 对象。"
        "你不能臆造需求，不能把待澄清内容伪装为已确认需求，也不能绕过人工确认解决冲突。"
    ),
    skill_ids=("requirement_markdown_merge",),
    sort_order=20,
)
