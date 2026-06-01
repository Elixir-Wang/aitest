# Raw Requirement Converter DeepAgents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the raw requirement file Markdown conversion capability into `apps/backend/app/agents` as a DeepAgents-based pipeline with PDF, Word, and Markdown formatter subagents.

**Architecture:** Keep deterministic binary parsing in the existing service/parser layer, then pass candidate Markdown into a DeepAgents main agent. PDF and Word inputs run through a type-specific parser subagent before the shared Markdown formatter subagent; Markdown/TXT inputs go directly to the formatter. Conversion output is reduced to `markdown_content` and `conversion_summary`.

**Tech Stack:** Python, FastAPI service layer, Pydantic, DeepAgents, LangChain chat model factory, pytest.

---

## File Structure

- Create: `apps/backend/app/agents/raw_requirement_converter/__init__.py`
  - Exports the new agent factory and schemas.
- Create: `apps/backend/app/agents/raw_requirement_converter/agent.py`
  - Defines prompts, subagent specs, skill paths, and `raw_requirement_converter_agent(model)`.
- Create: `apps/backend/app/agents/raw_requirement_converter/schemas.py`
  - Re-exports `RequirementConversionInput` and `RequirementConversionOutput`.
- Create: `apps/backend/app/agents/raw_requirement_converter/tools.py`
  - Exposes an explicit empty `tools` list for the first version because parsing is handled before the agent.
- Create: `apps/backend/app/agents/raw_requirement_converter/skills/pdf_parse/SKILL.md`
  - Migrated and narrowed PDF conversion rules.
- Create: `apps/backend/app/agents/raw_requirement_converter/skills/word_parse/SKILL.md`
  - Migrated and narrowed Word conversion rules.
- Create: `apps/backend/app/agents/raw_requirement_converter/skills/markdown_format/SKILL.md`
  - Markdown standardization rules migrated from the old converter prompt.
- Modify: `apps/backend/app/schemas/requirement_conversion.py`
  - Remove `quality_score` and `warnings`.
- Modify: `apps/backend/app/services/raw_requirement_format_converter_service.py`
  - Replace old runner import with the new DeepAgents service invocation.
- Modify: `apps/backend/app/services/document_file_service.py`
  - Stop reading removed output fields.
- Modify: `apps/backend/tests/test_document_editor_agent.py`
  - No direct change unless shared imports move.
- Create or modify: `apps/backend/tests/test_raw_requirement_converter_agent.py`
  - Unit tests for schema, agent construction, service behavior, and file type routing intent.
- Modify: `apps/backend/tests/test_ai_agents_architecture.py`
  - Assert the new raw converter agent exists and the old runner is not referenced.

---

### Task 1: Shrink Requirement Conversion Output Schema

**Files:**
- Modify: `apps/backend/app/schemas/requirement_conversion.py`
- Test: `apps/backend/tests/test_raw_requirement_converter_agent.py`

- [ ] **Step 1: Write the failing schema test**

Create `apps/backend/tests/test_raw_requirement_converter_agent.py` with:

```python
from __future__ import annotations

from app.schemas.requirement_conversion import RequirementConversionOutput


def test_requirement_conversion_output_contract_is_minimal() -> None:
    assert set(RequirementConversionOutput.model_fields) == {
        "markdown_content",
        "conversion_summary",
    }
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py -q
```

Expected: FAIL because `quality_score` and `warnings` still exist.

- [ ] **Step 3: Update the schema**

Edit `apps/backend/app/schemas/requirement_conversion.py` to:

```python
from __future__ import annotations

from pydantic import BaseModel


class RequirementConversionInput(BaseModel):
    filename: str
    file_format: str
    candidate_markdown: str
    candidate_summary: str


class RequirementConversionOutput(BaseModel):
    markdown_content: str
    conversion_summary: str = ""
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py -q
```

Expected: PASS.

---

### Task 2: Add Raw Requirement Converter Agent Package

