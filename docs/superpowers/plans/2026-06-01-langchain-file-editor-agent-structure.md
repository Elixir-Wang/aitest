# LangChain Document Editor Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the document editor as the first LangChain `create_agent` based agent under the new `app/agents` directory.

**Architecture:** `app/agents` becomes the new LangChain/DeepAgents agent root. The document editor agent lives in `app/agents/document_editor` with only `agent.py`, `schemas.py`, and `tools.py`. Business execution belongs in `app/services/document_editor_service.py`; FastAPI keeps the existing `/agents/document-editor/run` path and calls the service.

**Tech Stack:** FastAPI, Pydantic, LangChain `create_agent`, `langchain-openai`, existing `ai_runtime.model_selection`.

---

## File Structure

Create:

```text
apps/backend/app/agents/__init__.py
apps/backend/app/agents/document_editor/__init__.py
apps/backend/app/agents/document_editor/agent.py
apps/backend/app/agents/document_editor/schemas.py
apps/backend/app/agents/document_editor/tools.py
apps/backend/app/agents/model_factory.py
apps/backend/app/services/document_editor_service.py
apps/backend/tests/test_document_editor_agent.py
```

Modify:

```text
apps/backend/pyproject.toml
apps/backend/app/ai_runtime/capabilities.py
apps/backend/app/api/v1/agents.py
apps/backend/app/services/agent_service.py
apps/backend/tests/test_ai_agent_model_assignments.py
apps/backend/tests/test_ai_agents_architecture.py
```

Delete:

```text
apps/backend/app/llm_tasks/document_editor.py
```

Do not create:

```text
apps/backend/app/agents/document_editor/runner.py
apps/backend/app/agents/document_editor/prompts.py
apps/backend/app/agents/document_editor/skills.py
apps/backend/app/agents/document_editor/subagents.py
apps/backend/app/agents/document_editor/evals/
apps/backend/app/runtime/
```

---

### Task 1: Dependencies

**Files:**
- Modify: `apps/backend/pyproject.toml`

- [ ] **Step 1: Add LangChain dependencies**

Add these dependencies to `[project].dependencies`:

```toml
"langchain>=1.0.0",
"langchain-openai>=1.0.0",
```

- [ ] **Step 2: Verify dependency metadata**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pip install -e .
```

Expected: install completes without dependency resolution errors.

---

### Task 2: Capability Type Update

**Files:**
- Modify: `apps/backend/app/ai_runtime/capabilities.py`
- Modify: `apps/backend/tests/test_ai_agent_model_assignments.py`

- [ ] **Step 1: Update tests for document editor as agent**

Change the document editor assertions in `apps/backend/tests/test_ai_agent_model_assignments.py` so they expect:

```python
def test_ai_capabilities_include_document_editor_as_agent() -> None:
    capability = get_ai_capability("document_editor")
    assert capability.name == "文档修改"
    assert capability.kind == "agent"


def test_agent_capabilities_include_document_editor() -> None:
    ids = [capability.id for capability in list_agent_capabilities()]
    assert "document_editor" in ids
    assert "requirement_merge" in ids


def test_llm_task_capabilities_exclude_document_editor() -> None:
    ids = [capability.id for capability in list_llm_task_capabilities()]
    assert "document_editor" not in ids
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_ai_agent_model_assignments.py -q
```

Expected: FAIL because `document_editor` is still `llm_task`.

- [ ] **Step 3: Change capability kind**

In `apps/backend/app/ai_runtime/capabilities.py`, change:

```python
kind="llm_task",
```

to:

```python
kind="agent",
```

for the `document_editor` capability.

- [ ] **Step 4: Run capability tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_ai_agent_model_assignments.py -q
```

Expected: PASS.

---

### Task 3: Document Editor Agent Package

**Files:**
- Create: `apps/backend/app/agents/__init__.py`
- Create: `apps/backend/app/agents/document_editor/__init__.py`
- Create: `apps/backend/app/agents/document_editor/schemas.py`
- Create: `apps/backend/app/agents/document_editor/tools.py`
- Create: `apps/backend/app/agents/document_editor/agent.py`
- Test: `apps/backend/tests/test_document_editor_agent.py`

