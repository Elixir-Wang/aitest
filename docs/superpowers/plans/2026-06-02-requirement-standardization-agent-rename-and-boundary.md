# Requirement Standardization Agent Rename And Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the raw requirement converter concept to "需求标准化智能体" and cleanly separate deterministic file conversion from agent-owned Markdown standardization.

**Architecture:** File-to-candidate-Markdown conversion lives in backend service/converter code and does not depend on model execution. The requirement standardization agent consumes source file metadata through existing tools, normalizes candidate Markdown into standard Markdown, and keeps compatibility aliases for the current `raw_requirement_format_converter` capability id during migration.

**Tech Stack:** FastAPI backend, Pydantic schemas, LangChain `create_agent`, pytest, existing SQLite-backed model assignment capability ids.

---

## Current State

- Active agent package: `apps/backend/app/agents/raw_requirement_converter/`
- User-facing capability id: `raw_requirement_format_converter`
- Current user-facing name: `格式转换智能体`
- Existing wrapper service: `apps/backend/app/services/raw_requirement_format_converter_service.py`
- Upload flow imports the agent service directly from `apps/backend/app/services/document_file_service.py`
- Deterministic converters currently live under the agent package at `apps/backend/app/agents/raw_requirement_converter/converters/`

## Target Boundary

```text
document_file_service
  -> services.requirement_file_converter
     -> deterministic PDF / Word / TXT / Markdown conversion
  -> agents.requirement_standardization.service
     -> LangChain agent standardizes Markdown structure and returns RequirementConversionOutput
```

The implementation should keep old import paths as thin compatibility wrappers until all internal callers and tests have moved.

## File Structure

- Create: `apps/backend/app/services/requirement_file_conversion/__init__.py`
  - Owns `ConvertedRequirementFile` and `convert_requirement_file_to_markdown`.
- Create: `apps/backend/app/services/requirement_file_conversion/pdf.py`
  - Owns PDF file extraction.
- Create: `apps/backend/app/services/requirement_file_conversion/word.py`
  - Owns Word file extraction.
- Create: `apps/backend/app/services/requirement_file_conversion/text.py`
  - Owns TXT/Markdown decoding.
- Modify: `apps/backend/app/services/requirement_file_converter.py`
  - Re-export from `app.services.requirement_file_conversion`.
- Create: `apps/backend/app/agents/requirement_standardization/`
  - New canonical agent package.
- Modify: `apps/backend/app/agents/raw_requirement_converter/`
  - Leave compatibility wrappers that import from `requirement_standardization`.
- Modify: `apps/backend/app/agents/capabilities.py`
  - Keep id `raw_requirement_format_converter`; change name and description to "需求标准化智能体".
- Modify: `apps/backend/app/services/document_file_service.py`
  - Import canonical standardization service, not old raw converter package.
- Modify: backend tests under `apps/backend/tests/`
  - Add architecture and behavior coverage for the new boundary and name.

---

### Task 1: Add Failing Architecture Tests For The New Boundary

**Files:**
- Modify: `apps/backend/tests/test_raw_requirement_converter_agent.py`
- Modify: `apps/backend/tests/test_ai_agents_architecture.py`
- Test: `apps/backend/tests/test_raw_requirement_converter_agent.py`
- Test: `apps/backend/tests/test_ai_agents_architecture.py`

- [ ] **Step 1: Add canonical package and service assertions**

In `apps/backend/tests/test_ai_agents_architecture.py`, add:

```python
def test_requirement_standardization_agent_exists_as_canonical_package() -> None:
    assert (NEW_AGENTS_ROOT / "requirement_standardization" / "agent.py").exists()
    assert (NEW_AGENTS_ROOT / "requirement_standardization" / "service.py").exists()
    assert (NEW_AGENTS_ROOT / "requirement_standardization" / "tools.py").exists()
    assert (NEW_AGENTS_ROOT / "requirement_standardization" / "schemas.py").exists()


def test_deterministic_requirement_file_conversion_lives_outside_agent_package() -> None:
    conversion_root = BACKEND_APP / "services" / "requirement_file_conversion"
    for filename in ("__init__.py", "pdf.py", "word.py", "text.py"):
        assert (conversion_root / filename).exists()
    assert not (NEW_AGENTS_ROOT / "requirement_standardization" / "converters").exists()
```

