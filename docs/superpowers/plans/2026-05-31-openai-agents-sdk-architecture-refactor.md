# OpenAI Agents SDK Architecture Refactor Implementation Plan

> Superseded: 本计划中的 `prompts.py`、薄 `runner.py`、`AgentDefinition` 迁移方向已被废弃。当前执行计划为 `docs/superpowers/plans/2026-06-01-openai-agents-sdk-per-agent-directory.md`，按每个智能体一个目录和 SDK 原生 `Agent + workflow` 结构实施。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor backend agent architecture so each `app/agents/{agent}` package owns its Agent SDK definition, input builder, structured output contract, and runner. Remove direct generic `run_agent()` calls from product services and API routes.

**Architecture:** Align with OpenAI Agents SDK: `Agent` owns instructions/tools/output type, `Runner.run(agent, input)` executes, agent-specific runners expose typed product entrypoints, and services only orchestrate business data, persistence, logs, and quality gates.

**Spec:** `docs/superpowers/specs/2026-05-31-openai-agents-sdk-architecture-refactor-spec.md`

**Tech Stack:** FastAPI backend, Python, Pydantic, OpenAI Agents SDK, pytest.

---

### Task 1: Add Architecture Boundary Tests

**Files:**
- Create: `apps/backend/tests/test_agent_architecture_boundaries.py`

- [ ] **Step 1: Add service/API boundary tests**

Create tests that scan Python files and fail if `app/services` or `app/api` directly imports generic runtime:

```python
from pathlib import Path


BACKEND_APP = Path(__file__).resolve().parents[1] / "app"


def _python_files(root: Path):
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def test_services_do_not_call_generic_agent_runtime():
    offenders = []
    for path in _python_files(BACKEND_APP / "services"):
        text = path.read_text(encoding="utf-8")
        if "from app.agents.runtime import run_agent" in text:
            offenders.append(str(path.relative_to(BACKEND_APP.parent)))
    assert offenders == []


def test_api_does_not_call_generic_agent_runtime():
    offenders = []
    for path in _python_files(BACKEND_APP / "api"):
        text = path.read_text(encoding="utf-8")
        if "from app.agents.runtime import run_agent" in text:
            offenders.append(str(path.relative_to(BACKEND_APP.parent)))
    assert offenders == []
```

- [ ] **Step 2: Add agent package shape test**

Initially allow both legacy `*_agent.py` and new `agent.py` during migration:

```python
def test_agent_packages_have_definition_entrypoint():
    agent_root = BACKEND_APP / "agents"
    ignored = {"__pycache__", "skills"}
    missing = []
    for package in sorted(path for path in agent_root.iterdir() if path.is_dir()):
        if package.name.startswith("_") or package.name in ignored:
            continue
        has_new = (package / "agent.py").exists()
        has_legacy = any(package.glob("*_agent.py"))
        if not has_new and not has_legacy:
            missing.append(package.name)
    assert missing == []
```

- [ ] **Step 3: Run tests and capture expected RED**

Run:

```bash
cd apps/backend
uv run pytest tests/test_agent_architecture_boundaries.py -q
```

Expected: fails because services currently import `run_agent`.

### Task 2: Make Runtime SDK-Oriented

**Files:**
- Modify: `apps/backend/app/agents/runtime.py`
- Test: `apps/backend/tests/test_agent_runtime.py` or create replacement if missing

- [ ] **Step 1: Rename runtime input parameter**

Change:

```python
async def run_agent(agent_id: str, prompt: str) -> AgentRunResult:
```

to:

```python
async def run_agent(agent_id: str, agent_input: Any) -> AgentRunResult:
```

Update internal logging from `prompt_len` to `input_len`:

```python
input_len=len(str(agent_input))
```

Pass `agent_input` to `Runner.run`.

- [ ] **Step 2: Keep compatibility for existing callers**

No caller signature changes are required because existing callers pass positional second argument. Do not rename all callsites in this task.

- [ ] **Step 3: Add or update runtime unit test**

Verify `run_agent()` passes the second argument through to `Runner.run` and still returns `AgentRunResult` metadata.

- [ ] **Step 4: Run focused runtime tests**

Run:

```bash
cd apps/backend
uv run pytest tests/test_agent_runtime.py -q
```

If `tests/test_agent_runtime.py` is currently deleted or unavailable, create focused coverage in `tests/test_agent_architecture_boundaries.py` only after confirming with repository state.

### Task 3: Update Agent Registry for New `agent.py`

**Files:**
- Modify: `apps/backend/app/agents/registry.py`
- Test: `apps/backend/tests/test_skill_loader.py`

