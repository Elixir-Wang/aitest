# Document Editor Compact Output Spec

## Background

The document editor agent currently returns four fields:

```python
class DocumentEditOutput(BaseModel):
    status: Literal["edited", "unchanged"]
    edited_content: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
```

In the current frontend flow, the effective fields are `edited_content` and `change_summary`:

- `edited_content` is saved as the updated standard Markdown content.
- `change_summary` is saved into the document version change summary and shown in success feedback.

`status` is declared in the frontend response type but is not used to decide whether to save. `warnings` is displayed as a toast, but the same information can be folded into `change_summary` for this lightweight document editing flow.

For long Markdown documents, returning the original full document when no edit is needed wastes output tokens. The new contract should allow `edited_content` to be empty when no actual change is made, and the frontend should keep the existing document unchanged in that case.

## Goals

- Reduce `DocumentEditOutput` to two fields: `edited_content` and `change_summary`.
- Allow `edited_content` to be an empty string when the agent does not modify the document.
- Require the frontend to skip saving when `edited_content` is empty or whitespace-only.
- Keep `change_summary` mandatory so the user still receives a reason when no edit happens.
- Preserve the current API path: `POST /agents/document-editor/run`.
- Preserve the document editing guardrails: explicit user instruction only, no unsupported business facts, minimal Markdown changes.

## Non-Goals

- Do not redesign the requirement document editing UI.
- Do not change the standard Markdown save API.
- Do not add a separate warning channel.
- Do not introduce diff-based patch application in this change.
- Do not change model selection, provider configuration, or LangChain agent creation.

## Contract

### Backend Response Schema

`DocumentEditOutput` should become:

```python
from pydantic import BaseModel, Field


class DocumentEditOutput(BaseModel):
    edited_content: str = Field(
        default="",
        description="修改后的完整 Markdown。只有实际修改文档时返回完整内容；未修改时必须返回空字符串。",
    )
    change_summary: str = Field(
        min_length=1,
        description="本次处理摘要。实际修改时说明改了什么；未修改、依据不足、指令歧义、无法定位或只完成部分修改时，也必须在这里说明。",
    )
```

Field semantics:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `edited_content` | `str` | No, default `""` | Full edited Markdown only when a real edit was made. Empty string means no document update should be saved. |
| `change_summary` | `str` | Yes | User-facing summary. When no edit is made, explain why. If the instruction lacks document support, explain the risk here. |

### Removed Fields

| Field | Reason |
| --- | --- |
| `status` | The frontend can derive "changed vs unchanged" from `edited_content.trim()`. Keeping both creates duplicate state. |
| `warnings` | The current flow only needs one user-facing explanation channel. Risk and limitation messages should be written into `change_summary`. |

## Prompt Rules

The agent system prompt should no longer mention `status` or `warnings`.

Recommended prompt:

```text
你是 Markdown 文档修改智能体，只根据用户明确指令修改当前文档。

编辑规则：
1. 采用最小修改原则，只修改用户明确要求的内容。
2. 必须保留与修改无关的内容、标题层级、段落顺序、Markdown 表格、代码块、列表、链接和整体结构。
3. 不得主动扩写、润色、总结、重组全文。
4. 不得新增当前文档没有依据、且用户未明确确认的业务事实，包括接口、字段、流程、角色、状态、规则和约束。
5. 如果用户明确要求新增或改写，但当前文档缺少依据，可以执行，但必须在 change_summary 中说明依据不足。
6. 无法确定修改位置或修改意图时，不要猜测，edited_content 返回空字符串，并在 change_summary 中说明未修改原因。

输出必须符合 DocumentEditOutput 结构化结果：
- edited_content：只有实际修改文档时，返回修改后的完整 Markdown；未修改时返回空字符串。
- change_summary：本次处理摘要；未修改、依据不足、指令歧义、无法定位或只完成部分修改时，也必须在这里说明。
```

## Backend Changes

### Files

- Modify `apps/backend/app/schemas/document_editor.py`
- Modify `apps/backend/app/agents/document_editor/agent.py`
- Modify `apps/backend/app/services/document_editor_service.py`
- Modify `apps/backend/tests/test_document_editor_agent.py`

### Schema

Update `DocumentEditOutput` to the two-field contract.

Remove unused import:

```python
from typing import Literal
```

Keep `DocumentEditInput` unchanged.

### Agent Prompt

Update `SYSTEM_PROMPT`:

- Remove `status 只能是 edited 或 unchanged。`
- Remove references to `warnings`.
- Add the rule that no-change output must set `edited_content` to an empty string and explain the reason in `change_summary`.

