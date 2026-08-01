# API Scenario AI Orchestration Review Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace open-ended API scenario Agent generation with a bounded AI Planner and an editable, persisted per-step review workflow.

**Architecture:** Keep Canonical Scenario Model V2 as the executable model. Add a ReviewPlan V3 between AI planning and compilation, execute Planning once plus at most one Repair, persist user resolutions with optimistic locking, and render each interface invocation as an editable frontend card.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, SQLite, LangChain chat models without `create_agent`, React 19, Next.js 16, TypeScript, pytest, Node contract tests, Biome.

## Global Constraints

- Preserve current Canonical Scenario Model V2 and runtime request semantics.
- Maximum model calls per orchestration task: 2.
- Single model call timeout: 45 seconds.
- Total orchestration deadline: 90 seconds.
- Do not expose Secret values to the model, frontend, ReviewPlan, or logs.
- Review UI columns remain `字段 | AI 建议 | 最终值 | 状态`.
- Existing `schema_version < 3` unapplied plans expire; do not build a compatibility renderer.
- Do not overwrite unrelated uncommitted workspace changes.
- Do not create commits unless the user explicitly requests them.

---

### Task 1: ReviewPlan Domain Contract

**Files:**
- Modify: `apps/backend/app/agents/api_automation/orchestration/schemas.py`
- Modify: `apps/backend/app/schemas/api_automation.py`
- Modify: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Produces: `PlannerProposal`, `ApiScenarioAiReviewPlan`, `ApiScenarioAiReviewStep`, `ApiScenarioAiReviewFieldGroup`, `ApiScenarioAiReviewField`, `ApiScenarioAiReviewSaveIn`.
- Reuses: existing `ValueSource`, `ParameterTarget`, extractor, assertion, and canonical plan types.

- [ ] Add failing schema tests for field statuses, grouped request locations, full-step review saves, and `expected_review_revision`.
- [ ] Run focused schema tests and confirm they fail because ReviewPlan V3 types do not exist.
- [ ] Add the minimal Pydantic models and discriminated unions without duplicating ValueSource.
- [ ] Run focused schema tests and confirm they pass.

### Task 2: ReviewPlan Persistence

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Produces database columns: `proposal_json`, `review_json`, `review_revision`, `generation_meta_json`, `asset_fingerprint`.
- Preserves existing `plan_json` as the compiled Canonical Plan.

- [ ] Add failing migration tests proving existing databases receive all five columns with safe defaults.
- [ ] Run the migration test and confirm the columns are absent.
- [ ] Extend table creation and idempotent migration logic without disturbing current UI automation migrations.
- [ ] Run the migration tests and confirm they pass.

### Task 3: Bounded AI Planner

**Files:**
- Create: `apps/backend/app/services/api_automation/orchestration_planner.py`
- Modify: `apps/backend/app/agents/api_automation/orchestration/schemas.py`
- Modify: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Produces: `ApiScenarioPlanner.plan(snapshot) -> PlannerProposal`.
- Error contract: `PlannerTimeoutError`, `PlannerProtocolError`, `PlannerProviderError`.
- Accepts injected model factory and monotonic clock for deterministic tests.

- [ ] Add failing tests for one Planning call, one optional Repair call, no third call, JSON content parsing, timeout, and selected-endpoint-only input.
- [ ] Run focused planner tests and confirm failure.
- [ ] Implement direct chat invocation without `create_agent` or `ToolStrategy`.
- [ ] Enforce 45-second per-call timeout, two-call budget, and 90-second deadline.
- [ ] Add structured generation metadata without prompt or Secret leakage.
- [ ] Run planner tests and confirm they pass.

### Task 4: Review Normalization and Validation

**Files:**
- Create: `apps/backend/app/services/api_automation/orchestration_review.py`
- Create: `apps/backend/app/services/api_automation/orchestration_validator.py`
- Modify: `apps/backend/app/services/api_automation/orchestration_compiler.py`
- Modify: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Produces: `build_review_plan(proposal, assets, environment, scenario) -> ApiScenarioAiReviewPlan`.
- Produces: `validate_review_plan(review, assets) -> ReviewValidationResult`.
- Produces: `compile_review_plan(review, assets, environment) -> ScenarioPlanResult`.

- [ ] Add failing tests for exact environment matches resolving automatically.
- [ ] Add failing tests for semantic environment matches remaining pending.
- [ ] Add failing tests for AI literal Mock remaining pending.
- [ ] Add failing tests for `step_output` dependency derivation and reversed-order blocking.
- [ ] Add failing tests for repeated use of the same endpoint producing separate steps.
- [ ] Implement normalization, field grouping, confirmation summaries, and deterministic validation.
- [ ] Extend the compiler to consume ReviewPlan resolutions while preserving Canonical V2 output.
- [ ] Run focused normalization and compiler tests.

### Task 5: Bounded Job Runner and Lifecycle

