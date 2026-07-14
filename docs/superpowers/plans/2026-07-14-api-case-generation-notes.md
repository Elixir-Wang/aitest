# API Case Generation Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate runnable API cases even when expected response details are incomplete, persist the model's generation explanation, and show it on the case detail page.

**Architecture:** Extend the structured agent case with a plain-text `generation_notes` field. Persist it into the existing `api_test_cases.notes` column and render the existing API `notes` field conditionally in the frontend. Keep the runner, database schema, and assertion model unchanged.

**Tech Stack:** Python, Pydantic, FastAPI service layer, SQLite repository, Next.js, React, Node contract tests.

---

### Task 1: Persist generation notes

**Files:**
- Modify: `apps/backend/tests/test_api_automation_generation_agent.py`
- Modify: `apps/backend/app/agents/api_automation/case_generation/schemas.py`
- Modify: `apps/backend/app/services/api_automation/service.py`

- [ ] Add a failing test that creates an `ApiGeneratedCase` with `generation_notes` and expects the serialized API case `notes` value to match.
- [ ] Run the focused backend test and verify it fails because the generated schema does not expose or persist the field.
- [ ] Add `generation_notes: str = ""` to `ApiGeneratedCase` and map it to the existing repository `notes` argument.
- [ ] Run the focused backend tests and verify they pass.

### Task 2: Relax and document Skill behavior

**Files:**
- Modify: `apps/backend/tests/test_api_automation_generation_agent.py`
- Modify: `apps/backend/app/agents/api_automation/case_generation/skills/api-automation-case-generation/SKILL.md`

- [ ] Add failing Skill contract assertions requiring runnable cases, correct/incorrect Mock data, and `generation_notes` when response facts are incomplete.
- [ ] Run the focused Skill contract test and verify it fails on the current Oracle skip rules.
- [ ] Replace mandatory skipping with inferred executable expectations plus explicit generation notes, while retaining the prohibition against silently inventing facts.
- [ ] Run the focused Skill contract test and verify it passes.

### Task 3: Show notes in case detail

**Files:**
- Modify: `apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs`
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/cases/[caseId]/page.tsx`

- [ ] Add failing frontend contract assertions requiring a conditional `testCase.notes` block titled `生成说明`.
- [ ] Run the focused frontend contract test and verify it fails.
- [ ] Add a restrained amber information card below the test description, rendered only when trimmed notes are non-empty.
- [ ] Run the focused frontend contract test and verify it passes.

### Task 4: Verify focused regression scope

**Files:**
- Test: `apps/backend/tests/test_api_automation_generation_agent.py`
- Test: `apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs`

- [ ] Run focused backend generation tests.
- [ ] Run focused frontend contract tests.
- [ ] Review the final diff to ensure no runner or database migration changes were introduced.
