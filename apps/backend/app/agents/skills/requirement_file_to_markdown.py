from __future__ import annotations

from app.agents.definitions import SkillDefinition

requirement_file_to_markdown_skill = SkillDefinition(
    id="requirement_file_to_markdown",
    name="需求文件转 Markdown",
    description="将 PDF、Word、TXT 和 Markdown 需求源文件解析为统一 Markdown 工作稿。",
)