**Files:**
- Create: `apps/backend/app/agents/raw_requirement_converter/__init__.py`
- Create: `apps/backend/app/agents/raw_requirement_converter/schemas.py`
- Create: `apps/backend/app/agents/raw_requirement_converter/tools.py`
- Modify: `apps/backend/tests/test_raw_requirement_converter_agent.py`

- [ ] **Step 1: Add failing package tests**

Append to `apps/backend/tests/test_raw_requirement_converter_agent.py`:

```python
from app.agents.raw_requirement_converter import schemas
from app.agents.raw_requirement_converter.tools import tools
from app.schemas.requirement_conversion import RequirementConversionInput


def test_raw_requirement_converter_schemas_reuse_api_contract() -> None:
    assert schemas.RequirementConversionInput is RequirementConversionInput
    assert schemas.RequirementConversionOutput is RequirementConversionOutput


def test_raw_requirement_converter_tools_are_empty_for_service_parsed_input() -> None:
    assert tools == []
```

- [ ] **Step 2: Run tests to verify package import fails**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.agents.raw_requirement_converter'`.

- [ ] **Step 3: Create the package files**

Create `apps/backend/app/agents/raw_requirement_converter/schemas.py`:

```python
from __future__ import annotations

from app.schemas.requirement_conversion import RequirementConversionInput, RequirementConversionOutput


__all__ = ["RequirementConversionInput", "RequirementConversionOutput"]
```

Create `apps/backend/app/agents/raw_requirement_converter/tools.py`:

```python
from __future__ import annotations


tools = []


__all__ = ["tools"]
```

Create `apps/backend/app/agents/raw_requirement_converter/__init__.py`:

```python
from __future__ import annotations

from app.agents.raw_requirement_converter.schemas import RequirementConversionInput, RequirementConversionOutput


__all__ = ["RequirementConversionInput", "RequirementConversionOutput"]
```

- [ ] **Step 4: Run tests to verify package passes**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py -q
```

Expected: PASS.

---

### Task 3: Create DeepAgents Agent Factory

**Files:**
- Create: `apps/backend/app/agents/raw_requirement_converter/agent.py`
- Modify: `apps/backend/app/agents/raw_requirement_converter/__init__.py`
- Modify: `apps/backend/tests/test_raw_requirement_converter_agent.py`

- [ ] **Step 1: Add failing DeepAgents construction test**

Append to `apps/backend/tests/test_raw_requirement_converter_agent.py`:

```python
from app.agents.raw_requirement_converter.agent import raw_requirement_converter_agent


def test_raw_requirement_converter_agent_uses_deepagents(monkeypatch) -> None:
    calls = {}

    def fake_create_deep_agent(model, tools, *, system_prompt, subagents, skills, response_format):
        calls.update(
            {
                "model": model,
                "tools": tools,
                "system_prompt": system_prompt,
                "subagents": subagents,
                "skills": skills,
                "response_format": response_format,
            }
        )
        return "agent"

    monkeypatch.setattr("app.agents.raw_requirement_converter.agent.create_deep_agent", fake_create_deep_agent)

    agent = raw_requirement_converter_agent("model")

    assert agent == "agent"
    assert calls["model"] == "model"
    assert calls["tools"] == []
    assert calls["response_format"] is RequirementConversionOutput
    assert "原始需求文件转换主智能体" in calls["system_prompt"]
    assert [item["name"] for item in calls["subagents"]] == [
        "pdf_parser_agent",
        "word_parser_agent",
        "markdown_formatter_agent",
    ]
    assert any("pdf_parse" in item for item in calls["skills"])
    assert any("word_parse" in item for item in calls["skills"])
    assert any("markdown_format" in item for item in calls["skills"])
```

- [ ] **Step 2: Run tests to verify agent import fails**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py::test_raw_requirement_converter_agent_uses_deepagents -q
```

Expected: FAIL because `agent.py` does not exist.

- [ ] **Step 3: Implement the agent factory**

Create `apps/backend/app/agents/raw_requirement_converter/agent.py`:

