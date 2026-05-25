# Agents Directory Redesign Implementation Plan

> Superseded note: The original plan kept upload conversion under `raw_requirement_format_converter/parser.py` and used a wrapper `raw_requirement_format_converter` skill. That boundary was later corrected in `docs/superpowers/plans/2026-05-22-upload-conversion-agent-boundary.md`: upload conversion now belongs to `app.services.requirement_file_converter`, and the format converter agent registers only `pdf_to_markdown` and `docx_to_markdown`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework backend agent discovery and skill lookup so each agent owns its own `*_agent.py` definition and `skills/` directory, and PDF/DOCX conversion uses the raw requirement format converter's local skills.

**Architecture:** Keep framework code in `apps/backend/app/agents/*.py`, move agent definitions into `agent_dir/*_agent.py`, and load skills from each agent directory rather than a shared pool. File conversion remains deterministic local tooling invoked by the format converter parser/service. Semantic analysis remains future Agent Runtime work and is not registered in this slice.

**Tech Stack:** FastAPI backend, Python 3.13, OpenAI Agents SDK, pytest/unittest, Node-based conversion skills.

---

### Task 1: Agent Definition Discovery

**Files:**
- Modify: `apps/backend/app/agents/registry.py`
- Create: `apps/backend/app/agents/raw_requirement_format_converter/raw_requirement_format_converter_agent.py`
- Modify: `apps/backend/app/agents/raw_requirement_format_converter/__init__.py`
- Test: `apps/backend/tests/test_skill_loader.py`

- [ ] **Step 1: Update tests for `*_agent.py` discovery**

In `apps/backend/tests/test_skill_loader.py`, change the registry assertion to expect only the current format converter agent:

```python
def test_registry_exposes_requirement_file_agents(self):
    agents = agent_registry.list()

    self.assertEqual([agent.id for agent in agents], ["raw_requirement_format_converter"])
    self.assertEqual(agents[0].name, "格式转换智能体")
    self.assertEqual(agents[0].skill_ids, ("raw_requirement_format_converter",))
```

- [ ] **Step 2: Run focused test and confirm failure**

Run:

```powershell
cd apps/backend
python -m pytest tests/test_skill_loader.py::SkillLoaderTest::test_registry_exposes_requirement_file_agents -q
```

Expected: fail because the format converter is not registered from `*_agent.py` yet.

- [ ] **Step 3: Add format converter agent definition**

Create `apps/backend/app/agents/raw_requirement_format_converter/raw_requirement_format_converter_agent.py`:

```python
from __future__ import annotations

from app.agents.definitions import AgentDefinition


agent_definition = AgentDefinition(
    id="raw_requirement_format_converter",
    name="格式转换智能体",
    description="负责将上传的 PDF、Word、TXT 和 Markdown 需求文件解析为 Markdown 工作稿。",
    instructions=(
        "你是 AI 测试系统中的格式转换智能体。"
        "你的职责是把上传的 Word、PDF、TXT、Markdown 等原始需求文件转换成结构稳定的 Markdown 标准文件。"
        "你只负责高保真格式转换、质量检查和无法识别项提示，不生成业务结论。"
    ),
    skill_ids=("raw_requirement_format_converter",),
    sort_order=10,
)
```

Keep `apps/backend/app/agents/raw_requirement_format_converter/__init__.py` as:

```python
from __future__ import annotations
```

- [ ] **Step 4: Update registry discovery**

Replace `discover_agent_definitions()` in `apps/backend/app/agents/registry.py` with logic that imports `app.agents.{agent_dir}.{stem}` for every `*/*_agent.py`:

```python
def discover_agent_definitions(agents_dir: Path | None = None) -> list[AgentDefinition]:
    root = agents_dir or Path(__file__).parent
    definitions: list[AgentDefinition] = []
    for agent_file in sorted(root.glob("*/*_agent.py")):
        package_dir = agent_file.parent
        if not _is_agent_package(package_dir):
            continue
        module = importlib.import_module(f"app.agents.{package_dir.name}.{agent_file.stem}")
        definition = getattr(module, "agent_definition", None)
        if isinstance(definition, AgentDefinition):
            definitions.append(definition)
    return sorted(definitions, key=lambda item: (item.sort_order, item.id))
```