- [ ] **Step 1: Support both new and legacy definition files**

Update discovery to scan:

```text
app/agents/*/agent.py
app/agents/*/*_agent.py
```

During migration, if both exist in one package, prefer `agent.py` and ignore legacy `*_agent.py`.

- [ ] **Step 2: Keep sort behavior**

Preserve sorting by `(sort_order, id)`.

- [ ] **Step 3: Add registry test**

Assert all current agent IDs are still discovered:

```python
{
    "document_editor",
    "knowledge_builder",
    "raw_requirement_format_converter",
    "requirement_analysis",
    "requirement_merge",
    "site_exploration",
}
```

- [ ] **Step 4: Run registry tests**

Run:

```bash
cd apps/backend
uv run pytest tests/test_skill_loader.py -q
```

### Task 4: Migrate `document_editor`

**Files:**
- Create: `apps/backend/app/agents/document_editor/agent.py`
- Create: `apps/backend/app/agents/document_editor/prompts.py`
- Create: `apps/backend/app/agents/document_editor/runner.py`
- Modify: `apps/backend/app/agents/document_editor/__init__.py`
- Modify: `apps/backend/app/api/v1/agents.py`
- Delete: `apps/backend/app/services/document_editor_service.py`
- Test: replace `apps/backend/tests/test_document_editor_service.py` with agent runner tests

- [ ] **Step 1: Create `agent.py` with structured output**

Move the definition from `document_editor_agent.py` into `agent.py`, import `DocumentEditOutput`, and set:

```python
output_type=DocumentEditOutput,
```

Move all durable behavior rules into `instructions`:

- only edit according to the user instruction
- do not create unconfirmed business facts
- keep unrelated Markdown structure
- return `DocumentEditOutput`
- provide warnings for unsupported fact additions

- [ ] **Step 2: Create `prompts.py`**

Move input formatting into:

```python
def build_document_edit_input(input_data: DocumentEditInput) -> str:
    ...
```

This function must include only run-specific data: document type, title, instruction, content.

- [ ] **Step 3: Create `runner.py`**

Implement:

```python
async def run_document_editor(input_data: DocumentEditInput) -> DocumentEditOutput:
    result = await run_agent("document_editor", build_document_edit_input(input_data))
    return DocumentEditOutput.model_validate(result.output)
```

Do not manually strip Markdown fences here unless non-OpenAI compatible provider behavior requires a documented fallback.

- [ ] **Step 4: Wire API directly to agent runner**

In `apps/backend/app/api/v1/agents.py`, replace:

```python
from app.services.document_editor_service import edit_document
```

with:

```python
from app.agents.document_editor.runner import run_document_editor
```

and call `run_document_editor(payload)`.

- [ ] **Step 5: Delete old service**

Delete `apps/backend/app/services/document_editor_service.py`.

- [ ] **Step 6: Add focused tests**

Test:

- prompt builder contains document data
- agent definition has `output_type=DocumentEditOutput`
- API route calls typed runner or runner validates output

- [ ] **Step 7: Run focused tests**

Run:

```bash
cd apps/backend
uv run pytest tests/test_agent_architecture_boundaries.py tests/test_document_editor_service.py -q
```

If the old service test is deleted, create `tests/test_document_editor_agent.py` and run it instead.

### Task 5: Migrate `raw_requirement_format_converter`

**Files:**
- Create: `apps/backend/app/agents/raw_requirement_format_converter/agent.py`
- Create: `apps/backend/app/agents/raw_requirement_format_converter/prompts.py`
- Create: `apps/backend/app/agents/raw_requirement_format_converter/runner.py`
- Modify: `apps/backend/app/services/document_file_service.py`
- Modify or delete: `apps/backend/app/services/raw_requirement_format_converter_service.py`
- Test: `apps/backend/tests/test_raw_requirement_format_converter_service.py`

- [ ] **Step 1: Move agent definition to `agent.py`**

Preserve `output_type=RequirementConversionOutput`.

- [ ] **Step 2: Move prompt builder to `prompts.py`**

Move `_build_agent_prompt` out of service.

- [ ] **Step 3: Add typed runner**

Implement:

```python
async def run_raw_requirement_format_converter(input_data: RequirementConversionInput) -> RequirementConversionOutput:
    ...
```

- [ ] **Step 4: Re-evaluate deterministic normalization**

If `normalize_requirement_markdown` is deterministic, keep it outside the LLM runner and call it from the business service after agent output. If it is agent behavior, move the call into runner. Record the decision in comments or tests.

- [ ] **Step 5: Update service imports**