```python
from __future__ import annotations

from pathlib import Path

from deepagents import create_deep_agent

from app.agents.raw_requirement_converter.schemas import RequirementConversionOutput
from app.agents.raw_requirement_converter.tools import tools


AGENT_DIR = Path(__file__).parent

MAIN_INSTRUCTIONS = """
你是 AI 测试系统中的原始需求文件转换主智能体。
你负责把本地解析器生成的候选内容转换为标准 Markdown。

执行规则：
- PDF 文件先委派给 pdf_parser_agent，再交给 markdown_formatter_agent。
- Word 文件先委派给 word_parser_agent，再交给 markdown_formatter_agent。
- Markdown、TXT 文件直接交给 markdown_formatter_agent。
- 不得编造原文没有的需求事实。
- 最终必须返回符合 RequirementConversionOutput 的结构化结果。
""".strip()

PDF_PARSER_PROMPT = """
你是 PDF 需求文件解析子智能体。
你处理的是本地 PDF 解析器生成的候选 Markdown，不直接读取 PDF 二进制文件。
你必须遵循 pdf_parse skill，清理页眉页脚、页码、重复噪声和异常断行。
""".strip()

WORD_PARSER_PROMPT = """
你是 Word 需求文件解析子智能体。
你处理的是本地 Word 解析器生成的候选 Markdown，不直接读取 Word 二进制文件。
你必须遵循 word_parse skill，保留标题、表格、列表、链接、图片引用和代码块。
""".strip()

MARKDOWN_FORMATTER_PROMPT = """
你是 Markdown 标准化子智能体。
所有文件最终都必须经过你处理。
你必须遵循 markdown_format skill，统一标题、空行、列表、表格和代码块格式。
你不得改变业务语义。
""".strip()

SUBAGENTS = [
    {
        "name": "pdf_parser_agent",
        "description": "整理 PDF 本地解析器输出的候选 Markdown。",
        "system_prompt": PDF_PARSER_PROMPT,
        "tools": [],
    },
    {
        "name": "word_parser_agent",
        "description": "整理 Word 本地解析器输出的候选 Markdown。",
        "system_prompt": WORD_PARSER_PROMPT,
        "tools": [],
    },
    {
        "name": "markdown_formatter_agent",
        "description": "将候选内容统一标准化为最终 Markdown。",
        "system_prompt": MARKDOWN_FORMATTER_PROMPT,
        "tools": [],
    },
]


def raw_requirement_converter_agent(model):
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=MAIN_INSTRUCTIONS,
        subagents=SUBAGENTS,
        skills=[
            str(AGENT_DIR / "skills" / "pdf_parse"),
            str(AGENT_DIR / "skills" / "word_parse"),
            str(AGENT_DIR / "skills" / "markdown_format"),
        ],
        response_format=RequirementConversionOutput,
    )
```

Update `apps/backend/app/agents/raw_requirement_converter/__init__.py`:

```python
from __future__ import annotations

from app.agents.raw_requirement_converter.agent import raw_requirement_converter_agent
from app.agents.raw_requirement_converter.schemas import RequirementConversionInput, RequirementConversionOutput


__all__ = [
    "RequirementConversionInput",
    "RequirementConversionOutput",
    "raw_requirement_converter_agent",
]
```

- [ ] **Step 4: Run the focused construction test**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py::test_raw_requirement_converter_agent_uses_deepagents -q
```

Expected: PASS.

---

### Task 4: Migrate Skill Content

**Files:**
- Create: `apps/backend/app/agents/raw_requirement_converter/skills/pdf_parse/SKILL.md`
- Create: `apps/backend/app/agents/raw_requirement_converter/skills/word_parse/SKILL.md`
- Create: `apps/backend/app/agents/raw_requirement_converter/skills/markdown_format/SKILL.md`
- Modify: `apps/backend/tests/test_raw_requirement_converter_agent.py`

- [ ] **Step 1: Add failing skill existence test**

Append to `apps/backend/tests/test_raw_requirement_converter_agent.py`:

```python
from pathlib import Path


