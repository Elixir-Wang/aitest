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
        id="requirement_merge",
        name="需求归并智能体",
        description="分析并归并多来源标准 Markdown，识别冲突并输出覆盖矩阵。",
    ),
    AiCapability(
        id="requirement_analysis",
        name="需求分析智能体",
        description="基于已归并的需求 Markdown 工作稿，生成模块分析、澄清问题、可测试性检查和质量门禁结果。",
    ),
    AiCapability(
        id="site_exploration",
        name="站点探索智能体",
        description="使用 Playwright CLI 探索 Web 站点，生成页面事实、模块覆盖、locator 和探索文档。",
    ),
    AiCapability(
        id="knowledge_builder",
        name="知识库构建智能体",
        description="基于已确认需求版本和已完成探索结果，生成 Karpathy llm-wiki 风格的项目知识库。",
    ),
)


def list_ai_capabilities() -> list[AiCapability]:
    return list(AI_CAPABILITIES)


def get_ai_capability(capability_id: str) -> AiCapability:
    for capability in AI_CAPABILITIES:
        if capability.id == capability_id:
            return capability
    raise KeyError(capability_id)