- [ ] **Step 2: Add capability display-name assertion**

In `apps/backend/tests/test_ai_agents_architecture.py`, add:

```python
def test_raw_requirement_format_converter_capability_is_displayed_as_requirement_standardization() -> None:
    from app.agents.capabilities import get_ai_capability

    capability = get_ai_capability("raw_requirement_format_converter")

    assert capability.name == "需求标准化智能体"
    assert "标准 Markdown" in capability.description
    assert "解析为 Markdown 工作稿" not in capability.description
```

- [ ] **Step 3: Add canonical service import assertion**

In `apps/backend/tests/test_raw_requirement_converter_agent.py`, replace `test_document_file_service_uses_raw_requirement_converter_service` with:

```python
def test_document_file_service_uses_requirement_standardization_service() -> None:
    service_path = Path("app/services/document_file_service.py")
    content = service_path.read_text(encoding="utf-8")
    assert "from app.agents.requirement_standardization.service import convert_requirement_file" in content
    assert "from app.agents.raw_requirement_converter.service import convert_requirement_file" not in content
    assert "from app.agents.raw_requirement_converter.converters import convert_requirement_file_to_markdown" not in content
```

- [ ] **Step 4: Run tests and verify they fail**

Run from `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ai_agents_architecture.py tests/test_raw_requirement_converter_agent.py -q
```

Expected: FAIL because `requirement_standardization` package and service converter package do not exist yet, and the capability name still says `格式转换智能体`.

---

### Task 2: Move Deterministic Converters To Service Layer

**Files:**
- Create: `apps/backend/app/services/requirement_file_conversion/__init__.py`
- Create: `apps/backend/app/services/requirement_file_conversion/pdf.py`
- Create: `apps/backend/app/services/requirement_file_conversion/word.py`
- Create: `apps/backend/app/services/requirement_file_conversion/text.py`
- Modify: `apps/backend/app/services/requirement_file_converter.py`
- Modify: `apps/backend/app/agents/raw_requirement_converter/converters/__init__.py`
- Modify: `apps/backend/app/agents/raw_requirement_converter/converters/pdf.py`
- Modify: `apps/backend/app/agents/raw_requirement_converter/converters/word.py`
- Modify: `apps/backend/app/agents/raw_requirement_converter/converters/text.py`

- [ ] **Step 1: Copy current converter implementation into service package**

Move the current implementation from `apps/backend/app/agents/raw_requirement_converter/converters/__init__.py` to `apps/backend/app/services/requirement_file_conversion/__init__.py`.

Keep these exported names:

```python
__all__ = ["ConvertedRequirementFile", "convert_requirement_file_to_markdown"]
```

- [ ] **Step 2: Create split service converter wrappers**

Create `apps/backend/app/services/requirement_file_conversion/pdf.py`:

```python
from pathlib import Path

from app.services.requirement_file_conversion import convert_requirement_file_to_markdown


def convert_pdf_file_to_markdown(input_path: str, *, assets_dir: str | None = None) -> tuple[str, str]:
    source_path = Path(input_path)
    return convert_requirement_file_to_markdown(
        source_path.name,
        source_path.read_bytes(),
        assets_dir=Path(assets_dir) if assets_dir else None,
    )
```

Create `apps/backend/app/services/requirement_file_conversion/word.py`:

```python
from pathlib import Path

from app.services.requirement_file_conversion import convert_requirement_file_to_markdown


def convert_word_file_to_markdown(input_path: str, *, assets_dir: str | None = None) -> tuple[str, str]:
    source_path = Path(input_path)
    return convert_requirement_file_to_markdown(
        source_path.name,
        source_path.read_bytes(),
        assets_dir=Path(assets_dir) if assets_dir else None,
    )
```

