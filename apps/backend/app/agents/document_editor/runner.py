from __future__ import annotations

import json
import re
from typing import Any

from app.agents.document_editor.prompts import build_document_edit_input
from app.agents.runtime import run_agent
from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput


DOCUMENT_EDITOR_AGENT_ID = "document_editor"


async def run_document_editor(input_data: DocumentEditInput) -> DocumentEditOutput:
    result = await run_agent(DOCUMENT_EDITOR_AGENT_ID, build_document_edit_input(input_data))
    return parse_document_edit_output(result.output)


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