`document_file_service.py` should call the typed runner or a thin deterministic conversion service, not generic runtime.

- [ ] **Step 6: Run focused tests**

Run:

```bash
cd apps/backend
uv run pytest tests/test_raw_requirement_format_converter_service.py tests/test_agent_architecture_boundaries.py -q
```

### Task 6: Migrate `requirement_analysis`

**Files:**
- Create: `apps/backend/app/agents/requirement_analysis/agent.py`
- Create: `apps/backend/app/agents/requirement_analysis/prompts.py`
- Create: `apps/backend/app/agents/requirement_analysis/runner.py`
- Modify: `apps/backend/app/services/requirement_analysis_service.py`
- Test: `apps/backend/tests/test_requirement_analysis_service.py`

- [ ] **Step 1: Move definition to `agent.py`**

Preserve `output_type=RequirementAnalysisOutput`.

- [ ] **Step 2: Move `_build_agent_prompt` to `prompts.py`**

Service must no longer own prompt construction.

- [ ] **Step 3: Add typed runner**

Implement:

```python
async def run_requirement_analysis(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    ...
```

- [ ] **Step 4: Update service**

Service handles reading versions, saving analysis artifacts, and logs. It calls `run_requirement_analysis`.

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd apps/backend
uv run pytest tests/test_requirement_analysis_service.py tests/test_agent_architecture_boundaries.py -q
```

### Task 7: Migrate `knowledge_builder`

**Files:**
- Create: `apps/backend/app/agents/knowledge_builder/agent.py`
- Create: `apps/backend/app/agents/knowledge_builder/prompts.py`
- Create: `apps/backend/app/agents/knowledge_builder/runner.py`
- Modify: `apps/backend/app/services/knowledge_builder_service.py`
- Test: add focused knowledge builder agent/service tests if missing

- [ ] **Step 1: Move definition to `agent.py`**

Preserve `output_type=KnowledgeBuildOutput`.

- [ ] **Step 2: Move prompt builder to `prompts.py`**

Keep all durable knowledge-building instructions in agent `instructions`.

- [ ] **Step 3: Add typed runner**

Implement `run_knowledge_builder(...)`.

- [ ] **Step 4: Update service**

Service reads confirmed requirement/exploration inputs and writes knowledge artifacts. It calls the typed runner.

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd apps/backend
uv run pytest tests/test_global_knowledge_service.py tests/test_agent_architecture_boundaries.py -q
```

Adjust test list to the actual knowledge builder tests present after checking repository state.

### Task 8: Migrate `requirement_merge` In Stages

**Files:**
- Create: `apps/backend/app/agents/requirement_merge/agent.py`
- Create: `apps/backend/app/agents/requirement_merge/prompts.py`
- Create: `apps/backend/app/agents/requirement_merge/runner.py`
- Create: `apps/backend/app/agents/requirement_merge/outline_runner.py`
- Create: `apps/backend/app/agents/requirement_merge/assignment_runner.py`
- Create: `apps/backend/app/agents/requirement_merge/section_runner.py`
- Modify: `apps/backend/app/services/requirement_merge_service.py`
- Modify: `apps/backend/app/services/requirement_merge_outline_service.py`
- Modify: `apps/backend/app/services/requirement_outline_assignment_service.py`
- Modify: `apps/backend/app/services/requirement_section_merge_service.py`
- Test: requirement merge service and outline tests

- [ ] **Step 1: Move base definition to `agent.py`**

Keep `requirement_merge` instructions focused on durable merge behavior and output constraints.

- [ ] **Step 2: Extract target outline runner**

Move prompt construction and runtime call from `requirement_merge_outline_service.py` into `outline_runner.py`.

Service keeps:

- source outline flattening
- validation
- artifact writing
- fail-fast orchestration

- [ ] **Step 3: Extract assignment runner**

Move old-outline-to-target assignment prompt/runtime behavior into `assignment_runner.py`.

- [ ] **Step 4: Extract section merge runner**

Move section-level merge prompt/runtime behavior into `section_runner.py`.

- [ ] **Step 5: Extract repair prompts**

If repair prompts remain necessary, place them beside the corresponding runner. Do not keep repair prompt text in service.

- [ ] **Step 6: Keep deterministic rendering in services**

Markdown artifact rendering, quality checks, source block extraction, and version writes remain in services.

- [ ] **Step 7: Run focused tests after each extraction**

Run after each sub-step:

```bash
cd apps/backend
uv run pytest tests/test_requirement_outline_merge_services.py tests/test_requirement_merge_service.py -q
```