- [ ] **Step 1: Write agent package tests**

Create `apps/backend/tests/test_document_editor_agent.py`:

```python
from __future__ import annotations

import pytest

from app.agents.document_editor import schemas
from app.agents.document_editor.agent import create_document_editor_agent
from app.agents.document_editor.tools import tools
from app.schemas.document_editor import DocumentEditOutput


def test_document_editor_agent_schemas_reuse_api_contract() -> None:
    assert schemas.DocumentEditOutput is DocumentEditOutput


def test_document_editor_tools_are_empty_for_payload_based_editing() -> None:
    assert tools == []


def test_create_document_editor_agent_uses_langchain_create_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {}

    def fake_create_agent(**kwargs):
        calls.update(kwargs)
        return "agent"

    monkeypatch.setattr("app.agents.document_editor.agent.create_agent", fake_create_agent)

    agent = create_document_editor_agent("model")

    assert agent == "agent"
    assert calls["model"] == "model"
    assert calls["tools"] == []
    assert calls["response_format"] is DocumentEditOutput
    assert "文档修改智能体" in calls["system_prompt"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_editor_agent.py -q
```

Expected: FAIL because `app.agents.document_editor` does not exist.

- [ ] **Step 3: Create schemas re-export**

Create `apps/backend/app/agents/document_editor/schemas.py`:

```python
from __future__ import annotations

from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput

__all__ = ["DocumentEditInput", "DocumentEditOutput"]
```

- [ ] **Step 4: Create empty tool binding**

Create `apps/backend/app/agents/document_editor/tools.py`:

```python
from __future__ import annotations

tools = []
```

- [ ] **Step 5: Create agent factory**

Create `apps/backend/app/agents/document_editor/agent.py`:

```python
from __future__ import annotations

from langchain.agents import create_agent

from .schemas import DocumentEditOutput
from .tools import tools


SYSTEM_PROMPT = """
你是 AI 测试系统中的文档修改智能体。
你只根据用户明确指令修改当前文档。
你不能新增未经文档支持或用户确认的业务事实。
如果用户指令要求新增事实，但当前文档没有依据，你必须在 warnings 中说明。
你必须保留与修改指令无关的内容、标题层级、Markdown 表格、代码块、列表和整体结构。
你必须返回符合 DocumentEditOutput 契约的结构化结果。
status 只能是 edited 或 unchanged。
""".strip()


def create_document_editor_agent(model):
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        response_format=DocumentEditOutput,
    )
```

- [ ] **Step 6: Create package exports**

Create `apps/backend/app/agents/__init__.py` as empty.

Create `apps/backend/app/agents/document_editor/__init__.py`:

```python
from .agent import create_document_editor_agent
from .schemas import DocumentEditInput, DocumentEditOutput

__all__ = [
    "DocumentEditInput",
    "DocumentEditOutput",
    "create_document_editor_agent",
]
```

- [ ] **Step 7: Run agent package tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_editor_agent.py -q
```

Expected: PASS.

---

### Task 4: Agent Model Factory

**Files:**
- Create: `apps/backend/app/agents/model_factory.py`
- Test: `apps/backend/tests/test_document_editor_agent.py`

- [ ] **Step 1: Add agent model factory tests**

Append to `apps/backend/tests/test_document_editor_agent.py`:

```python
from app.agents.model_factory import build_agent_model
from app.ai_runtime.model_selection import ModelSelection


def test_build_agent_model_maps_openai_compatible_to_openai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {}

    def fake_init_chat_model(**kwargs):
        calls.update(kwargs)
        return "chat-model"

    monkeypatch.setattr("app.agents.model_factory.init_chat_model", fake_init_chat_model)

    model = build_agent_model(
        ModelSelection(
            capability_id="document_editor",
            capability_kind="agent",
            model_provider_id="mp-deepseek",
            provider="deepseek",
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key="sk-test",
            model_status="enabled",
        )
    )

    assert model == "chat-model"
    assert calls == {
        "model": "deepseek-chat",
        "model_provider": "openai",
        "api_key": "sk-test",
        "base_url": "https://api.deepseek.com",
        "temperature": 0,
    }
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_editor_agent.py -q
```

Expected: FAIL because `app.agents.model_factory` does not exist.

- [ ] **Step 3: Implement agent model factory**

Create `apps/backend/app/agents/model_factory.py`:

```python
from __future__ import annotations

