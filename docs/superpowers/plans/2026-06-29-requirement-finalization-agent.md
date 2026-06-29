# Requirement Finalization Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone requirement finalization agent that rewrites final markdown by enhancing the standard requirement document skeleton, while keeping `/analysis/finalize` and the version system intact.

**Architecture:** Backend assembles a minimal finalization context from the latest analysis, standard markdown, and handled clarification answers. A new `requirement_finalization` agent generates the final markdown using the `requirement_analysis` model selection. The frontend only controls button visibility and calls the existing finalize endpoint.

**Tech Stack:** Python, FastAPI, Pydantic, LangChain, SQLite-backed repositories, Next.js/React, TypeScript, Vitest/Jest-style frontend tests, pytest.

---

### Task 1: Lock the finalization contract in backend schemas

**Files:**
- Modify: `apps/backend/app/schemas/document.py`
- Modify: `apps/backend/app/agents/requirement_analysis/schemas.py` if shared types need reuse
- Create: `apps/backend/app/agents/requirement_finalization/schemas.py`

- [ ] **Step 1: Write the failing schema test**

```python
from app.agents.requirement_finalization.schemas import RequirementFinalizationInput


def test_unresolved_no_op_clarifications_are_not_required_for_input():
    payload = RequirementFinalizationInput(
        document_name="订单管理需求",
        standard_markdown="# 订单管理需求\n",
        preliminary_markdown="# 需求理解\n",
        primary_document={"filename": "primary.md", "markdown_content": "## 需求背景\n..."},
        handled_clarifications=[],
        no_op_clarifications=[],
    )
    assert payload.document_name == "订单管理需求"
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `pytest apps/backend/tests/test_requirement_finalization_agent.py -v`
Expected: fail because the module and schema do not exist yet.

- [ ] **Step 3: Implement the minimal schema**

```python
from pydantic import BaseModel, Field


class FinalizationSourceDocument(BaseModel):
    filename: str
    markdown_content: str


class HandledClarification(BaseModel):
    question_id: str
    priority: str
    answer_markdown: str
    apply_status: str
    insertion_anchor: str = ""
    module_name: str = ""
    module_key: str = ""


class RequirementFinalizationInput(BaseModel):
    document_name: str
    standard_markdown: str
    preliminary_markdown: str
    primary_document: FinalizationSourceDocument
    supporting_documents: list[FinalizationSourceDocument] = Field(default_factory=list)
    handled_clarifications: list[HandledClarification] = Field(default_factory=list)
    no_op_clarifications: list[HandledClarification] = Field(default_factory=list)


class RequirementFinalizationOutput(BaseModel):
    final_requirement_markdown: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)
    unresolved_notes: list[str] = Field(default_factory=list)
    merge_notes: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run the test again and confirm it passes**

Run: `pytest apps/backend/tests/test_requirement_finalization_agent.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/schemas/document.py apps/backend/app/agents/requirement_finalization/schemas.py apps/backend/tests/test_requirement_finalization_agent.py
git commit -m "feat: add requirement finalization schemas"
```

### Task 2: Build finalization context assembly

**Files:**
- Create: `apps/backend/app/services/document/finalization_context.py`
- Modify: `apps/backend/app/services/document/service.py`
- Modify: `apps/backend/app/repositories/requirement_clarification_answer_repo.py` if query helpers are needed

- [ ] **Step 1: Write failing tests for context filtering**

```python
def test_no_op_clarifications_do_not_enter_model_context():
    context = build_finalization_context(...)
    assert context.no_op_clarifications == []
    assert all(item.apply_status != "not_applicable" for item in context.handled_clarifications)


def test_open_p0_p1_blocks_finalization_context():
    with pytest.raises(api_error):
        build_finalization_context(...)
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `pytest apps/backend/tests/test_requirement_finalization_context.py -v`
Expected: fail because the builder does not exist yet.

- [ ] **Step 3: Implement the minimal builder**

```python
def build_finalization_context(project_id: str, document_id: str, analysis_id: str) -> RequirementFinalizationInput:
    ...
```

Behavior:
- load latest analysis and standard markdown
- collect handled clarification answers only
- treat every `apply_status == "not_applicable"` item as internal-only, never pass it to the model
- reject any open P0/P1
- exclude unprocessed P2/P3 from model input entirely

- [ ] **Step 4: Re-run the tests**

Run: `pytest apps/backend/tests/test_requirement_finalization_context.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/services/document/finalization_context.py apps/backend/app/services/document/service.py apps/backend/tests/test_requirement_finalization_context.py
git commit -m "feat: assemble requirement finalization context"
```

### Task 3: Add the standalone finalization agent

**Files:**
- Create: `apps/backend/app/agents/requirement_finalization/__init__.py`
- Create: `apps/backend/app/agents/requirement_finalization/agent.py`
- Create: `apps/backend/app/agents/requirement_finalization/service.py`
- Create: `apps/backend/app/agents/requirement_finalization/system_prompt.py`
- Create: `apps/backend/app/agents/requirement_finalization/skills/requirement-finalization/SKILL.md`
- Create: `apps/backend/app/agents/requirement_finalization/skills/requirement-finalization/references/finalization-writing.md`

- [ ] **Step 1: Write the failing agent test**

```python
def test_finalization_agent_uses_requirement_analysis_model_assignment(monkeypatch):
    ...
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `pytest apps/backend/tests/test_requirement_finalization_agent.py -v`
Expected: fail because the agent package is missing.