Create `apps/backend/app/services/requirement_file_conversion/text.py`:

```python
from pathlib import Path

from app.services.requirement_file_conversion import convert_requirement_file_to_markdown


def convert_text_file_to_markdown(input_path: str) -> tuple[str, str]:
    source_path = Path(input_path)
    return convert_requirement_file_to_markdown(source_path.name, source_path.read_bytes())
```

- [ ] **Step 3: Keep legacy service re-export**

Replace `apps/backend/app/services/requirement_file_converter.py` with:

```python
from app.services.requirement_file_conversion import (
    ConvertedRequirementFile,
    convert_requirement_file_to_markdown,
)


__all__ = ["ConvertedRequirementFile", "convert_requirement_file_to_markdown"]
```

- [ ] **Step 4: Turn old agent converter modules into compatibility wrappers**

Replace `apps/backend/app/agents/raw_requirement_converter/converters/__init__.py` with:

```python
from app.services.requirement_file_conversion import (
    ConvertedRequirementFile,
    convert_requirement_file_to_markdown,
)


__all__ = ["ConvertedRequirementFile", "convert_requirement_file_to_markdown"]
```

Replace `apps/backend/app/agents/raw_requirement_converter/converters/pdf.py` with:

```python
from app.services.requirement_file_conversion.pdf import convert_pdf_file_to_markdown


__all__ = ["convert_pdf_file_to_markdown"]
```

Replace `apps/backend/app/agents/raw_requirement_converter/converters/word.py` with:

```python
from app.services.requirement_file_conversion.word import convert_word_file_to_markdown


__all__ = ["convert_word_file_to_markdown"]
```

Replace `apps/backend/app/agents/raw_requirement_converter/converters/text.py` with:

```python
from app.services.requirement_file_conversion.text import convert_text_file_to_markdown


__all__ = ["convert_text_file_to_markdown"]
```

- [ ] **Step 5: Run converter tests**

Run from `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py -q
```

Expected: tests still fail only on new canonical package/name assertions, not on converter import errors.

- [ ] **Step 6: Commit converter boundary**

```powershell
git add apps/backend/app/services/requirement_file_conversion apps/backend/app/services/requirement_file_converter.py apps/backend/app/agents/raw_requirement_converter/converters apps/backend/tests/test_ai_agents_architecture.py apps/backend/tests/test_raw_requirement_converter_agent.py
git commit -m "refactor: move requirement file conversion to services"
```

---

### Task 3: Add Canonical Requirement Standardization Agent Package

**Files:**
- Create: `apps/backend/app/agents/requirement_standardization/__init__.py`
- Create: `apps/backend/app/agents/requirement_standardization/agent.py`
- Create: `apps/backend/app/agents/requirement_standardization/service.py`
- Create: `apps/backend/app/agents/requirement_standardization/schemas.py`
- Create: `apps/backend/app/agents/requirement_standardization/tools.py`
- Modify: `apps/backend/app/agents/raw_requirement_converter/__init__.py`
- Modify: `apps/backend/app/agents/raw_requirement_converter/agent.py`
- Modify: `apps/backend/app/agents/raw_requirement_converter/service.py`
- Modify: `apps/backend/app/agents/raw_requirement_converter/schemas.py`
- Modify: `apps/backend/app/agents/raw_requirement_converter/tools.py`

- [ ] **Step 1: Create canonical schemas module**

Create `apps/backend/app/agents/requirement_standardization/schemas.py`:

```python
from app.schemas.requirement_conversion import (
    RequirementConversionInput,
    RequirementConversionOutput,
)


__all__ = ["RequirementConversionInput", "RequirementConversionOutput"]
```

- [ ] **Step 2: Create canonical tools module**

Create `apps/backend/app/agents/requirement_standardization/tools.py`:

```python
from langchain_core.tools import tool

from app.services.requirement_file_conversion.pdf import convert_pdf_file_to_markdown
from app.services.requirement_file_conversion.text import convert_text_file_to_markdown
from app.services.requirement_file_conversion.word import convert_word_file_to_markdown
from app.services.requirement_markdown_normalizer import normalize_requirement_markdown


@tool
def convert_pdf_to_markdown(input_path: str, assets_dir_path: str | None = None) -> dict:
    """Convert a local PDF requirement file into candidate Markdown."""
    markdown, summary = convert_pdf_file_to_markdown(input_path, assets_dir=assets_dir_path)
    return {"markdown": markdown, "summary": summary}


@tool
def convert_word_to_markdown(input_path: str, assets_dir_path: str | None = None) -> dict:
    """Convert a local Word requirement file into candidate Markdown."""
    markdown, summary = convert_word_file_to_markdown(input_path, assets_dir=assets_dir_path)
    return {"markdown": markdown, "summary": summary}


@tool
def convert_text_to_markdown(input_path: str) -> dict:
    """Convert a local TXT or Markdown requirement file into candidate Markdown."""
    markdown, summary = convert_text_file_to_markdown(input_path)
    return {"markdown": markdown, "summary": summary}


@tool
def normalize_markdown_content(markdown: str) -> str:
    """Normalize candidate requirement Markdown without changing business meaning."""
    return normalize_requirement_markdown(markdown)


tools = [
    convert_pdf_to_markdown,
    convert_word_to_markdown,
    convert_text_to_markdown,
    normalize_markdown_content,
]


__all__ = [
    "convert_pdf_to_markdown",
    "convert_word_to_markdown",
    "convert_text_to_markdown",
    "normalize_markdown_content",
    "tools",
]
```

- [ ] **Step 3: Create canonical agent module**

Create `apps/backend/app/agents/requirement_standardization/agent.py`:

```python
from langchain.agents import create_agent

from app.agents.requirement_standardization.schemas import RequirementConversionOutput
from app.agents.requirement_standardization.tools import tools


SYSTEM_PROMPT = """
你是 AI 测试系统中的需求标准化智能体。

你负责把 PDF、Word、TXT、Markdown 原始需求文件转换后得到的候选内容整理为标准 Markdown。
你必须根据 file_format 调用合适的转换工具：
- pdf 调用 convert_pdf_to_markdown。
- doc/docx 调用 convert_word_to_markdown。
- txt 调用 convert_text_to_markdown。
- md/markdown 直接进入规范化流程，不调用文件转换工具。

转换工具返回候选 Markdown 后，你需要整理为最终标准 Markdown：
- 不得编造原文没有的需求事实。
- 不删除原文中的需求点、表格、字段、枚举、流程、限制条件和异常规则。
- 保留标题、列表、表格、代码块、接口字段、枚举值和流程步骤。
- PDF 解析出的纯文本需要尽量恢复标题、列表、段落结构。
- Word 中的标题、表格、列表、链接、图片引用和代码块需要保留。
- Markdown 输入不得大幅改写原文结构，只做必要清理。
- TXT 输入可以整理为 Markdown 段落和列表，但不得扩写。

最终必须返回符合 RequirementConversionOutput 的结构化结果。
conversion_summary 需要简要说明使用的工具、完成的标准化动作和明确遇到的问题。
""".strip()


def requirement_standardization_agent(model):
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        response_format=RequirementConversionOutput,
    )
```

- [ ] **Step 4: Create canonical service module**

Create `apps/backend/app/agents/requirement_standardization/service.py`:

```python
from pathlib import Path

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.requirement_standardization.agent import requirement_standardization_agent
from app.agents.requirement_standardization.schemas import RequirementConversionInput, RequirementConversionOutput
from app.services.requirement_file_conversion import convert_requirement_file_to_markdown


CAPABILITY_ID = "raw_requirement_format_converter"


async def convert_requirement_file(input_data: RequirementConversionInput) -> RequirementConversionOutput:
    source_path = Path(input_data.source_file_path)
    if not source_path.exists():
        raise ValueError("原始需求文件不存在，无法标准化。")

    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    agent = requirement_standardization_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": _build_conversion_input(input_data),
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("需求标准化智能体未返回结构化结果。")
    if not output.markdown_content.strip():
        raise ValueError("需求标准化智能体返回的 Markdown 为空。")
    return output


def _build_conversion_input(input_data: RequirementConversionInput) -> str:
    lines = [
        f"filename: {input_data.filename}",
        f"file_format: {input_data.file_format}",
        f"source_file_path: {input_data.source_file_path}",
    ]
    if input_data.assets_dir_path:
        lines.append(f"assets_dir_path: {input_data.assets_dir_path}")
    return "\n".join(lines)


def fallback_convert_requirement_file(input_data: RequirementConversionInput) -> tuple[str, str]:
    source_path = Path(input_data.source_file_path)
    return convert_requirement_file_to_markdown(
        input_data.filename,
        source_path.read_bytes(),
        assets_dir=Path(input_data.assets_dir_path) if input_data.assets_dir_path else None,
    )
```

- [ ] **Step 5: Create canonical package exports**

Create `apps/backend/app/agents/requirement_standardization/__init__.py`:

```python
from app.agents.requirement_standardization.agent import requirement_standardization_agent
from app.agents.requirement_standardization.schemas import (
    RequirementConversionInput,
    RequirementConversionOutput,
)
from app.agents.requirement_standardization.service import convert_requirement_file


__all__ = [
    "RequirementConversionInput",
    "RequirementConversionOutput",
    "convert_requirement_file",
    "requirement_standardization_agent",
]
```

- [ ] **Step 6: Turn old raw requirement package into compatibility wrappers**

Replace `apps/backend/app/agents/raw_requirement_converter/agent.py` with:

```python
from app.agents.requirement_standardization.agent import (
    SYSTEM_PROMPT,
    requirement_standardization_agent,
)


def raw_requirement_converter_agent(model):
    return requirement_standardization_agent(model)


__all__ = ["SYSTEM_PROMPT", "raw_requirement_converter_agent"]
```

Replace `apps/backend/app/agents/raw_requirement_converter/service.py` with:

```python
from app.agents.requirement_standardization.service import (
    CAPABILITY_ID,
    convert_requirement_file,
    fallback_convert_requirement_file,
)


__all__ = ["CAPABILITY_ID", "convert_requirement_file", "fallback_convert_requirement_file"]
```

Replace `apps/backend/app/agents/raw_requirement_converter/schemas.py` with:

```python
from app.agents.requirement_standardization.schemas import (
    RequirementConversionInput,
    RequirementConversionOutput,
)


__all__ = ["RequirementConversionInput", "RequirementConversionOutput"]
```

Replace `apps/backend/app/agents/raw_requirement_converter/tools.py` with:

```python
from app.agents.requirement_standardization.tools import (
    convert_pdf_to_markdown,
    convert_text_to_markdown,
    convert_word_to_markdown,
    normalize_markdown_content,
    tools,
)


__all__ = [
    "convert_pdf_to_markdown",
    "convert_word_to_markdown",
    "convert_text_to_markdown",
    "normalize_markdown_content",
    "tools",
]
```

- [ ] **Step 7: Update tests to use canonical imports**

In `apps/backend/tests/test_raw_requirement_converter_agent.py`, update imports:

```python
from app.agents.requirement_standardization import schemas
from app.agents.requirement_standardization.agent import requirement_standardization_agent
from app.agents.requirement_standardization.tools import (
    convert_pdf_to_markdown,
    convert_text_to_markdown,
    convert_word_to_markdown,
    normalize_markdown_content,
    tools,
)
```

Rename test functions from `test_raw_requirement_converter_*` to `test_requirement_standardization_*` where practical.

Update monkeypatch paths:

