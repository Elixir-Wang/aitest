from dataclasses import dataclass


@dataclass(frozen=True)
class AiCapability:
    id: str
    name: str
    description: str


AI_CAPABILITIES: tuple[AiCapability, ...] = (
    AiCapability(
        id="document_editor",
        name="文档修改",
        description="根据用户指令修改 Markdown 文档，返回修改后的文档、修改摘要和风险提示。",
    ),
    AiCapability(
        id="raw_requirement_format_converter",
        name="需求标准化智能体",
        description="负责将上传的 PDF、Word、TXT 和 Markdown 需求文件标准化为结构稳定的标准 Markdown。",
    ),
    AiCapability(
        id="requirement_analysis",
        name="需求分析智能体",
        description="基于当前主需求 Markdown 工作稿，生成模块分析、澄清问题、可测试性检查和质量门禁结果。",
    ),
    AiCapability(
        id="site_exploration",
        name="站点探索智能体",
        description="使用 Playwright CLI 探索 Web 站点，生成页面事实、模块覆盖、locator 和探索文档。",
    ),
    AiCapability(
        id="knowledge_query",
        name="项目知识库查询智能体",
        description="直接读取最终需求文档和探索记录，使用 Codex agentic search 返回带来源引用的项目知识库答案。",
    ),
    AiCapability(
        id="test_case_generation",
        name="测试用例生成智能体",
        description="根据最终需求文档生成完整、系统、可执行的测试用例集。",
    ),
)


def list_ai_capabilities() -> list[AiCapability]:
    return list(AI_CAPABILITIES)


def get_ai_capability(capability_id: str) -> AiCapability:
    for capability in AI_CAPABILITIES:
        if capability.id == capability_id:
            return capability
    raise KeyError(capability_id)
