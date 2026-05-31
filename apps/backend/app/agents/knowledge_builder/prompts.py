from __future__ import annotations

import json

from app.schemas.knowledge import KnowledgeBuildInput


def build_knowledge_builder_input(input_data: KnowledgeBuildInput) -> str:
    return f"输入：\n{json.dumps(input_data.model_dump(), ensure_ascii=False)}"
