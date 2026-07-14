# Global Performance Test Locust UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a global performance-test creation flow with project/environment/endpoint selection, unified load stages, controlled Locust script generation, and authenticated access to the native Locust Web UI.

**Architecture:** Extend the existing project-scoped performance-test aggregate instead of creating a parallel module. Persist test mode, data source, load stages, and circuit-breaker settings in JSON columns; render fixed-load scripts without a shape and non-fixed scripts with a deterministic `LoadTestShape`. Replace the headless LocalRunner child process with a per-run Locust Web subprocess bound to localhost and expose it through a project-authorized FastAPI proxy.

**Tech Stack:** FastAPI, Pydantic v2, SQLite, Locust 2.45.0, Next.js, React, TypeScript, Node contract tests, pytest.

## Global Constraints

- First release supports one endpoint per performance test.
- Test modes are `fixed`, `gradient`, `stress`, `spike`, and `endurance`.
- Fixed mode delegates users, spawn rate, and run time to the native Locust UI.
- Non-fixed modes use deterministic platform-generated `LoadTestShape` code.
- The platform does not render load charts or realtime Locust statistics.
- Secrets stay server-side and are injected only into the runtime snapshot.
- Existing uncommitted workspace changes must not be reverted or committed accidentally.

---

### Task 1: Extend Performance Test Contracts

**Files:**
- Modify: `apps/backend/app/schemas/performance_test.py`
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/repositories/performance_test_repo.py`
- Test: `apps/backend/tests/test_performance_testing.py`

**Interfaces:**
- Produces: `PerformanceDataConfig`, `PerformanceLoadStage`, `PerformanceCircuitBreaker`, and a mode-aware `PerformanceLoadConfig`.
- Produces persisted JSON fields `data_config_json` and `circuit_breaker_json`; `load_config_json` contains `mode` and `stages`.

- [ ] Add failing schema tests for fixed mode, ascending gradient stages, spike rollback, invalid descending gradient, JSON/CSV data settings, and circuit-breaker validation.
- [ ] Run `uv run pytest tests/test_performance_testing.py -q` and verify the new tests fail.
- [ ] Add the Pydantic models and validators, preserving defaults that can deserialize existing rows.
- [ ] Add schema columns plus idempotent seed migration helpers.
- [ ] Update repository create/update/serialize mappings for the new JSON fields.
- [ ] Run `uv run pytest tests/test_performance_testing.py -q` and verify it passes.

### Task 2: Render Data Sources and Load Shapes

**Files:**
- Modify: `apps/backend/app/services/performance_testing/models.py`
- Modify: `apps/backend/app/services/performance_testing/plan_builder.py`
- Modify: `apps/backend/app/services/performance_testing/ai_plan_builder.py`
- Modify: `apps/backend/app/services/performance_testing/script_renderer.py`
- Modify: `apps/backend/app/services/performance_testing/validator.py`
- Test: `apps/backend/tests/test_performance_script_generation.py`

**Interfaces:**
- Consumes: mode-aware `load_config`, `data_config`, and success rules from Task 1.
- Produces: `LocustScriptPlan.load.mode`, `LocustScriptPlan.load.stages`, and `LocustScriptPlan.data`.
- Produces generated code containing `PerformanceLoadShape` only for non-fixed modes.

- [ ] Add failing tests that fixed scripts omit `LoadTestShape`, gradient scripts emit deterministic stage ticks, and JSON data selection supports sequential/random strategies.
- [ ] Run `uv run pytest tests/test_performance_script_generation.py -q` and verify failure.
- [ ] Extend plan models and deterministic plan construction.
- [ ] Render controlled data selection helpers and `PerformanceLoadShape` without accepting model-generated Python.
- [ ] Keep validator import allowlists compatible with `LoadTestShape` and generated helpers.
- [ ] Run the script-generation tests and verify they pass.

### Task 3: Launch Locust Web and Proxy It

**Files:**
- Modify: `apps/backend/app/services/performance_testing/runner.py`
- Replace behavior in: `apps/backend/app/services/performance_testing/runtime.py`
- Modify: `apps/backend/app/services/performance_testing/run_service.py`
- Modify: `apps/backend/app/repositories/performance_run_repo.py`
- Modify: `apps/backend/app/schemas/performance_test.py`
- Modify: `apps/backend/app/api/v1/performance_runs.py`
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Test: `apps/backend/tests/test_performance_runtime.py`
- Test: `apps/backend/tests/test_performance_run_service.py`

**Interfaces:**
- Produces: `locust_ui_path` and `locust_web_port` on `PerformanceRunOut`.
- Produces: `launch_locust_web_process(run_dir, port) -> pid` and localhost-only port allocation.
- Produces: authenticated HTTP proxy route `/projects/{project_id}/performance-test-runs/{run_id}/locust-ui/{path:path}`.

- [ ] Add failing tests for localhost port allocation, Locust Web command arguments, project authorization, immutable proxy targets, and UI URL serialization.
- [ ] Run the two targeted test modules and verify failure.
- [ ] Persist the internal web port and launch `locust --web-host 127.0.0.1 --web-port <port>` with the confirmed script.
- [ ] Replace headless auto-start semantics: creating a run starts the Web UI and leaves the load test for Locust UI control.
- [ ] Proxy HTML, static assets, Socket.IO polling, and API requests using `httpx`, stripping hop-by-hop headers and never accepting a client-provided target.
- [ ] Mark dead Locust Web processes unavailable and release their ports during recovery.
- [ ] Run targeted runtime and service tests and verify they pass.

### Task 4: Build the Global Creation Page

**Files:**
- Create: `apps/frontend/src/app/(main)/performance-tests/new/page.tsx`
- Refactor: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-form.tsx`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/load-stage-editor.tsx`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-data-editor.tsx`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/all-performance-test-list.tsx`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-list.tsx`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Test: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Consumes: `/projects`, project-scoped environments/endpoints/test cases, request preview, and the extended create payload.
- Produces: global route `/performance-tests/new`; optional `projectId` query preselection.

