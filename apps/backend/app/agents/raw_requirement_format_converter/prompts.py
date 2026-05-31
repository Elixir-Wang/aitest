from __future__ import annotations

import json

from app.schemas.requirement_conversion import RequirementConversionInput
from app.services.requirement_markdown_normalizer import normalize_requirement_markdown


def build_requirement_conversion_input(input_data: RequirementConversionInput) -> str:
    payload = input_data.model_copy(
        update={"candidate_markdown": normalize_requirement_markdown(input_data.candidate_markdown)}
    ).model_dump()
    return (
        "请校验并标准化以下原始需求文件转换得到的候选 Markdown。\n"
        "如果 file_format=pdf，必须按 pdf_to_markdown 技能规则根据内容生成合适的 Markdown 标题、章节和列表；"
        "首个像文档名称、产品需求标题、说明书标题的内容必须作为一级标题 `# ...`，"
        "`1. 项目概述` 这类章节必须转为 `## ...`，`1.1 项目背景` 这类子章节必须转为 `### ...`，"
        "不能把 PDF 标准文件继续输出成纯文本墙。\n"
        "必须先使用 markdown_normalize 技能规则处理候选 Markdown：业务流程不得放入普通代码块；"
        "只有明确的跨步骤流程链路才可转换为 Mermaid flowchart TD；"
        "业务逻辑、规则说明、条件判断、字段取值和 action 映射应保持普通 Markdown 列表/段落/表格，"
        "不要仅因多个 ↓ 或 → 转换为 Mermaid。\n\n"
        f"输入：\n{json.dumps(payload, ensure_ascii=False)}"
    )