from langchain.chat_models import init_chat_model

from app.ai_runtime.model_selection import ModelSelection, normalize_provider


def build_agent_model(selection: ModelSelection):
    provider = normalize_provider(selection.provider)
    model_provider = "openai" if provider == "openai-compatible" else provider
    return init_chat_model(
        model=selection.model,
        model_provider=model_provider,
        api_key=selection.api_key,
        base_url=selection.base_url,
        temperature=0,
    )
```

- [ ] **Step 4: Run agent model factory tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_editor_agent.py -q
```

Expected: PASS.

---

### Task 5: Document Editor Service

**Files:**
- Create: `apps/backend/app/services/document_editor_service.py`
- Test: `apps/backend/tests/test_document_editor_agent.py`

- [ ] **Step 1: Add service tests**

Append to `apps/backend/tests/test_document_editor_agent.py`:

```python
from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput
from app.services.document_editor_service import edit_document


def test_document_editor_service_returns_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    output = DocumentEditOutput(
        status="edited",
        edited_content="# New title\n\nBody",
        change_summary="Updated title.",
        warnings=[],
    )

    class FakeAgent:
        def invoke(self, payload):
            assert payload["messages"][0]["role"] == "user"
            assert "instruction:" in payload["messages"][0]["content"]
            assert "document_content:" in payload["messages"][0]["content"]
            return {"structured_response": output}

    monkeypatch.setattr("app.services.document_editor_service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.services.document_editor_service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.services.document_editor_service.create_document_editor_agent", lambda model: FakeAgent())

    result = edit_document(
        DocumentEditInput(
            document_type="markdown",
            document_title="Old title",
            content="# Old title\n\nBody",
            instruction="把标题改成 New title",
        )
    )

    assert result is output


def test_document_editor_service_rejects_missing_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAgent:
        def invoke(self, payload):
            return {}

    monkeypatch.setattr("app.services.document_editor_service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.services.document_editor_service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.services.document_editor_service.create_document_editor_agent", lambda model: FakeAgent())

    with pytest.raises(ValueError, match="未返回结构化结果"):
        edit_document(
            DocumentEditInput(
                document_type="markdown",
                document_title="Old title",
                content="# Old title\n\nBody",
                instruction="把标题改成 New title",
            )
        )
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_editor_agent.py -q
```

Expected: FAIL because `app.services.document_editor_service` does not exist.

- [ ] **Step 3: Implement service**

Create `apps/backend/app/services/document_editor_service.py`:

```python
from __future__ import annotations

from app.agents.document_editor.agent import create_document_editor_agent
from app.agents.model_factory import build_agent_model
from app.ai_runtime.model_selection import resolve_model_selection
from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput


def edit_document(input_data: DocumentEditInput) -> DocumentEditOutput:
    _validate_document_edit_input(input_data)
    selection = resolve_model_selection("document_editor")
    model = build_agent_model(selection)
    agent = create_document_editor_agent(model)

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


def _validate_document_edit_output(input_data: DocumentEditInput, output: DocumentEditOutput) -> None:
    if not output.edited_content.strip():
        raise ValueError("文档修改返回的 edited_content 不能为空。")
    if not output.change_summary.strip():
        raise ValueError("文档修改返回的 change_summary 不能为空。")

    original = input_data.content.strip()
    edited = output.edited_content.strip()
    if original and len(edited) < max(50, int(len(original) * 0.2)):
        raise ValueError("文档修改输出疑似异常缩水。")
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_editor_agent.py -q
```

Expected: PASS.

---

### Task 6: FastAPI Route Rewire And Legacy Cleanup

**Files:**
- Modify: `apps/backend/app/api/v1/agents.py`
- Modify: `apps/backend/app/services/agent_service.py`
- Delete: `apps/backend/app/llm_tasks/document_editor.py`
- Modify: `apps/backend/tests/test_ai_agents_architecture.py`