def test_raw_requirement_converter_skills_exist() -> None:
    skill_root = Path("app/agents/raw_requirement_converter/skills")
    for skill_name in ("pdf_parse", "word_parse", "markdown_format"):
        skill_path = skill_root / skill_name / "SKILL.md"
        assert skill_path.exists(), f"missing {skill_path}"
        content = skill_path.read_text(encoding="utf-8")
        assert "不得编造" in content
```

- [ ] **Step 2: Run test to verify skills are missing**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py::test_raw_requirement_converter_skills_exist -q
```

Expected: FAIL because the skill files do not exist.

- [ ] **Step 3: Create PDF skill**

Create `apps/backend/app/agents/raw_requirement_converter/skills/pdf_parse/SKILL.md`:

```markdown
---
name: pdf_parse
description: 整理 PDF 本地解析器输出的候选 Markdown，清理页眉页脚、页码、重复噪声和异常断行。
---

# PDF Parse Skill

- 你处理的是本地解析器已经提取出的候选 Markdown，不直接读取 PDF 文件。
- 不得编造原文没有的需求事实。
- 删除明显重复的页眉、页脚、页码和版权水印。
- 修复 PDF 文本抽取导致的异常断行，但不能合并语义不连续的段落。
- 保留章节标题、编号、列表、表格痕迹、接口字段、枚举值和流程步骤。
- 如果候选内容疑似扫描件、乱码或明显缺页，在 `conversion_summary` 中说明。
- 输出正文不要包裹在完整代码块中。
```

- [ ] **Step 4: Create Word skill**

Create `apps/backend/app/agents/raw_requirement_converter/skills/word_parse/SKILL.md`:

```markdown
---
name: word_parse
description: 整理 Word 本地解析器输出的候选 Markdown，保留标题、表格、列表、链接、图片引用和代码块。
---

# Word Parse Skill

- 你处理的是本地解析器已经提取出的候选 Markdown，不直接读取 Word 文件。
- 不得编造原文没有的需求事实。
- 保留 Word 标题层级，修正明显错误的 Markdown 标题格式。
- 保留表格为 GFM Markdown 表格；无法完整保留的表格问题写入 `conversion_summary`。
- 保留列表、编号、链接、图片引用、代码块、接口字段和状态枚举。
- 不把普通正文改写成需求结论。
- 输出正文不要包裹在完整代码块中。
```

- [ ] **Step 5: Create Markdown format skill**

Create `apps/backend/app/agents/raw_requirement_converter/skills/markdown_format/SKILL.md`:

```markdown
---
name: markdown_format
description: 将候选内容统一标准化为最终 Markdown，不改变业务语义。
---

# Markdown Format Skill

- 不得编造原文没有的需求事实。
- 不删除原文中的需求点、表格、字段、枚举、流程、限制条件和异常规则。
- 统一标题格式为 `#`、`##`、`###` 等 Markdown 标题。
- 统一列表、编号、空行和代码块格式。
- 保留 Markdown 表格；表格内容中的换行可用 `<br>` 表示。
- 保留 JSON、SQL、接口示例、配置片段等代码块。
- TXT 内容可以整理为 Markdown 段落和列表，但不得扩写。
- 最终输出 `markdown_content` 和 `conversion_summary`。
- `conversion_summary` 简要说明本次做了哪些转换，以及明确遇到的问题。
```

- [ ] **Step 6: Run skill test**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py::test_raw_requirement_converter_skills_exist -q
```

Expected: PASS.

---

### Task 5: Replace Old Converter Service With New DeepAgents Invocation

**Files:**
- Modify: `apps/backend/app/services/raw_requirement_format_converter_service.py`
- Modify: `apps/backend/tests/test_raw_requirement_converter_agent.py`

- [ ] **Step 1: Add failing service tests**

Append to `apps/backend/tests/test_raw_requirement_converter_agent.py`:

