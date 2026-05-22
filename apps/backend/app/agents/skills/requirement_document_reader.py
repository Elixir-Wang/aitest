from __future__ import annotations

from app.agents.definitions import SkillDefinition

requirement_document_reader_skill = SkillDefinition(
    id="requirement_document_reader",
    name="需求文档读取",
    description="读取和理解项目需求文档，为后续需求解析、澄清和测试设计提供上下文。",
)