```python
"app.agents.requirement_standardization.agent.create_agent"
"app.agents.requirement_standardization.service.resolve_model_selection"
"app.agents.requirement_standardization.service.build_agent_model"
"app.agents.requirement_standardization.service.requirement_standardization_agent"
```

Update prompt assertion:

```python
assert "需求标准化智能体" in calls["system_prompt"]
```

- [ ] **Step 8: Run focused tests**

Run from `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py tests/test_ai_agents_architecture.py -q
```

Expected: only failures left should be direct service imports or capability display name not yet updated.

- [ ] **Step 9: Commit canonical agent package**

```powershell
git add apps/backend/app/agents/requirement_standardization apps/backend/app/agents/raw_requirement_converter apps/backend/tests/test_raw_requirement_converter_agent.py apps/backend/tests/test_ai_agents_architecture.py
git commit -m "refactor: add requirement standardization agent package"
```

---

### Task 4: Update Capability Display Name And Internal Callers

**Files:**
- Modify: `apps/backend/app/agents/capabilities.py`
- Modify: `apps/backend/app/services/document_file_service.py`
- Modify: `apps/backend/app/services/raw_requirement_format_converter_service.py`
- Modify: `apps/backend/tests/test_raw_requirement_converter_agent.py`
- Modify: `apps/backend/tests/test_ai_agents_architecture.py`

- [ ] **Step 1: Update capability name and description**

In `apps/backend/app/agents/capabilities.py`, replace the `raw_requirement_format_converter` capability block with:

```python
    AiCapability(
        id="raw_requirement_format_converter",
        name="需求标准化智能体",
        description="负责将上传的 PDF、Word、TXT 和 Markdown 需求文件标准化为结构稳定的标准 Markdown。",
    ),
```

Keep the id unchanged for now so existing model assignment rows still resolve.

- [ ] **Step 2: Update upload flow import**

In `apps/backend/app/services/document_file_service.py`, replace:

```python
from app.agents.raw_requirement_converter.service import convert_requirement_file, fallback_convert_requirement_file
```

with:

```python
from app.agents.requirement_standardization.service import convert_requirement_file, fallback_convert_requirement_file
```

Keep existing runtime behavior unchanged.

- [ ] **Step 3: Update compatibility wrapper service**

Replace `apps/backend/app/services/raw_requirement_format_converter_service.py` with:

```python
from app.agents.requirement_standardization.service import convert_requirement_file
from app.schemas.requirement_conversion import RequirementConversionInput, RequirementConversionOutput


async def convert_raw_requirement_format(input_data: RequirementConversionInput) -> RequirementConversionOutput:
    return await convert_requirement_file(input_data)
```

- [ ] **Step 4: Update user-visible summary fallback wording**

In `apps/backend/app/services/document_file_service.py`, replace:

```python
summary = agent_output.conversion_summary.strip() or "已通过格式转换智能体标准化 Markdown。"
```

with:

```python
summary = agent_output.conversion_summary.strip() or "已通过需求标准化智能体生成标准 Markdown。"
```

- [ ] **Step 5: Run focused tests**

Run from `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py tests/test_ai_agents_architecture.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit naming and callers**

```powershell
git add apps/backend/app/agents/capabilities.py apps/backend/app/services/document_file_service.py apps/backend/app/services/raw_requirement_format_converter_service.py apps/backend/tests/test_raw_requirement_converter_agent.py apps/backend/tests/test_ai_agents_architecture.py
git commit -m "refactor: rename converter capability to requirement standardization"
```

---

### Task 5: Add Compatibility Tests For Old Imports

**Files:**
- Modify: `apps/backend/tests/test_raw_requirement_converter_agent.py`
- Test: `apps/backend/tests/test_raw_requirement_converter_agent.py`

- [ ] **Step 1: Add old import compatibility coverage**

In `apps/backend/tests/test_raw_requirement_converter_agent.py`, add:

```python
def test_raw_requirement_converter_imports_remain_compatible() -> None:
    from app.agents.raw_requirement_converter.agent import raw_requirement_converter_agent
    from app.agents.requirement_standardization.agent import requirement_standardization_agent
    from app.agents.raw_requirement_converter.service import convert_requirement_file as legacy_convert
    from app.agents.requirement_standardization.service import convert_requirement_file as canonical_convert

    assert raw_requirement_converter_agent("model").__class__ is requirement_standardization_agent("model").__class__
    assert legacy_convert is canonical_convert
