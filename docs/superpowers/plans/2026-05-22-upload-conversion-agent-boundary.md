# Upload Conversion And Agent Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate requirement file upload/conversion from Agent Runtime so upload uses a dedicated backend conversion service, while `raw_requirement_format_converter` only registers concrete conversion skills.

**Architecture:** The upload API remains a deterministic FastAPI service flow under `app.services.document_service`. File-to-Markdown conversion moves into a dedicated service module that directly invokes agent-local `pdf_to_markdown` and `docx_to_markdown` tool assets without pretending to be an agent. `raw_requirement_format_converter_agent.py` registers only the actual skills it can use in model runs: `pdf_to_markdown` and `docx_to_markdown`.

**Tech Stack:** FastAPI backend, Python 3.13, pytest/unittest, Node-based `convert.cjs` skill scripts, OpenAI Agents SDK skill registry.

---

### File Structure

- Create: `apps/backend/app/services/requirement_file_converter.py`
  - Owns upload-time file conversion.
  - Accepts `(filename: str, raw_bytes: bytes)`.
  - Returns `(markdown: str, summary: str)`.
  - Calls `apps/backend/app/agents/raw_requirement_format_converter/skills/pdf_to_markdown/scripts/convert.cjs` for PDF.
  - Calls `apps/backend/app/agents/raw_requirement_format_converter/skills/docx_to_markdown/scripts/convert.cjs` for DOC/DOCX.
  - Directly decodes TXT/MD.
  - Handles failure with explicit conversion summaries.

- Modify: `apps/backend/app/services/document_service.py`
  - Remove import from `app.agents.raw_requirement_format_converter.parser`.
  - Import the dedicated service instead.
  - Keep upload, storage, mapping, merge, and version behavior unchanged.

- Modify: `apps/backend/app/agents/raw_requirement_format_converter/raw_requirement_format_converter_agent.py`
  - Change `skill_ids` from `("raw_requirement_format_converter",)` to `("pdf_to_markdown", "docx_to_markdown")`.

- Delete: `apps/backend/app/agents/raw_requirement_format_converter/parser.py`
  - This file is not an agent and should not sit in the agent package as upload service logic.

- Delete: `apps/backend/app/agents/raw_requirement_format_converter/skills/raw_requirement_format_converter/`
  - This wrapper skill only calls `parser.py`; it duplicates routing and hides the real skills.

- Modify: `apps/backend/tests/test_skill_loader.py`
  - Expect only `pdf_to_markdown` and `docx_to_markdown` as the format converter agent's `skill_ids`.
  - Assert the wrapper skill no longer exists.
  - Assert both real skills are scoped to `raw_requirement_format_converter`.

- Modify: `apps/backend/tests/test_document_service.py`
  - Add upload conversion tests that patch the new service module, not the agent parser.

- Create or modify: `apps/backend/tests/test_requirement_file_converter.py`
  - Cover direct TXT/MD conversion.
  - Cover PDF conversion invoking local `pdf_to_markdown`.
  - Cover DOCX conversion invoking local `docx_to_markdown`.
  - Cover missing Node or missing script returning clear failure.

---

### Task 1: Lock The New Boundary With Tests

**Files:**
- Modify: `apps/backend/tests/test_skill_loader.py`
- Create: `apps/backend/tests/test_requirement_file_converter.py`

- [ ] **Step 1: Update agent registry expectation**

In `apps/backend/tests/test_skill_loader.py`, change the format converter assertion to:

```python
def test_registry_exposes_requirement_file_agents(self):
    agents = agent_registry.list()

    self.assertEqual([agent.id for agent in agents], ["raw_requirement_format_converter"])
    self.assertEqual(agents[0].name, "原始需求格式转换智能体")
    self.assertEqual(agents[0].skill_ids, ("pdf_to_markdown", "docx_to_markdown"))
```

- [ ] **Step 2: Replace wrapper skill test**

Remove assertions for `raw_requirement_format_converter` skill. Add:

