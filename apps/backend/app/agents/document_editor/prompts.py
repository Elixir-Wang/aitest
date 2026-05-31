from __future__ import annotations

from app.schemas.document_editor import DocumentEditInput


def build_document_edit_input(input_data: DocumentEditInput) -> str:
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