```

If constructing the real agent object is expensive in this environment, use monkeypatch instead:

```python
def test_raw_requirement_converter_imports_remain_compatible(monkeypatch) -> None:
    from app.agents.raw_requirement_converter import agent as legacy_agent_module
    from app.agents.raw_requirement_converter.service import convert_requirement_file as legacy_convert
    from app.agents.requirement_standardization.service import convert_requirement_file as canonical_convert

    monkeypatch.setattr(
        "app.agents.raw_requirement_converter.agent.requirement_standardization_agent",
        lambda model: ("agent", model),
    )

    assert legacy_agent_module.raw_requirement_converter_agent("model") == ("agent", "model")
    assert legacy_convert is canonical_convert
```

- [ ] **Step 2: Run compatibility test**

Run from `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py::test_raw_requirement_converter_imports_remain_compatible -q
```

Expected: PASS.

- [ ] **Step 3: Commit compatibility coverage**

```powershell
git add apps/backend/tests/test_raw_requirement_converter_agent.py
git commit -m "test: cover legacy requirement converter imports"
```

---

### Task 6: Full Backend Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run targeted backend tests**

Run from `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py tests/test_ai_agents_architecture.py tests/test_ai_agent_model_assignments.py tests/test_model_selection.py -q
```

Expected: PASS.

- [ ] **Step 2: Run document upload/conversion related tests**

Run from `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_document_service.py tests/test_raw_requirement_converter_agent.py -q
```

Expected: PASS. If `tests/test_document_service.py` does not exist in the current branch, run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -k "requirement_converter or document_file or document_service"
```

- [ ] **Step 3: Compile backend**

Run from `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m compileall -q app tests
```

Expected: command exits with code 0.

- [ ] **Step 4: Check old naming remains only in compatibility/id contexts**

Run from repo root:

```powershell
rg -n "格式转换智能体|原始需求文件 Markdown 转换智能体|app\.agents\.raw_requirement_converter\.service|app\.agents\.raw_requirement_converter\.converters" apps/backend/app apps/backend/tests
```

Expected:
- No `格式转换智能体`.
- No `原始需求文件 Markdown 转换智能体`.
- Old `raw_requirement_converter` package references only appear in compatibility tests or compatibility wrapper modules.
- Capability id `raw_requirement_format_converter` remains.

- [ ] **Step 5: Commit final verification adjustments if needed**

If verification required test or import fixes:

```powershell
git add apps/backend/app apps/backend/tests
git commit -m "test: verify requirement standardization migration"
```

---

## Rollback Notes

- Keep `raw_requirement_format_converter` as the capability id during this plan.
- Keep `app.agents.raw_requirement_converter` wrappers until all references and stored model assignments are migrated.
- Do not delete `apps/backend/app/services/raw_requirement_format_converter_service.py` in this plan; it is a compatibility entry point.
- Do not rename Pydantic schema classes in this plan; `RequirementConversionInput` and `RequirementConversionOutput` remain valid API contracts.

## Self-Review

- Spec coverage: The plan covers user-visible rename, canonical package rename, deterministic converter service boundary, upload flow caller migration, legacy compatibility, and tests.
- Placeholder scan: No TODO/TBD placeholders remain.
- Type consistency: `RequirementConversionInput`, `RequirementConversionOutput`, `convert_requirement_file`, and `fallback_convert_requirement_file` keep existing signatures.
- Scope check: This plan intentionally does not migrate persisted capability ids; that should be a separate DB/data migration only if the product needs id-level rename later.
