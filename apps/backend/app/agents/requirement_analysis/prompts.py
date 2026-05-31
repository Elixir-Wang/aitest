from __future__ import annotations

import json

from app.schemas.requirement_analysis import RequirementAnalysisInput


def build_requirement_analysis_input(input_data: RequirementAnalysisInput) -> str:
    return f"输入：\n{json.dumps(input_data.model_dump(), ensure_ascii=False)}"