```python
def test_raw_requirement_format_converter_uses_only_real_conversion_skills(self):
    pdf_skill = skill_registry.get("pdf_to_markdown", agent_id="raw_requirement_format_converter")
    docx_skill = skill_registry.get("docx_to_markdown", agent_id="raw_requirement_format_converter")

    self.assertEqual(pdf_skill.agent_id, "raw_requirement_format_converter")
    self.assertEqual(docx_skill.agent_id, "raw_requirement_format_converter")
    self.assertIn("agents\\raw_requirement_format_converter\\skills\\pdf_to_markdown", pdf_skill.path)
    self.assertIn("agents\\raw_requirement_format_converter\\skills\\docx_to_markdown", docx_skill.path)

    with self.assertRaises(KeyError):
        skill_registry.get("raw_requirement_format_converter", agent_id="raw_requirement_format_converter")
```

- [ ] **Step 3: Add converter service tests**

Create `apps/backend/tests/test_requirement_file_converter.py`:

```python
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.services.requirement_file_converter import convert_requirement_file_to_markdown


class RequirementFileConverterTest(unittest.TestCase):
    def test_markdown_file_is_saved_directly(self):
        markdown, summary = convert_requirement_file_to_markdown("需求.md", "# 登录需求".encode("utf-8"))

        self.assertEqual(markdown, "# 登录需求\n")
        self.assertEqual(summary, "文本文件直接保存为 Markdown 转换稿。")

    def test_pdf_uses_local_pdf_skill_script(self):
        def fake_run(cmd, **_kwargs):
            output_path = Path(cmd[cmd.index("--output") + 1])
            output_path.write_text("# PDF 转换结果", encoding="utf-8")
            return Mock(returncode=0, stdout='{"pageCount": 2}', stderr="")

        with patch("app.services.requirement_file_converter.shutil.which", return_value="node"):
            with patch("app.services.requirement_file_converter.subprocess.run", side_effect=fake_run) as run:
                markdown, summary = convert_requirement_file_to_markdown("需求.pdf", b"%PDF-1.4")

        command = run.call_args.args[0]
        self.assertIn("raw_requirement_format_converter", command[1])
        self.assertIn("pdf_to_markdown", command[1])
        self.assertEqual(markdown, "# PDF 转换结果\n")
        self.assertEqual(summary, "已通过 pdf_to_markdown skill 转换，页数 2。")

    def test_docx_uses_local_docx_skill_script(self):
        def fake_run(cmd, **_kwargs):
            output_path = Path(cmd[cmd.index("--output") + 1])
            output_path.write_text("# DOCX 转换结果", encoding="utf-8")
            return Mock(returncode=0, stdout='{"pages": 1}', stderr="")

        with patch("app.services.requirement_file_converter.shutil.which", return_value="node"):
            with patch("app.services.requirement_file_converter.subprocess.run", side_effect=fake_run) as run:
                markdown, summary = convert_requirement_file_to_markdown("需求.docx", b"docx")

        command = run.call_args.args[0]
        self.assertIn("raw_requirement_format_converter", command[1])
        self.assertIn("docx_to_markdown", command[1])
        self.assertEqual(markdown, "# DOCX 转换结果\n")
        self.assertEqual(summary, "已通过 docx_to_markdown skill 转换，页数 1。")

    def test_pdf_missing_node_fails_clearly(self):
        with patch("app.services.requirement_file_converter.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as caught:
                convert_requirement_file_to_markdown("需求.pdf", b"%PDF-1.4")

        self.assertIn("缺少 Node.js", str(caught.exception))
```

- [ ] **Step 4: Run tests and confirm failure**

Run:

```powershell
cd apps/backend
python -m pytest tests/test_skill_loader.py tests/test_requirement_file_converter.py -q
```

Expected: fail because `requirement_file_converter.py` does not exist and the agent still references the wrapper skill.

---

### Task 2: Implement Dedicated Upload Conversion Service

**Files:**
- Create: `apps/backend/app/services/requirement_file_converter.py`

- [ ] **Step 1: Create the service module**

