from app.agents.definitions import AgentDefinition
from app.schemas.requirement_conversion import RequirementConversionOutput


agent_definition = AgentDefinition(
    id="raw_requirement_format_converter",
    name="格式转换智能体",
    description="负责将上传的 PDF、Word、TXT 和 Markdown 需求文件解析为 Markdown 工作稿。",
    instructions=(
        "你是 AI 测试系统中的格式转换智能体。"
        "你的职责是把上传的 Word、PDF、TXT、Markdown 等原始需求文件转换成结构稳定的 Markdown 标准文件。"
        "你只负责格式转换质量检查和 Markdown 标准化，不得创造、补充或推断业务需求。"
        "你必须保留原文中已有的需求、标题、列表、表格、链接和图片引用。"
        "你应删除明显的转换噪声、页码、重复页眉页脚。"
        "如果候选内容不足以形成可读 Markdown，必须如实返回 warnings。"
        "你只返回符合 RequirementConversionOutput 契约的结果。"
    ),
    skill_ids=("pdf_to_markdown", "docx_to_markdown", "markdown_normalize"),
    sort_order=10,
    output_type=RequirementConversionOutput,
)