Then run architecture boundaries:

```bash
uv run pytest tests/test_agent_architecture_boundaries.py -q
```

### Task 9: Clarify `site_exploration` Boundary

**Files:**
- Inspect/Modify: `apps/backend/app/agents/site_exploration/agent.py`
- Inspect/Modify: `apps/backend/app/services/site_exploration_orchestrator.py`
- Test: `apps/backend/tests/test_site_exploration_orchestrator.py`

- [ ] **Step 1: Decide whether site exploration is an LLM agent**

Confirm based on current implementation:

- If Playwright runner is deterministic and no LLM plan generation is used, remove or de-register the `site_exploration` agent.
- If LLM is used to create an exploration plan, keep only plan generation in `app/agents/site_exploration`.

- [ ] **Step 2: Document decision in code**

Add a short comment in the relevant runner or orchestrator explaining why this path is or is not an OpenAI Agents SDK agent.

- [ ] **Step 3: Keep deterministic runner separate**

Playwright execution remains under `apps/backend/runners/playwright` and service/orchestrator code, not OpenAI Agents SDK runtime.

- [ ] **Step 4: Run focused tests**

Run:

```bash
cd apps/backend
uv run pytest tests/test_site_exploration_orchestrator.py tests/test_agent_architecture_boundaries.py -q
```

### Task 10: Clean Legacy Agent Definition Files

**Files:**
- Delete or empty legacy `apps/backend/app/agents/*/*_agent.py`
- Modify: `apps/backend/app/agents/registry.py`
- Test: `apps/backend/tests/test_skill_loader.py`

- [ ] **Step 1: Remove legacy files**

After all agents have `agent.py`, delete legacy `*_agent.py` files.

- [ ] **Step 2: Make registry strict**

Change registry discovery to only scan:

```text
app/agents/*/agent.py
```

- [ ] **Step 3: Update architecture test**

Change `test_agent_packages_have_definition_entrypoint` to require `agent.py` only.

- [ ] **Step 4: Run registry and architecture tests**

Run:

```bash
cd apps/backend
uv run pytest tests/test_skill_loader.py tests/test_agent_architecture_boundaries.py -q
```

### Task 11: Run Backend Regression

**Files:** no code changes unless failures reveal scoped defects.

- [ ] **Step 1: Run full backend tests**

Run:

```bash
cd apps/backend
uv run pytest -q
```

- [ ] **Step 2: Fix only regressions caused by this refactor**

Do not repair unrelated dirty worktree failures in this task.

- [ ] **Step 3: Run API smoke checks**

At minimum verify:

- `GET /agents`
- `GET /agents/model-assignments`
- `POST /agents/document-editor/run`
- requirement upload/conversion path
- requirement analysis path
- requirement merge path

### Task 12: Manual Product Verification

**Files:** no code changes unless failures reveal scoped defects.

- [ ] **Step 1: Start backend and frontend**

Use existing project commands from README/package config.

- [ ] **Step 2: Verify document editor flow**

Open a requirement document standard Markdown preview and run AI edit. Confirm:

- edited content is saved
- warnings display if present
- operation task clears

- [ ] **Step 3: Verify model assignment UI**

Open model assignment page and confirm agents still list with names/descriptions.

- [ ] **Step 4: Verify requirement merge**

Run a small merge and confirm artifacts still write correctly.

### Task 13: Update Documentation References

**Files:**
- Modify: `docs/superpowers/specs/2026-05-22-agents-directory-redesign.md` only if needed
- Modify: `docs/superpowers/specs/2026-05-23-requirement-merge-agent-skill-boundary-spec.md` only if needed

- [ ] **Step 1: Add supersession notes where specs conflict**

If older specs say services own prompt construction or call generic runtime, add a short note pointing to:

```text
docs/superpowers/specs/2026-05-31-openai-agents-sdk-architecture-refactor-spec.md
```

- [ ] **Step 2: Do not rewrite old business specs wholesale**

Only clarify architecture precedence.

### Completion Checklist

- [ ] `app/services` has no direct `from app.agents.runtime import run_agent`.
- [ ] `app/api` has no direct `from app.agents.runtime import run_agent`.
- [ ] Each product agent has `agent.py`, `prompts.py`, and `runner.py`.
- [ ] Structured output agents set `output_type`.
- [ ] `document_editor_service.py` is deleted.
- [ ] Generic `/agents/{agent_id}/run` remains available for debugging only.
- [ ] Full backend test suite passes or unrelated pre-existing failures are documented.
- [ ] Manual document edit, model assignment, conversion, analysis, and merge flows are verified.
