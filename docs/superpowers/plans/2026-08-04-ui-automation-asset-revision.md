# UI Automation Asset Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe asset revision flow that accepts an optional user instruction, repairs missing business-step mappings from the current asset, avoids duplicate list rows, and exposes UI automation tasks in the task center.

**Architecture:** Existing assets remain the stable identity. A revision creates a linked generation run with `target_asset_id`, copies the current suite into an isolated staging workspace, applies deterministic mapping repair when unambiguous or invokes the existing AI agent with revision context, validates the staged suite, then atomically publishes and updates the same asset. Frontend active revision runs are merged into their target asset row.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, Next.js/React/TypeScript, Node contract tests.

## Global Constraints

- Do not modify original manual or approved test cases.
- Empty user instruction means minimal repair for the structured reason code.
- Prefer deterministic mapping; never guess ambiguous mappings.
- Revision failure must leave the current asset usable and unchanged.
- Existing workspace changes and runtime database contents must not be reverted.
- Do not create commits unless explicitly requested.

---

### Task 1: Revision Run Persistence and Interface

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/repositories/ui_automation_repo.py`
- Modify: `apps/backend/app/schemas/ui_automation.py`
- Modify: `apps/backend/app/api/v1/ui_automation.py`
- Test: `apps/backend/tests/test_ui_automation_api.py`
- Test: `apps/backend/tests/test_ui_automation_repo.py`

**Interfaces:**
- Produces: `POST /projects/{project_id}/ui-automation/assets/{asset_id}/revision-runs`
- Produces: generation run fields `target_asset_id`, `base_generation_run_id`, `generation_mode`, `reason_code`, `instruction`, `run_after_revision`, `revision_strategy`

- [ ] Write failing API and repository tests for revision fields, inherited environment/evidence, and active revision conflict.
- [ ] Run focused tests and confirm failures are caused by missing schema/interface behavior.
- [ ] Add schema migration, repository persistence, Pydantic request/output fields, and API route.
- [ ] Run focused tests until green.

### Task 2: Deterministic Business-Step Mapping Repair

**Files:**
- Create: `apps/backend/app/services/ui_automation/revision.py`
- Modify: `apps/backend/app/services/ui_automation/service.py`
- Test: `apps/backend/tests/test_ui_automation_revision.py`

**Interfaces:**
- Produces: `repair_business_step_mapping(plan: dict, case_data: dict) -> dict | None`
- Produces: `create_revision_run(project_id: str, asset_id: str, payload: dict, actor) -> dict`

- [ ] Write failing tests for exact step mapping, grouped technical actions, preservation of locators/assertions, and ambiguous mapping returning `None`.
- [ ] Run focused tests and verify red state.
- [ ] Implement deterministic repair using exact source IDs and unambiguous source-ID prefixes only.
- [ ] Implement revision run creation and conflict validation.
- [ ] Run focused tests until green.

### Task 3: Isolated AI Revision and Atomic Publication

**Files:**
- Modify: `apps/backend/app/agents/ui_automation/pytest_playwright/agent.py`
- Modify: `apps/backend/app/services/ui_automation/revision.py`
- Modify: `apps/backend/app/services/ui_automation/service.py`
- Test: `apps/backend/tests/test_ui_automation_revision.py`
- Test: `apps/backend/tests/test_ui_automation_generation_service.py`

**Interfaces:**
- Produces: revision-aware `generate_pytest_playwright_case(..., revision_context: dict | None = None)`
- Produces: staging workspace execution and publish result with `revision_strategy`

- [ ] Write failing tests proving current asset files are copied into staging and AI receives the revision reason/instruction.
- [ ] Write failing tests proving validation failure leaves formal files and asset pointers unchanged.
- [ ] Run focused tests and verify red state.
- [ ] Implement staging copy, deterministic-first strategy, AI fallback, collection validation, and atomic publish.
- [ ] Update the same asset ID and increment `source_version` only after successful validation.
- [ ] Run focused tests until green.

### Task 4: Revision Dialog and Single-Row List State

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/ui-automation/ui-automation-asset-detail.tsx`
- Modify: `apps/frontend/src/app/(main)/automation/ui/page.tsx`
- Test: `apps/frontend/tests/ui-automation-navigation-contract.test.mjs`

**Interfaces:**
- Consumes: revision run API and `target_asset_id`
- Produces: optional instruction dialog and `activeGenerationRun` merged row model

- [ ] Write failing contract tests for the revision dialog, structured reason code, optional instruction, real-run checkbox, and target-asset row merge.
- [ ] Run the contract test and verify red state.
- [ ] Add API types/client, dialog form, submit behavior, and active revision banner.
- [ ] Merge revision runs into existing asset rows while retaining initial-generation placeholder rows.
- [ ] Run frontend contract tests until green.

### Task 5: Task Center Integration

**Files:**
- Modify: `apps/backend/app/services/task_service.py`
- Test: `apps/backend/tests/test_task_service.py`
- Test: `apps/backend/tests/test_task_list_ordering.py`

**Interfaces:**
- Produces: task source types `ui_automation_generation_run` and `ui_automation_run`

- [ ] Write failing tests for UI revision and execution tasks in running-task and task-list responses.
- [ ] Run focused task tests and verify red state.
- [ ] Add UI status maps, running indicator types, collectors, titles, summaries, and detail URLs.
- [ ] Run focused task tests until green.

### Task 6: Regression Verification

**Files:**
- Verify only; no planned production edits.

- [ ] Run all UI automation backend tests.
- [ ] Run task service tests.
- [ ] Run frontend UI automation contract tests.
- [ ] Run backend formatting/import checks available in the repository.
- [ ] Run frontend typecheck or build if configured.
- [ ] Review `git diff --check` and ensure unrelated workspace changes remain untouched.