```python
import pytest

from app.schemas.requirement_conversion import RequirementConversionInput


@pytest.mark.asyncio
async def test_raw_requirement_converter_service_returns_structured_response(monkeypatch) -> None:
    from app.services.raw_requirement_format_converter_service import convert_raw_requirement_format

    expected = RequirementConversionOutput(
        markdown_content="# 登录\n\n- 支持账号密码登录。\n",
        conversion_summary="已标准化 Markdown。",
    )

    class FakeAgent:
        def invoke(self, payload):
            assert payload["messages"][0]["role"] == "user"
            assert "filename:" in payload["messages"][0]["content"]
            assert "candidate_markdown:" in payload["messages"][0]["content"]
            return {"structured_response": expected}

    monkeypatch.setattr("app.services.raw_requirement_format_converter_service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.services.raw_requirement_format_converter_service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.services.raw_requirement_format_converter_service.raw_requirement_converter_agent", lambda model: FakeAgent())

    result = await convert_raw_requirement_format(
        RequirementConversionInput(
            filename="demo.md",
            file_format="md",
            candidate_markdown="# 登录\n支持账号密码登录。",
            candidate_summary="文本文件直接保存为 Markdown 转换稿。",
        )
    )

    assert result is expected


@pytest.mark.asyncio
async def test_raw_requirement_converter_service_rejects_missing_structured_response(monkeypatch) -> None:
    from app.services.raw_requirement_format_converter_service import convert_raw_requirement_format

    class FakeAgent:
        def invoke(self, payload):
            return {}

    monkeypatch.setattr("app.services.raw_requirement_format_converter_service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.services.raw_requirement_format_converter_service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.services.raw_requirement_format_converter_service.raw_requirement_converter_agent", lambda model: FakeAgent())

    with pytest.raises(ValueError, match="未返回结构化结果"):
        await convert_raw_requirement_format(
            RequirementConversionInput(
                filename="demo.md",
                file_format="md",
                candidate_markdown="# 登录\n支持账号密码登录。",
                candidate_summary="文本文件直接保存为 Markdown 转换稿。",
            )
        )
```

- [ ] **Step 2: Run focused service tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py::test_raw_requirement_converter_service_returns_structured_response tests/test_raw_requirement_converter_agent.py::test_raw_requirement_converter_service_rejects_missing_structured_response -q
```

Expected: FAIL because the service still imports the old runner.

- [ ] **Step 3: Implement service invocation**

Replace `apps/backend/app/services/raw_requirement_format_converter_service.py` with:

```python
from __future__ import annotations

from app.agents.model_factory import build_agent_model
from app.agents.model_selection import resolve_model_selection
from app.agents.raw_requirement_converter.agent import raw_requirement_converter_agent
from app.schemas.requirement_conversion import RequirementConversionInput, RequirementConversionOutput


