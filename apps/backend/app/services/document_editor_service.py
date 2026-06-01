from app.agents.document_editor.agent import document_editor_agent
from app.agents.model_factory import build_agent_model
from app.agents.model_selection import resolve_model_selection
from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput


def edit_document(input_data: DocumentEditInput) -> DocumentEditOutput:
    selection = resolve_model_selection("document_editor")
    model = build_agent_model(selection)
    agent = document_editor_agent(model)

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": _build_document_editor_input(input_data),
                }
            ]
        }
    )

    output = result.get("structured_response")
    if output is None:
        raise ValueError("文档修改智能体未返回结构化结果。")

    _validate_document_edit_output(input_data, output)
    return output


def _build_document_editor_input(input_data: DocumentEditInput) -> str:
    return "\n".join(
        [
            "instruction:",
            input_data.instruction.strip(),
            "",
            "document_content:",
            input_data.content,
        ]
    )


def _validate_document_edit_output(input_data: DocumentEditInput, output: DocumentEditOutput) -> None:
    if not output.change_summary.strip():
        raise ValueError("文档修改返回的 change_summary 不能为空。")

    original = input_data.content.strip()
    edited = output.edited_content.strip()
    if not edited:
        return

    if original and len(edited) < max(50, int(len(original) * 0.2)):
        raise ValueError("文档修改输出疑似异常缩水。")
