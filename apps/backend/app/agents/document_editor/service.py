from app.agents.document_editor.agent import document_editor_agent
from app.agents.document_editor.schemas import DocumentEditInput, DocumentEditOutput
from app.agents.model_selection import build_agent_model, resolve_model_selection


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