Create `apps/backend/app/services/requirement_file_converter.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


@dataclass(frozen=True)
class ConvertedRequirementFile:
    markdown: str
    summary: str


def convert_requirement_file_to_markdown(filename: str, raw_bytes: bytes) -> tuple[str, str]:
    lowered = filename.lower()
    if lowered.endswith((".md", ".markdown", ".txt")):
        return _normalize_text_markdown(filename, raw_bytes), "文本文件直接保存为 Markdown 转换稿。"
    if lowered.endswith(".pdf"):
        converted = _convert_with_local_skill("pdf_to_markdown", filename, raw_bytes)
        return converted.markdown, converted.summary
    if lowered.endswith((".doc", ".docx")):
        converted = _convert_with_local_skill("docx_to_markdown", filename, raw_bytes)
        return converted.markdown, converted.summary
    preview = _decode_text(raw_bytes)[:4000]
    markdown = f"# {filename}\n\n暂不支持该文件类型的完整结构解析，已保存文本预览。\n\n```\n{preview}\n```\n"
    return markdown, "文件类型暂不支持完整解析，已生成文本预览。"


def _normalize_text_markdown(filename: str, raw_bytes: bytes) -> str:
    text = _decode_text(raw_bytes).strip()
    if filename.lower().endswith((".md", ".markdown")):
        return text + "\n"
    return f"# {filename}\n\n{text}\n"


def _convert_with_local_skill(skill_id: str, filename: str, raw_bytes: bytes) -> ConvertedRequirementFile:
    node = shutil.which("node")
    if not node:
        raise RuntimeError(f"无法转换 {filename}：缺少 Node.js，不能执行 {skill_id} skill。")

    convert_script = _find_skill_convert_script(skill_id)
    if convert_script is None:
        raise RuntimeError(f"无法转换 {filename}：缺少 {skill_id} skill 转换脚本。")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / Path(filename).name
        output_path = temp_path / f"{input_path.stem}.md"
        input_path.write_bytes(raw_bytes)
        completed = subprocess.run(
            [node, str(convert_script), "--input", str(input_path), "--output", str(output_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"无法转换 {filename}：{skill_id} skill 执行失败。{detail}")
        if not output_path.exists():
            raise RuntimeError(f"无法转换 {filename}：{skill_id} skill 未生成 Markdown 输出。")
        markdown = output_path.read_text(encoding="utf-8").strip() + "\n"
        return ConvertedRequirementFile(markdown=markdown, summary=_conversion_summary_from_stdout(completed.stdout, skill_id))


def _find_skill_convert_script(skill_id: str) -> Path | None:
    path = (
        Path(__file__).parents[1]
        / "agents"
        / "raw_requirement_format_converter"
        / "skills"
        / skill_id
        / "scripts"
        / "convert.cjs"
    )
    return path if path.exists() else None


def _decode_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def _conversion_summary_from_stdout(stdout: str, skill_id: str) -> str:
    for line in reversed([item.strip() for item in stdout.splitlines() if item.strip()]):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        page_count = payload.get("pageCount") or payload.get("pages")
        if page_count:
            return f"已通过 {skill_id} skill 转换，页数 {page_count}。"
        return f"已通过 {skill_id} skill 转换。"
    return f"已通过 {skill_id} skill 转换。"
```

- [ ] **Step 2: Run converter service tests**

Run:

```powershell
cd apps/backend
python -m pytest tests/test_requirement_file_converter.py -q
```

Expected: converter tests pass or expose path issues to fix in this module only.

---

### Task 3: Rewire Upload Service Away From Agents

**Files:**
- Modify: `apps/backend/app/services/document_service.py`
- Test: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Replace agent parser import**

In `apps/backend/app/services/document_service.py`, replace:

```python
from app.agents.raw_requirement_format_converter.parser import requirement_file_parser_agent
```

with:

```python
from app.services.requirement_file_converter import convert_requirement_file_to_markdown
```

- [ ] **Step 2: Simplify `_convert_to_markdown`**

Replace `_convert_to_markdown` with:

```python
def _convert_to_markdown(filename: str, raw_bytes: bytes) -> tuple[str, str]:
    return convert_requirement_file_to_markdown(filename, raw_bytes)
```

- [ ] **Step 3: Run document service tests**

Run:

```powershell
cd apps/backend
python -m pytest tests/test_document_service.py -q
```

Expected: pass. Existing MD/TXT upload behavior remains unchanged.

---

### Task 4: Register Real Skills On The Agent

**Files:**
- Modify: `apps/backend/app/agents/raw_requirement_format_converter/raw_requirement_format_converter_agent.py`
- Delete: `apps/backend/app/agents/raw_requirement_format_converter/skills/raw_requirement_format_converter/scripts/convert_file.py`
- Delete: `apps/backend/app/agents/raw_requirement_format_converter/skills/raw_requirement_format_converter/SKILL.md`