- [ ] Add failing contract assertions for the global route, project selector, five mode labels, stage editor, data source options, and absence of `LoadProfileRail`.
- [ ] Run `node --test tests/performance-testing-contract.test.mjs` and verify failure.
- [ ] Make `PerformanceTestForm` accept optional initial project ID and load active projects itself.
- [ ] Reset environment, endpoint, source case, request data, and performance data when project changes.
- [ ] Implement full-width sections for request, data, stages, goals, and circuit breaker; fixed mode hides stages.
- [ ] Route both global and project list creation actions to `/performance-tests/new`, using `?projectId=` for project context.
- [ ] Run the frontend contract test and verify it passes.

### Task 5: Open Native Locust UI From Script Review

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/script-review.tsx`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-detail.tsx`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Consumes: `PerformanceRun.locust_ui_path` from Task 3.
- Produces: `createPerformanceRun` followed by `window.open(locust_ui_path, "_blank", "noopener,noreferrer")`.

- [ ] Add failing assertions that confirmed scripts expose “启动 Locust UI” and open the backend-provided proxy path in a new tab.
- [ ] Run the contract test and verify failure.
- [ ] Change the confirmed-script action from routing to the platform run workspace to launching the run and opening native Locust UI.
- [ ] Keep run history links available for audit, but remove realtime-workspace language from the creation flow.
- [ ] Run the contract test and verify it passes.

### Task 6: Verify the End-to-End Slice

**Files:**
- Test: `apps/backend/tests/test_performance_integration.py`
- Test: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Consumes all previous tasks.
- Produces a verified global create → script confirm → Locust Web UI launch path.

- [ ] Add an integration test that creates a non-fixed task, confirms its generated script, launches Locust Web, and verifies the proxy root responds.
- [ ] Run targeted backend performance tests.
- [ ] Run the frontend performance contract test.
- [ ] Run backend formatting/type checks already configured by the repository.
- [ ] Run frontend formatting/type checks already configured by the repository.
- [ ] Review `git diff --check` and confirm unrelated dirty files were not reverted.
