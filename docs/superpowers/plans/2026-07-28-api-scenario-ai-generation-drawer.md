# API Scenario AI Generation Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert API scenario AI orchestration from a blocking Dialog flow into a right-side Drawer with background task status surfaced through the existing top task indicator.

**Architecture:** Keep `api_scenario_ai_plans` as the source of truth. The POST endpoint creates a persisted generating record and schedules the existing generation logic through FastAPI `BackgroundTasks`, returning a task handle immediately; the existing GET endpoint returns the completed preview. The frontend closes the Drawer after acceptance, reuses `TaskRunningIndicator`, and opens the result Drawer only when the user explicitly requests it.

**Tech Stack:** FastAPI, Pydantic, SQLite, Next.js 16, React 19, TypeScript, Radix/shadcn UI, existing contract tests, pytest.

## Global Constraints

- Reuse `api_scenario_ai_plans`, `/tasks/running`, `AI_TASK_STARTED_EVENT`, and existing Plan apply/version checks.
- Do not auto-apply generated plans.
- Do not show fake percentage progress.
- Do not modify unrelated existing worktree changes.
- Production code changes require a failing test first.

---

### Task 1: Define accepted-task response and background generation boundary

**Files:**
- Modify: `apps/backend/app/schemas/api_automation.py`
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Test: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Consumes: existing `ApiScenarioAiPlanIn` and current synchronous `create_api_scenario_ai_plan` logic.
- Produces: `ApiScenarioAiPlanAcceptedOut`, `enqueue_api_scenario_ai_plan(...)`, and a worker function that updates the existing plan row to completed/failed.

- [ ] **Step 1: Write the failing backend test**

Add a test that calls the route/service enqueue boundary with a fake background task collector and asserts the response contains `plan_id`, `scenario_id`, and `lifecycle_status == "generating"`; assert the collected task is the generation worker and the database row is `generating` before the worker runs.

- [ ] **Step 2: Run the focused test and verify RED**

Run from `D:\project\test_project\apps\backend`:

```text
..\\.venv\\Scripts\\python.exe -m pytest tests/test_api_scenario_ai_orchestration.py -k enqueue -q
```

Expected: FAIL because the accepted response and enqueue function do not exist.

- [ ] **Step 3: Implement the minimal accepted response**

Add a response model with `plan_id`, `scenario_id`, and `lifecycle_status`. Split the current service into a short enqueue function and a worker that receives the persisted `plan_id` plus serialized generation context. Keep the existing generation/compiler logic inside the worker and preserve `_fail_api_scenario_ai_plan`.

Change the route to accept `BackgroundTasks`, call the enqueue function, and schedule the worker after the row is committed. Keep the existing GET and apply routes unchanged.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the same pytest command. Expected: PASS.

- [ ] **Step 5: Run existing AI orchestration tests**

```text
..\\.venv\\Scripts\\python.exe -m pytest tests/test_api_scenario_ai_orchestration.py -q
```

Expected: existing synchronous service tests remain green, or are updated only where the public route contract intentionally changed.

### Task 2: Add lifecycle and duplicate-task protection

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/schemas/api_automation.py`
- Test: `apps/backend/tests/test_api_scenario_ai_orchestration.py`
- Test: `apps/backend/tests/test_api_automation_scenarios_tasks.py`

**Interfaces:**
- Consumes: `enqueue_api_scenario_ai_plan(...)` from Task 1.
- Produces: deterministic duplicate-task error or existing active task handle; task center sees only `generating` tasks.

- [ ] **Step 1: Write failing duplicate and status tests**

Cover: same project/scenario with a generating plan returns the existing plan handle or a stable conflict error; completed/failed plans do not block a new generation; task serialization maps `generating` to the existing running-task contract.

- [ ] **Step 2: Run focused tests and verify RED**

```text
..\\.venv\\Scripts\\python.exe -m pytest tests/test_api_scenario_ai_orchestration.py tests/test_api_automation_scenarios_tasks.py -k "duplicate or lifecycle or ai_plan" -q
```

Expected: FAIL for missing duplicate protection or status behavior.

- [ ] **Step 3: Implement minimal lifecycle checks**

Query `api_scenario_ai_plans` for active `generating` rows before insert. Return the existing handle when it belongs to the same scenario and project. Ensure worker success sets `lifecycle_status = completed`, worker exceptions set `failed`, and expired records are not treated as running.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the same command; expected PASS.

- [ ] **Step 5: Run task-service regression tests**

```text
..\\.venv\\Scripts\\python.exe -m pytest tests/test_task_service.py tests/test_api_automation_scenarios_tasks.py -q
```

Expected: PASS.

### Task 3: Update frontend API types and async submission flow

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/use-api-scenario-editor.ts`
- Test: `apps/frontend/tests/api-scenario-ai-generation-drawer-contract.test.mjs`

