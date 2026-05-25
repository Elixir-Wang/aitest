from __future__ import annotations

import json
import re
from typing import Any

from app.agents.runtime import run_agent
from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput


DOCUMENT_EDITOR_AGENT_ID = "document_editor"


async def edit_document(input_data: DocumentEditInput) -> DocumentEditOutput:
    result = await run_agent(DOCUMENT_EDITOR_AGENT_ID, build_document_edit_prompt(input_data))
    return parse_document_edit_output(result.output)


def build_document_edit_prompt(input_data: DocumentEditInput) -> str:
    title = input_data.document_title.strip() or "未命名文档"
    return "\n".join(
        [
            "你将收到一份文档和一条修改指令，请只根据指令修改文档内容。",
            "不要创造未提供、未确认的业务事实；如果指令需要新增事实但文档没有依据，请在 warnings 中说明。",
            "保留原文中与指令无关的结构、标题层级、Markdown 表格、代码块和列表。",
            "只返回 JSON，不要返回 Markdown 围栏或解释性文字。",
            "JSON 字段必须是 status, edited_content, change_summary, warnings。",
            "",
            f"document_type: {input_data.document_type}",
            f"document_title: {title}",
            "",
            "instruction:",
            input_data.instruction.strip(),
            "",
            "document_content:",
            input_data.content,
        ]
    )


def parse_document_edit_output(raw_output: Any) -> DocumentEditOutput:
    if isinstance(raw_output, DocumentEditOutput):
        return raw_output
    if isinstance(raw_output, dict):
        payload = raw_output
    else:
        payload = json.loads(_strip_json_fence(str(raw_output)))
    try:
        return DocumentEditOutput.model_validate(payload)
    except Exception as exc:
        raise ValueError("文档修改智能体返回内容不符合 DocumentEditOutput 契约。") from exc


def _strip_json_fence(value: str) -> str:
    stripped = value.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else stripped