- [ ] **Step 3: Implement the minimal agent wrapper**

```python
from app.agents.model_selection import build_agent_model, resolve_model_selection


CAPABILITY_ID = "requirement_analysis"


def requirement_finalization_agent(model, load_references: bool = True):
    ...
```

Behavior:
- bind a dedicated finalization skill directory
- use structured output with `RequirementFinalizationOutput`
- do not register a new capability id
- reuse `resolve_model_selection("requirement_analysis")`

- [ ] **Step 4: Re-run the agent test**

Run: `pytest apps/backend/tests/test_requirement_finalization_agent.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/agents/requirement_finalization
git commit -m "feat: add requirement finalization agent"
```

### Task 4: Rewrite finalize service to call the new agent and persist final markdown

**Files:**
- Modify: `apps/backend/app/services/document/service.py`
- Modify: `apps/backend/app/api/v1/requirements.py` only if request/response typing needs syncing

- [ ] **Step 1: Write the failing service test**

```python
def test_finalize_requirement_analysis_writes_agent_output_as_version(tmp_path):
    ...
```

- [ ] **Step 2: Run the service test and verify it fails**

Run: `pytest apps/backend/tests/test_requirement_finalization_service.py -v`
Expected: fail because finalize still writes the preliminary markdown directly.

- [ ] **Step 3: Implement the service change**

```python
finalization_input = build_finalization_context(project_id, document_id, payload.analysis_id)
result = await run_requirement_finalization(finalization_input)
version_path.write_text(result.final_requirement_markdown.rstrip() + "\n", encoding="utf-8")
```

Behavior:
- keep `/analysis/finalize` unchanged
- keep `requirement_analysis_finalize` as the version source action
- write the new markdown returned by the finalizer, not the raw preliminary markdown
- preserve idempotency and stale-analysis checks
- keep `P2/P3` no-op records out of the model input

- [ ] **Step 4: Re-run the service test**

Run: `pytest apps/backend/tests/test_requirement_finalization_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/services/document/service.py apps/backend/app/api/v1/requirements.py apps/backend/tests/test_requirement_finalization_service.py
git commit -m "feat: finalize requirement analysis through agent"
```

### Task 5: Update requirement detail page button visibility and finalize flow

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`
- Modify: frontend contract tests for the requirement detail page

- [ ] **Step 1: Add the failing frontend contract test**

```tsx
it("hides finalize button until P0 and P1 are handled", () => {
  ...
});
```

- [ ] **Step 2: Run the frontend test and verify it fails**

Run: `pnpm test -- --runInBand <target>`
Expected: fail because the visibility logic still reflects the old condition.

- [ ] **Step 3: Implement the button gating**

```tsx
const canFinalizeRequirement =
  Boolean(analysisResult) &&
  !requirementReviewRunning &&
  handledPendingAnalysisItems.every((item) => item.priority === "P2" || item.priority === "P3" || isPendingItemHandled(item));
```

Behavior:
- show the button only when the analysis is complete enough to finalize
- keep `P2/P3` unprocessed items from blocking visibility
- keep click behavior on the existing finalize endpoint

- [ ] **Step 4: Re-run the frontend test**

Run: `pnpm test -- --runInBand <target>`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx apps/frontend/tests/<target>
git commit -m "feat: gate requirement finalization in UI"
```

### Task 6: Add regression coverage for internal-only no-op handling and final markdown shape

**Files:**
- Create or modify: `apps/backend/tests/test_requirement_finalization_context.py`
- Create or modify: `apps/backend/tests/test_requirement_finalization_agent.py`
- Create or modify: `apps/backend/tests/test_requirement_finalization_service.py`

- [ ] **Step 1: Write the regression tests**

```python
def test_no_op_clarifications_never_enter_prompt_payload():
    ...


def test_final_markdown_keeps_standard_section_skeleton():
    ...
```

- [ ] **Step 2: Run the backend test suite subset**

Run: `pytest apps/backend/tests/test_requirement_finalization_context.py apps/backend/tests/test_requirement_finalization_agent.py apps/backend/tests/test_requirement_finalization_service.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/backend/tests/test_requirement_finalization_context.py apps/backend/tests/test_requirement_finalization_agent.py apps/backend/tests/test_requirement_finalization_service.py
git commit -m "test: cover requirement finalization flow"
```

## Self-Review

Coverage check:
- Spec goal: Task 3 and Task 4
- Independent agent directory: Task 3
- Reuse requirement_analysis model config: Task 3
- Final markdown keeps standard document skeleton: Task 4 and Task 6
- All no-op / unnecessary clarifications stay out of model input: Task 2 and Task 6
- P0/P1 blocking logic: Task 2 and Task 5
- Frontend button visibility: Task 5
- `/analysis/finalize` unchanged: Task 4

Placeholder scan:
- No TBD/TODO placeholders
- No vague “handle edge cases” wording
- File paths are explicit
- Test commands are explicit

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-29-requirement-finalization-agent.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
