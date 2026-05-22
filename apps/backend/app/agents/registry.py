from __future__ import annotations

from app.agents.definitions import AgentDefinition


class AgentRegistry:
    def __init__(self, agents: list[AgentDefinition]) -> None:
        self._agents = {agent.id: agent for agent in agents}

    def list(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def get(self, agent_id: str) -> AgentDefinition:
        return self._agents[agent_id]


agent_registry = AgentRegistry(
    [
        AgentDefinition(
            id="requirement_file_parser",
            name="需求文件解析智能体",
            description="负责将上传的 PDF、Word、TXT 和 Markdown 需求文件解析为 Markdown 工作稿。",
            instructions=(
                "你是 AI 测试系统中的需求文件解析智能体。"
                "你需要将 PDF、Word、TXT 和 Markdown 源文件转换为结构清晰的 Markdown 工作稿，"
                "尽量保留标题、段落、列表和表格信息，并为后续需求分析提供稳定输入。"
            ),
            skill_ids=("requirement_file_to_markdown",),
        ),
    ]
)