- [ ] **Step 1: Add architecture assertions**

Update `apps/backend/tests/test_ai_agents_architecture.py` with checks that:

```python
def test_document_editor_exists_in_new_agents_directory() -> None:
    assert (BACKEND_APP / "agents" / "document_editor" / "agent.py").exists()


def test_document_editor_no_longer_uses_llm_task_module() -> None:
    assert not (BACKEND_APP / "llm_tasks" / "document_editor.py").exists()
```

Update the legacy package constant to match the actual backup name:

```python
LEGACY_AGENTS_ROOT = BACKEND_APP / "agents_bak"
```

- [ ] **Step 2: Run architecture tests to verify failure**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_ai_agents_architecture.py -q
```

Expected: FAIL because the API still imports the old LLM task and the old file still exists.

- [ ] **Step 3: Rewire document editor route**

In `apps/backend/app/api/v1/agents.py`, replace:

```python
from app.llm_tasks.document_editor import edit_document
```

with:

```python
from app.services.document_editor_service import edit_document
```

Keep:

```python
@router.post("/document-editor/run", response_model=DocumentEditOutput)
async def run_document_editor(payload: DocumentEditInput, _actor=Depends(current_user)) -> DocumentEditOutput:
    return await edit_document(payload)
```

but if `edit_document` is synchronous, change it to:

```python
@router.post("/document-editor/run", response_model=DocumentEditOutput)
def run_document_editor(payload: DocumentEditInput, _actor=Depends(current_user)) -> DocumentEditOutput:
    return edit_document(payload)
```

- [ ] **Step 4: Remove old document editor LLM task**

Delete:

```text
apps/backend/app/llm_tasks/document_editor.py
```

Keep `apps/backend/app/llm_tasks/__init__.py` only if other llm tasks still need the package.

- [ ] **Step 5: Temporarily decouple agent_service from removed legacy agents**

Because `agents` is now the new LangChain directory and `agents_bak` is only a backup, `apps/backend/app/services/agent_service.py` must not import old `app.agents.admin_runner` or `app.agents.skills` at module import time.

For this phase, update `list_skills` and `execute_agent` to avoid legacy imports:

```python
def list_skills(_actor) -> list[dict]:
    return []


async def execute_agent(agent_id: str, payload: AgentRunIn, actor) -> dict:
    raise api_error(501, "AGENT_RUNTIME_NOT_MIGRATED", "智能体运行时正在迁移中。")
```

Keep `list_agents` using `list_agent_capabilities()`.

- [ ] **Step 6: Run architecture tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_ai_agents_architecture.py -q
```

Expected: PASS.

---

### Task 7: Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_document_editor_agent.py tests/test_ai_agent_model_assignments.py tests/test_ai_agents_architecture.py -q
```

Expected: targeted tests pass.

- [ ] **Step 2: Verify forbidden files were not created**

Run:

```powershell
cd apps/backend
$forbidden = @(
  "app/agents/document_editor/runner.py",
  "app/agents/document_editor/prompts.py",
  "app/agents/document_editor/skills.py",
  "app/agents/document_editor/subagents.py",
  "app/agents/document_editor/evals"
)
foreach ($path in $forbidden) {
  if (Test-Path -LiteralPath $path) {
    throw "Forbidden path exists: $path"
  }
}
```

Expected: command exits 0.

- [ ] **Step 3: Compile backend**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m compileall app -q
```

Expected: command exits 0.

- [ ] **Step 4: Run backend tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: tests pass, except failures from intentionally unmigrated legacy agents should be listed and converted into follow-up migration tasks instead of hidden.

---

## Self-Review

- Spec coverage: The plan creates the new `app/agents/document_editor` package, `app/agents/model_factory.py`, service entrypoint, and route rewiring.
- Excluded content: The plan does not create `runner.py`, `skills.py`, `prompts.py`, `subagents.py`, `evals/`, or extra `runtime/`.
- Current repo conflict handled: `agent_service.py` no longer imports legacy `app.agents.*` at module import time after `agents` is rebuilt as the new LangChain root.
