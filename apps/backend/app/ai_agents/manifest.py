from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AiAgentManifestItem:
    id: str
    name: str
    description: str
    model: str = "gpt-5.4-mini"
    skill_ids: tuple[str, ...] = field(default_factory=tuple)


AI_AGENT_MANIFEST: tuple[AiAgentManifestItem, ...] = (
    AiAgentManifestItem(
        id="raw_requirement_format_converter",
        name="格式转换智能体",
        description="负责将上传的 PDF、Word、TXT 和 Markdown 需求文件解析为 Markdown 工作稿。",
        skill_ids=("pdf_to_markdown", "docx_to_markdown", "markdown_normalize"),
    ),
    AiAgentManifestItem(
        id="requirement_merge",
        name="需求归并智能体",
        description="分析并归并多来源标准 Markdown，识别冲突并输出覆盖矩阵。",
        skill_ids=("requirement_markdown_merge",),
    ),
    AiAgentManifestItem(
        id="document_editor",
        name="文档修改智能体",
        description="根据用户指令修改任意 Markdown 文档，返回修改后的文档、修改摘要和风险提示。",
    ),
    AiAgentManifestItem(
        id="requirement_analysis",
        name="需求分析智能体",
        description="基于已归并的需求 Markdown 工作稿，生成模块分析、澄清问题、可测试性检查和质量门禁结果。",
        skill_ids=("requirement_analysis",),
    ),
    AiAgentManifestItem(
        id="site_exploration",
        name="站点探索智能体",
        description="使用 Playwright CLI 探索 Web 站点，生成页面事实、模块覆盖、locator 和探索文档。",
        skill_ids=("playwright_cli", "site_exploration"),
    ),
    AiAgentManifestItem(
        id="knowledge_builder",
        name="知识库构建智能体",
        description="基于已确认需求版本和已完成探索结果，生成 Karpathy llm-wiki 风格的项目知识库。",
        skill_ids=("karpathy_llm_wiki",),
    ),
)


def list_ai_agents() -> list[AiAgentManifestItem]:
    return list(AI_AGENT_MANIFEST)


def get_ai_agent(agent_id: str) -> AiAgentManifestItem:
    for agent in AI_AGENT_MANIFEST:
        if agent.id == agent_id:
            return agent
    raise KeyError(agent_id)