- [ ] **Step 1: Change the agent skill list**

In `raw_requirement_format_converter_agent.py`, replace:

```python
skill_ids=("raw_requirement_format_converter",),
```

with:

```python
skill_ids=("pdf_to_markdown", "docx_to_markdown"),
```

- [ ] **Step 2: Remove wrapper skill directory**

Delete:

```text
apps/backend/app/agents/raw_requirement_format_converter/skills/raw_requirement_format_converter/
```

This removes the redundant `agent -> wrapper skill -> parser.py` path.

- [ ] **Step 3: Run skill registry tests**

Run:

```powershell
cd apps/backend
python -m pytest tests/test_skill_loader.py -q
```

Expected: pass. The only skills attached to `raw_requirement_format_converter` are `pdf_to_markdown` and `docx_to_markdown`.

---

### Task 5: Delete The Old Parser And Clean References

**Files:**
- Delete: `apps/backend/app/agents/raw_requirement_format_converter/parser.py`
- Modify tests that import the parser.

- [ ] **Step 1: Delete parser file**

Delete:

```text
apps/backend/app/agents/raw_requirement_format_converter/parser.py
```

- [ ] **Step 2: Search for stale references**

Run:

```powershell
rg -n "raw_requirement_format_converter\\.parser|requirement_file_parser_agent|parse_requirement_file_path|skills/raw_requirement_format_converter|raw_requirement_format_converter skill" apps/backend docs -S
```

Expected: no runtime references. Documentation references should either be removed or rewritten to describe the old behavior as replaced.

- [ ] **Step 3: Update docs to reflect the corrected boundary**

In `docs/superpowers/specs/2026-05-22-agents-directory-redesign.md`, update the format conversion section to say:

```text
上传接口属于 document_service/requirement_file_converter 服务链路，不属于 Agent Runtime。
raw_requirement_format_converter 智能体只注册 pdf_to_markdown 和 docx_to_markdown 两个实际转换 skill。
```

- [ ] **Step 4: Run stale reference search again**

Run the same `rg` command.

Expected: no stale runtime references.

---

### Task 6: Final Verification

**Files:**
- No new code expected unless tests expose issues.

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
cd apps/backend
python -m pytest tests/test_skill_loader.py tests/test_agent_runtime.py tests/test_document_service.py tests/test_requirement_file_converter.py -q
```

Expected: all pass.

- [ ] **Step 2: Run registry smoke check**

Run:

```powershell
cd apps/backend
python -c "from app.agents.registry import agent_registry; from app.agents.skills import skill_registry; print([a.id for a in agent_registry.list()]); print(sorted((s.agent_id, s.id) for s in skill_registry.list()))"
```

Expected output:

```text
['raw_requirement_format_converter']
[('raw_requirement_format_converter', 'docx_to_markdown'), ('raw_requirement_format_converter', 'pdf_to_markdown')]
```

- [ ] **Step 3: Run upload behavior smoke test**

Run:

```powershell
cd apps/backend
python -m pytest tests/test_document_service.py::DocumentServiceTest::test_upload_new_requirement_creates_one_document_with_multiple_pending_files -q
```

Expected: pass, proving upload still creates source document mappings and Markdown conversion files without importing any agent parser.

- [ ] **Step 4: Review diff boundary**

Run:

```powershell
git diff -- apps/backend/app/services apps/backend/app/agents apps/backend/tests docs/superpowers
```

Expected:

- Upload conversion code lives under `app/services`.
- Agent definition references only real conversion skills.
- No `parser.py` dependency remains in upload code.
- No wrapper `raw_requirement_format_converter` skill remains.

---

### Self-Review

- Spec coverage: The plan separates upload service logic from Agent Runtime, removes the wrapper skill, registers only `pdf_to_markdown` and `docx_to_markdown`, and preserves upload behavior.
- Placeholder scan: No placeholder tasks remain.
- Type consistency: The service returns `tuple[str, str]`, matching `document_service._convert_to_markdown`.
- Risk: If PDF/DOCX converter scripts require local `node_modules`, tests that mock `subprocess.run` will still pass; a real-file integration test can be added later once sample fixtures and dependencies are stable.