**Files:**
- Create: `apps/backend/app/services/api_automation/orchestration_job_runner.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Modify: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Produces: `submit(plan_id)`, `cancel(plan_id)`, `shutdown()`.
- Service entrypoints: `enqueue_api_scenario_ai_plan`, `execute_api_scenario_ai_plan`, `get_api_scenario_ai_plan`.

- [ ] Add failing tests proving the route does not register FastAPI `BackgroundTasks` for AI orchestration.
- [ ] Add failing tests for one active Future per plan, cancellation, deadline failure, and no late-result overwrite.
- [ ] Implement an application-level `ThreadPoolExecutor(max_workers=2)` runner.
- [ ] Move model execution out of the response lifecycle and stop raising `HTTPException` from worker code.
- [ ] Make GET status read-only and return structured failed-state errors.
- [ ] Run lifecycle tests and confirm they pass.

### Task 6: Review Save and Apply Interfaces

**Files:**
- Modify: `apps/backend/app/schemas/api_automation.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Modify: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Adds: `PUT /projects/{project_id}/api-scenarios/ai-plans/{plan_id}/review`.
- Extends apply input with `expected_review_revision`.

- [ ] Add failing tests for full review save, optimistic locking, immutable endpoint metadata, recompilation, and revision increments.
- [ ] Add failing tests proving required pending fields, blocking validation, stale review revision, stale scenario revision, and stale asset fingerprint block apply.
- [ ] Implement full-review replacement at a single deep service seam.
- [ ] Recompile and persist `review_json`, `plan_json`, and `validation_json` transactionally.
- [ ] Update apply to use only the persisted current review revision.
- [ ] Run focused route and service tests.

### Task 7: Frontend Review Types and State

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/use-api-scenario-editor.ts`
- Modify: `apps/frontend/tests/api-scenario-ai-generation-drawer-contract.test.mjs`

**Interfaces:**
- Produces TypeScript types mirroring ReviewPlan V3.
- Adds: `saveApiScenarioAiPlanReview(projectId, planId, payload)`.
- Hook produces local review draft, save status, pending counts, reorder and field-resolution actions.

- [ ] Add failing Node contract tests for ReviewPlan V3 types, review save call, revision handling, and application gating.
- [ ] Run the contract test and confirm failure.
- [ ] Add ReviewPlan V3 API types while preserving unrelated current edits in `api-client.ts`.
- [ ] Implement serialized debounced saves and flush-before-apply behavior in the editor hook.
- [ ] Run the contract test and Biome check for modified files.

### Task 8: Per-Step Review Cards

**Files:**
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-ai-review-drawer.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-ai-review-step-card.tsx`
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-ai-review-field.tsx`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`
- Modify: `apps/frontend/tests/api-scenario-ai-generation-drawer-contract.test.mjs`

**Interfaces:**
- Drawer consumes ReviewPlan and hook actions only.
- Step card renders one interface invocation and grouped request fields.
- Field editor edits `resolved` ValueSource and confirmation status.

- [ ] Add failing contract tests for one card per step, grouped request sections, four-column review rows, collapsed resolved fields, no reason/confidence rendering, and apply gating.
- [ ] Run contract tests and confirm failure.
- [ ] Extract the current orchestration drawer from `api-scenario-editor.tsx` without overwriting the existing config-panel layout change.
- [ ] Implement independent step cards, pending counts, expandable resolved fields, typed source editors, and confirmation actions.
- [ ] Implement accessible keyboard controls and responsive stacked field rows.
- [ ] Run contract tests and targeted Biome checks.

### Task 9: Step Reordering and Conflict Recovery

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-ai-review-drawer.tsx`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/use-api-scenario-editor.ts`
- Modify: `apps/frontend/tests/api-scenario-ai-generation-drawer-contract.test.mjs`
- Modify: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Produces stable step reorder action using the full ordered step list.
- Handles `409 API_SCENARIO_AI_REVIEW_CONFLICT` by reloading the latest ReviewPlan.

- [ ] Add failing frontend tests for reorder persistence and conflict reload.
- [ ] Add failing backend tests for reversed data dependencies after reorder.
- [ ] Implement drag controls using existing project dependencies; do not add a drag library unless required.
- [ ] Display blocking dependency errors on the affected step and field.
- [ ] Run focused frontend and backend tests.

### Task 10: End-to-End Verification

**Files:**
- Modify only files required to fix failures introduced by Tasks 1-9.

**Interfaces:**
- Verifies the fixed SegmentCode → SSE scenario from generation through apply.

- [ ] Run backend focused suite:
  `cd apps/backend && .venv/Scripts/python.exe -m pytest tests/test_api_scenario_ai_orchestration.py -q`
- [ ] Run frontend contract test:
  `cd apps/frontend && node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs`
- [ ] Run frontend checks for modified files:
  `cd apps/frontend && npx biome check src/lib/api-client.ts src/components/ai-testing/api-automation/api-scenario-editor.tsx src/components/ai-testing/api-automation/use-api-scenario-editor.ts src/components/ai-testing/api-automation/api-scenario-ai-review-drawer.tsx src/components/ai-testing/api-automation/api-scenario-ai-review-step-card.tsx src/components/ai-testing/api-automation/api-scenario-ai-review-field.tsx`
- [ ] Run `git diff --check`.
- [ ] Review the implementation against every acceptance criterion in the approved Spec.