async def convert_raw_requirement_format(input_data: RequirementConversionInput) -> RequirementConversionOutput:
    selection = resolve_model_selection("raw_requirement_format_converter")
    model = build_agent_model(selection)
    agent = raw_requirement_converter_agent(model)
    result = agent.invoke(
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
        raise ValueError("原始需求格式转换智能体未返回结构化结果。")
    if not output.markdown_content.strip():
        raise ValueError("原始需求格式转换智能体返回的 Markdown 为空。")
    return output


def _build_conversion_input(input_data: RequirementConversionInput) -> str:
    return "\n".join(
        [
            f"filename: {input_data.filename}",
            f"file_format: {input_data.file_format}",
            f"candidate_summary: {input_data.candidate_summary}",
            "candidate_markdown:",
            input_data.candidate_markdown,
        ]
    )
```

- [ ] **Step 4: Run focused service tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py::test_raw_requirement_converter_service_returns_structured_response tests/test_raw_requirement_converter_agent.py::test_raw_requirement_converter_service_rejects_missing_structured_response -q
```

Expected: PASS.

---

### Task 6: Remove Removed Output Field Usage From Document File Service

**Files:**
- Modify: `apps/backend/app/services/document_file_service.py`
- Modify: `apps/backend/tests/test_raw_requirement_converter_agent.py`

- [ ] **Step 1: Add regression test for no warnings dependency**

Append to `apps/backend/tests/test_raw_requirement_converter_agent.py`:

```python
@pytest.mark.asyncio
async def test_document_file_convert_to_markdown_uses_minimal_agent_output(monkeypatch) -> None:
    from app.services.document_file_service import convert_to_markdown

    output = RequirementConversionOutput(
        markdown_content="# 登录\n\n- 支持账号密码登录。\n",
        conversion_summary="已标准化 Markdown。",
    )

    monkeypatch.setattr(
        "app.services.document_file_service.convert_requirement_file_to_markdown",
        lambda filename, raw_bytes, assets_dir=None: ("# 登录\n支持账号密码登录。", "本地解析完成。"),
    )
    monkeypatch.setattr(
        "app.services.document_file_service.convert_raw_requirement_format",
        lambda input_data: _async_result(output),
    )

    markdown, summary = await convert_to_markdown("demo.md", b"# demo")

    assert markdown == "# 登录\n\n- 支持账号密码登录。\n"
    assert summary == "已标准化 Markdown。"


async def _async_result(value):
    return value
```

- [ ] **Step 2: Run the regression test**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py::test_document_file_convert_to_markdown_uses_minimal_agent_output -q
```

Expected: FAIL because `document_file_service.py` still reads `agent_output.warnings`.

- [ ] **Step 3: Update `convert_to_markdown()`**

In `apps/backend/app/services/document_file_service.py`, replace:

```python
summary = agent_output.conversion_summary.strip() or "已通过格式转换智能体标准化 Markdown。"
if agent_output.warnings:
    summary = f"{summary} 警告：{'；'.join(agent_output.warnings)}"
return markdown + "\n", summary
```

with:

```python
summary = agent_output.conversion_summary.strip() or "已通过格式转换智能体标准化 Markdown。"
return markdown + "\n", summary
```

- [ ] **Step 4: Run regression test**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_raw_requirement_converter_agent.py::test_document_file_convert_to_markdown_uses_minimal_agent_output -q
```

Expected: PASS.

---

### Task 7: Architecture Cleanup Assertions

**Files:**
- Modify: `apps/backend/tests/test_ai_agents_architecture.py`

- [ ] **Step 1: Add architecture assertions**

Append to `apps/backend/tests/test_ai_agents_architecture.py`:

```python
def test_raw_requirement_converter_exists_in_new_agents_directory() -> None:
    assert (NEW_AGENTS_ROOT / "raw_requirement_converter" / "agent.py").exists()
    assert (NEW_AGENTS_ROOT / "raw_requirement_converter" / "skills" / "pdf_parse" / "SKILL.md").exists()
    assert (NEW_AGENTS_ROOT / "raw_requirement_converter" / "skills" / "word_parse" / "SKILL.md").exists()
    assert (NEW_AGENTS_ROOT / "raw_requirement_converter" / "skills" / "markdown_format" / "SKILL.md").exists()


def test_raw_requirement_converter_service_no_longer_imports_old_runner() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "raw_requirement_format_converter_service.py"
    content = service_path.read_text(encoding="utf-8")
    assert "app.agents.raw_requirement_format_converter.runner" not in content
```

- [ ] **Step 2: Run architecture tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_ai_agents_architecture.py -q
```

Expected: PASS.

---

### Task 8: Full Verification

**Files:**
- Verify only.

- [ ] **Step 1: Search for removed fields and old runner references**

Run:

```powershell
rg -n "quality_score|agent_output\.warnings|raw_requirement_format_converter\.runner|markdown_read|markdown_reader_agent" apps/backend/app apps/backend/tests
```

Expected: no active references except unrelated historical files under `agents_bak` if the search scope includes them. The command above does not include `agents_bak` separately, so expected output should be empty.

- [ ] **Step 2: Run backend tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Compile backend app**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m compileall app -q
```

Expected: exits with code 0 and no output.

---

## Self-Review

- Spec coverage: The plan covers new DeepAgents package, three child-agent paths, three skills, schema cleanup, service integration, document conversion fallback compatibility, and architecture tests.
- Placeholder scan: No unfinished marker text or unspecified implementation steps remain.
- Type consistency: The plan consistently uses `RequirementConversionInput`, `RequirementConversionOutput`, `raw_requirement_converter_agent`, `markdown_content`, and `conversion_summary`.
