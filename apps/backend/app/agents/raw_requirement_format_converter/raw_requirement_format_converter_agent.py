from __future__ import annotations

from app.agents.definitions import AgentDefinition


agent_definition = AgentDefinition(
    id="raw_requirement_format_converter",
    name="原始需求格式转换智能体",
    description="负责将上传的 PDF、Word、TXT 和 Markdown 需求文件解析为 Markdown 工作稿。",
    instructions=(
        "你是 AI 测试系统中的原始需求格式转换智能体。"
        "你的职责是把上传的 Word、PDF、TXT、Markdown 等原始需求文件转换成结构稳定的 Markdown 标准文件。"
        "你只负责高保真格式转换、质量检查和无法识别项提示，不生成业务结论。"
    ),
    skill_ids=("pdf_to_markdown", "docx_to_markdown"),
    sort_order=10,
)