### Service Validation

Current validation rejects empty `edited_content`:

```python
if not output.edited_content.strip():
    raise ValueError("文档修改返回的 edited_content 不能为空。")
```

This must be removed.

New validation rules:

```python
def _validate_document_edit_output(input_data: DocumentEditInput, output: DocumentEditOutput) -> None:
    if not output.change_summary.strip():
        raise ValueError("文档修改返回的 change_summary 不能为空。")

    edited = output.edited_content.strip()
    if not edited:
        return

    original = input_data.content.strip()
    if original and len(edited) < max(50, int(len(original) * 0.2)):
        raise ValueError("文档修改输出疑似异常缩水。")
```

Rationale:

- Empty `edited_content` is valid and means no save should happen.
- Abnormal shrink validation still protects actual edited content.
- `change_summary` remains mandatory for user feedback.

### Backend Tests

Update existing tests:

- Remove `status="edited"` and `warnings=[]` from `DocumentEditOutput(...)`.
- Keep the structured response test for a normal edit.
- Add a no-change test where `edited_content=""` is accepted.
- Keep the missing `structured_response` test.

Required new test case:

```python
def test_document_editor_service_allows_empty_content_for_unchanged_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_content = "# Old title\n\n" + "Body line.\n" * 20
    from app.services.document_editor_service import edit_document

    output = DocumentEditOutput(
        edited_content="",
        change_summary="未修改：未找到需要调整的内容。",
    )

    class FakeAgent:
        def invoke(self, payload):
            return {"structured_response": output}

    monkeypatch.setattr("app.services.document_editor_service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.services.document_editor_service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.services.document_editor_service.document_editor_agent", lambda model: FakeAgent())

    result = edit_document(
        DocumentEditInput(
            document_type="markdown",
            document_title="Old title",
            content=original_content,
            instruction="如果没有问题就不要修改",
        )
    )

    assert result is output
    assert result.edited_content == ""
    assert result.change_summary.startswith("未修改")
```

## Frontend Changes

### Files

- Modify `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`

### Type Contract

Update:

```ts
type DocumentEditResponse = {
  status: "edited" | "unchanged";
  edited_content: string;
  change_summary: string;
  warnings: string[];
};
```

to:

```ts
type DocumentEditResponse = {
  edited_content: string;
  change_summary: string;
};
```

### Save Flow

After receiving `editResult`, check `edited_content` before calling the standard Markdown save API.

Required behavior:

```ts
const editedContent = editResult.edited_content.trim();
if (!editedContent) {
  toast.info(editResult.change_summary || "AI 未修改文档");
  return;
}
```

Then use the original `editResult.edited_content` for saving, not the trimmed value, so intentional leading/trailing Markdown whitespace is not lost:

```ts
body: JSON.stringify({
  markdown_content: editResult.edited_content,
  change_summary: `AI修改：${editResult.change_summary}`,
}),
```

Remove warning toast handling:

```ts
if (editResult.warnings.length > 0) {
  toast.warning(...)
} else {
  toast.success(...)
}
```

Replace it with:

```ts
toast.success(editResult.change_summary || "AI修改已保存");
```

### Loading State

The current `finally` block already clears `editingStandardWithAi` and the running task. Keep that behavior. Returning early after empty `edited_content` must still run the `finally` block.

## Acceptance Criteria

- `DocumentEditOutput` has only `edited_content` and `change_summary`.
- `edited_content` can be an empty string.
- `change_summary` remains required and non-empty.
- The document editor prompt no longer mentions `status` or `warnings`.
- The prompt explicitly says no-change results return `edited_content=""`.
- Backend service accepts empty `edited_content` without raising.
- Backend shrink protection still applies when `edited_content` is non-empty.
- Frontend response type no longer contains `status` or `warnings`.
- Frontend skips the save API call when `edited_content.trim()` is empty.
- No-change results keep the original Markdown content unchanged.
- Successful edits still save the full returned Markdown content.
- Successful edits still save `AI修改：${change_summary}` as the version summary.

## Verification

Backend:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_editor_agent.py -q
```

Frontend:

```powershell
cd D:\project\test_project\apps\frontend
npm run lint
```

Manual verification:

1. Open a requirement standard file.
2. Ask AI to make a real, small edit.
3. Confirm the standard file is saved and the version summary uses `AI修改：...`.
4. Ask AI to make a no-op instruction such as "如果没有错别字就不要修改".
5. Confirm the UI shows the no-change summary and does not call the Markdown save endpoint.