- [ ] **Step 5: Run focused registry test**

Run:

```powershell
cd apps/backend
python -m pytest tests/test_skill_loader.py::SkillLoaderTest::test_registry_exposes_requirement_file_agents -q
```

Expected: pass.

### Task 2: Agent-Scoped Skill Loading

**Files:**
- Modify: `apps/backend/app/agents/skills/__init__.py`
- Modify: `apps/backend/app/agents/definitions.py`
- Test: `apps/backend/tests/test_skill_loader.py`

- [ ] **Step 1: Add `agent_id` and `agent_path` to `SkillDefinition`**

In `apps/backend/app/agents/definitions.py`, update `SkillDefinition`:

```python
@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    instructions: str = ""
    tools: tuple[FunctionTool, ...] = field(default_factory=tuple)
    path: str = ""
    enabled: bool = True
    agent_id: str | None = None
    agent_path: str = ""
```

- [ ] **Step 2: Update skill registry keying**

In `apps/backend/app/agents/skills/__init__.py`, make the registry store skills by `(agent_id, skill_id)` and select by agent:

```python
class SkillRegistry:
    def __init__(self, skills: list[SkillDefinition]) -> None:
        self._skills = {(skill.agent_id or "", skill.id): skill for skill in skills}

    def list(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def get(self, skill_id: str, agent_id: str | None = None) -> SkillDefinition:
        if agent_id is not None:
            return self._skills[(agent_id, skill_id)]
        matches = [skill for (_agent_id, item_id), skill in self._skills.items() if item_id == skill_id]
        if len(matches) != 1:
            raise KeyError(skill_id)
        return matches[0]

    def select(self, skill_ids: tuple[str, ...], agent_id: str | None = None) -> list[SkillDefinition]:
        selected: list[SkillDefinition] = []
        for skill_id in skill_ids:
            try:
                skill = self.get(skill_id, agent_id=agent_id)
            except KeyError:
                continue
            if skill.enabled:
                selected.append(skill)
        return selected
```

- [ ] **Step 3: Update skill discovery**

In the same file, update `discover_skills()` to scan each agent directory and attach scope metadata:

```python
def discover_skills(agents_dir: Path | None = None) -> list[SkillDefinition]:
    root = agents_dir or AGENTS_DIR
    skills: list[SkillDefinition] = []
    for package_dir in sorted(root.iterdir()):
        if not _is_agent_package(package_dir):
            continue
        for skill in load_skills(package_dir / "skills"):
            skills.append(
                SkillDefinition(
                    id=skill.id,
                    name=skill.name,
                    description=skill.description,
                    instructions=skill.instructions,
                    tools=skill.tools,
                    path=skill.path,
                    enabled=skill.enabled,
                    agent_id=package_dir.name,
                    agent_path=str(package_dir),
                )
            )
    return skills
```

- [ ] **Step 4: Update runtime skill selection**

In `apps/backend/app/agents/runtime.py`, change:

```python
skills = skill_registry.select(definition.skill_ids)
```

to:

```python
skills = skill_registry.select(definition.skill_ids, agent_id=definition.id)
```

- [ ] **Step 5: Add scoped skill assertion**

In `apps/backend/tests/test_skill_loader.py`, assert converter skill path is under its agent:

```python
skill = skill_registry.get("raw_requirement_format_converter", agent_id="raw_requirement_format_converter")
self.assertEqual(skill.agent_id, "raw_requirement_format_converter")
self.assertIn("agents\\raw_requirement_format_converter\\skills\\raw_requirement_format_converter", skill.path)
```

- [ ] **Step 6: Run skill loader tests**

Run:

```powershell
cd apps/backend
python -m pytest tests/test_skill_loader.py -q
```

Expected: pass.

### Task 3: Move PDF/DOCX Skills Into Format Converter

