from __future__ import annotations

from agents import GuardrailFunctionOutput, RunContextWrapper, output_guardrail

from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput


@output_guardrail(name="document_edit_output_guardrail")
def document_edit_output_guardrail(
    ctx: RunContextWrapper[DocumentEditInput],
    agent,
    output: DocumentEditOutput,
) -> GuardrailFunctionOutput:
    issues: list[str] = []
    if not output.edited_content.strip():
        issues.append("文档修改智能体返回的 edited_content 不能为空。")
    if not output.change_summary.strip():
        issues.append("文档修改智能体返回的 change_summary 不能为空。")

    original = ctx.context.content.strip()
    edited = output.edited_content.strip()
    if original and len(edited) < max(50, int(len(original) * 0.2)):
        issues.append("文档修改智能体输出疑似异常缩水。")

    return GuardrailFunctionOutput(
        output_info={"issues": issues},
        tripwire_triggered=bool(issues),
    )