**Interfaces:**
- Consumes: accepted task response from Task 1 and existing `getApiScenarioAiPlan`.
- Produces: hook actions that submit, close the Drawer, notify the top task indicator, and recover a completed Plan by `plan_id`.

- [ ] **Step 1: Write failing frontend contract tests**

Assert source contains: accepted response typing, task handle storage, `notifyAiTaskStarted()` after acceptance, no `await` that keeps the input panel open until the full Plan is returned, and recovery through `getApiScenarioAiPlan`.

- [ ] **Step 2: Run the focused contract test and verify RED**

Run from `D:\project\test_project\apps\frontend`:

```text
node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs
```

Expected: FAIL because the new contract is absent.

- [ ] **Step 3: Implement minimal hook flow**

Change `generateAiPlan` to submit and receive the accepted handle, persist the handle in session storage keyed by project/scenario, call `notifyAiTaskStarted`, return without waiting for the full Plan, and reset local submitting state. Add a recovery action that queries the handle and sets `aiPlan` only when the lifecycle is completed.

- [ ] **Step 4: Run the focused contract test and type check**

```text
node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs
npm exec tsc -- --noEmit
```

Expected: contract test PASS and TypeScript reports no new errors.

### Task 4: Replace the Dialog with a non-blocking right Drawer

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/use-api-scenario-editor.ts`
- Test: `apps/frontend/tests/api-scenario-ai-generation-drawer-contract.test.mjs`

**Interfaces:**
- Consumes: hook submission/recovery actions from Task 3 and existing Plan preview/apply actions.
- Produces: `AiOrchestrationDrawer` with input, result, and explicit open behavior.

- [ ] **Step 1: Extend failing UI contract tests**

Assert the editor uses a right-side Drawer, no longer renders `DialogContent` for AI orchestration, closes immediately after accepted submission, and does not auto-open on completion.

- [ ] **Step 2: Run the focused contract test and verify RED**

```text
node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs
```

Expected: FAIL because the current component is still a Dialog and busy state controls its close behavior.

- [ ] **Step 3: Implement the Drawer**

Use the project’s existing Drawer component if available; otherwise use the existing Radix primitives with side-right positioning. Keep the current input and Plan preview content, but make `submitting` disable only the submit button. On accepted submission set the open state to false. Do not automatically open when polling detects completion. Preserve explicit `apply` and `discard` actions.

- [ ] **Step 4: Run focused frontend checks**

```text
node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs tests/api-automation-scenario-contract.test.mjs
npm run check -- --no-errors-on-unmatched
```

Expected: PASS with no new lint/format/type errors.

### Task 5: Make top task status actionable and verify end-to-end behavior

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/task-running-indicator.tsx`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Test: `apps/frontend/tests/api-scenario-ai-generation-drawer-contract.test.mjs`
- Test: `apps/backend/tests/test_api_scenario_ai_orchestration.py`

**Interfaces:**
- Consumes: persisted task detail URL and Plan handle from earlier tasks.
- Produces: top indicator task card with `查看生成草稿`, failure/retry affordance, and route/deep-link recovery.

- [ ] **Step 1: Write failing actionable-status assertions**

Assert task cards expose the existing detail URL and a visible action label for API scenario AI plan tasks; assert failure state is not rendered as an active spinner.

- [ ] **Step 2: Run focused tests and verify RED**

```text
node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs
..\\apps\\backend\\.venv\\Scripts\\python.exe -m pytest apps\\backend\\tests\\test_api_scenario_ai_orchestration.py -q
```

Expected: FAIL for the new action/status behavior.

- [ ] **Step 3: Implement minimal task-card behavior**

Show the existing task title/status and an action that navigates to the task detail URL. Use non-spinner icons for failed/error states. Keep the component generic for other task types.

- [ ] **Step 4: Run the targeted regression suite**

```text
node --test tests/api-scenario-ai-generation-drawer-contract.test.mjs tests/api-automation-scenario-contract.test.mjs tests/page-shell-header-contract.test.mjs
..\\.venv\\Scripts\\python.exe -m pytest tests/test_api_scenario_ai_orchestration.py tests/test_api_automation_scenarios_tasks.py tests/test_task_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Run final checks for touched packages**

```text
npm run check -- --no-errors-on-unmatched
..\\.venv\\Scripts\\python.exe -m pytest tests/test_api_scenario_ai_orchestration.py tests/test_api_automation_scenarios_tasks.py tests/test_task_service.py -q
```

Expected: PASS; report any pre-existing unrelated failures separately.