**Files:**
- Move: `apps/backend/app/agents/skills/pdf-to-markdown` to `apps/backend/app/agents/raw_requirement_format_converter/skills/pdf_to_markdown`
- Move: `apps/backend/app/agents/skills/docx-to-markdown` to `apps/backend/app/agents/raw_requirement_format_converter/skills/docx_to_markdown`
- Modify: moved `SKILL.md` frontmatter names if needed

- [ ] **Step 1: Move directories**

Use PowerShell `Move-Item` after confirming target paths:

```powershell
Move-Item -LiteralPath apps/backend/app/agents/skills/pdf-to-markdown -Destination apps/backend/app/agents/raw_requirement_format_converter/skills/pdf_to_markdown
Move-Item -LiteralPath apps/backend/app/agents/skills/docx-to-markdown -Destination apps/backend/app/agents/raw_requirement_format_converter/skills/docx_to_markdown
```

- [ ] **Step 2: Normalize skill names**

Edit moved `SKILL.md` files so frontmatter names are:

```yaml
name: pdf_to_markdown
```

and:

```yaml
name: docx_to_markdown
```

- [ ] **Step 3: Run discovery check**

Run:

```powershell
cd apps/backend
python - <<'PY'
from app.agents.skills import skill_registry
print(sorted((s.agent_id, s.id) for s in skill_registry.list()))
PY
```

Expected includes:

```text
('raw_requirement_format_converter', 'pdf_to_markdown')
('raw_requirement_format_converter', 'docx_to_markdown')
```

### Task 4: Use Agent-Local Conversion Skills

**Files:**
- Modify: `apps/backend/app/agents/raw_requirement_format_converter/parser.py`
- Test: `apps/backend/tests/test_document_service.py`
- Test: `apps/backend/tests/test_skill_loader.py`

- [ ] **Step 1: Add parser tests for local skill path**

Add tests that patch `subprocess.run` and verify converter script path includes:

```text
raw_requirement_format_converter\skills\pdf_to_markdown\scripts\convert.cjs
```

Expected summary should contain:

```text
已通过 pdf_to_markdown skill 转换
```

- [ ] **Step 2: Update parser skill ids**

In `parser.py`, change PDF and DOCX calls:

```python
external = _convert_with_installed_skill("pdf_to_markdown", filename, raw_bytes)
```

and:

```python
external = _convert_with_installed_skill("docx_to_markdown", filename, raw_bytes)
```

- [ ] **Step 3: Update `_find_skill_convert_script`**

Replace the user-home candidate list with agent-local paths:

```python
def _find_skill_convert_script(skill_id: str) -> Path | None:
    candidates = [
        Path(__file__).parent / "skills" / skill_id / "scripts" / "convert.cjs",
    ]
    return next((path for path in candidates if path.exists()), None)
```

- [ ] **Step 4: Include dependency failure detail**

When `completed.returncode != 0`, parse stdout/stderr JSON/text and raise or return a summary that includes missing dependency details. If fallback is kept, summary must say `fallback`.

- [ ] **Step 5: Run parser and document service tests**

Run:

```powershell
cd apps/backend
python -m pytest tests/test_skill_loader.py tests/test_document_service.py -q
```

Expected: pass.

### Task 5: Final Verification

**Files:**
- No new code expected unless previous tasks expose issues.

- [ ] **Step 1: Run backend test slice**

Run:

```powershell
cd apps/backend
python -m pytest tests/test_skill_loader.py tests/test_agent_runtime.py tests/test_document_service.py -q
```

Expected: pass.

- [ ] **Step 2: Run import smoke check**

Run:

```powershell
cd apps/backend
python -c "from app.agents.registry import agent_registry; from app.agents.skills import skill_registry; print([a.id for a in agent_registry.list()]); print(sorted((s.agent_id, s.id) for s in skill_registry.list()))"
```

Expected: only `raw_requirement_format_converter` is listed as an agent; `pdf_to_markdown` and `docx_to_markdown` appear under `raw_requirement_format_converter`.

- [ ] **Step 3: Review git diff**

Run:

```powershell
git diff -- apps/backend/app/agents apps/backend/tests/test_skill_loader.py apps/backend/tests/test_document_service.py docs/superpowers
```

Expected: changes are limited to the agents redesign and tests/docs.
