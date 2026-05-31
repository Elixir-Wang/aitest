from __future__ import annotations

from typing import Any

from agents import Runner

from app.ai_agents.document_editor.agent import document_editor_agent
from app.ai_agents.run_config import build_run_config
from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput


async def edit_document(input_data: DocumentEditInput, *, actor_id: str | None = None) -> DocumentEditOutput:
    _validate_document_edit_input(input_data)
    result = await Runner.run(
        document_editor_agent,
        _build_document_editor_input(input_data),
        context=input_data,
        run_config=build_run_config("document_editor", actor_id=actor_id),
    )
    return _coerce_document_edit_output(result.final_output)


def _validate_document_edit_input(input_data: DocumentEditInput) -> None:
    if not input_data.content.strip():
        raise ValueError("待修改文档不能为空。")
    if not input_data.instruction.strip():
        raise ValueError("修改指令不能为空。")


def _build_document_editor_input(input_data: DocumentEditInput) -> str:
    title = input_data.document_title.strip() or "未命名文档"
    return "\n".join(
        [
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


def _coerce_document_edit_output(output: Any) -> DocumentEditOutput:
    if isinstance(output, DocumentEditOutput):
        return output
    return DocumentEditOutput.model_validate(output)
