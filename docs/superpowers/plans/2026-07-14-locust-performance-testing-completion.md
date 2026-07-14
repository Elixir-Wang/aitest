# Locust Performance Testing Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete performance testing stages two through six with deterministic script generation, real Locust LocalRunner execution, realtime results, artifact downloads, goal evaluation, AI-analysis fallback, and system integration.

**Architecture:** Keep performance test definitions in the existing CRUD service, and add focused script, run, statistics, reporting, and analysis modules. Every run consumes immutable JSON snapshots and executes Locust in a child process; the API reads persisted run-state artifacts and streams snapshots through SSE. The frontend adds script review and run workspace routes while reusing the existing API client and project-native components.

**Tech Stack:** Python 3.13, FastAPI, SQLite, Locust LocalRunner, Pydantic, Next.js, React, TypeScript, Node test runner, pytest.

## Global Constraints

- Locust is the only load execution and statistics engine.
- First release supports one endpoint and one local runner per run.
- AI outputs structured plans and analysis only; deterministic fallbacks must work without a model.
- Secrets never enter script-plan prompts, frontend state, snapshots returned by APIs, or analysis inputs.
- Confirmed immutable script versions are required before starting a run.
- Runner processes read immutable run snapshots instead of mutable business tables.
- No distributed workers, custom LoadShape, arbitrary Python editing, or multi-endpoint scenarios.

---

### Task 1: Locust Dependency and Script Plan

**Files:**
- Modify: `apps/backend/pyproject.toml`
- Modify: `apps/backend/uv.lock`
- Create: `apps/backend/app/services/performance_testing/models.py`
- Create: `apps/backend/app/services/performance_testing/plan_builder.py`
- Create: `apps/backend/app/services/performance_testing/script_renderer.py`
- Create: `apps/backend/app/services/performance_testing/validator.py`
- Create: `apps/backend/tests/test_performance_script_generation.py`

**Interfaces:**
- Produces: `build_default_plan(performance_test: dict) -> LocustScriptPlan`
- Produces: `render_locust_script(plan: LocustScriptPlan) -> str`
- Produces: `validate_locust_script(plan: LocustScriptPlan, source: str) -> ScriptValidationResult`

- [ ] Write failing tests proving the default plan excludes sensitive headers, renders `HttpUser`/`catch_response=True`, and rejects forbidden imports.
- [ ] Run `pytest -q tests/test_performance_script_generation.py` and verify failures are caused by missing modules.
- [ ] Add pinned Locust dependency and Pydantic plan/result models.
- [ ] Implement deterministic plan construction, template rendering, AST checks, compile checks, and isolated import validation.
- [ ] Run the focused tests and existing `tests/test_performance_testing.py` until green.

### Task 2: Script Version Lifecycle API

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/repositories/performance_test_repo.py`
- Create: `apps/backend/app/repositories/performance_script_repo.py`
- Create: `apps/backend/app/services/performance_testing/script_service.py`
- Modify: `apps/backend/app/schemas/performance_test.py`
- Modify: `apps/backend/app/api/v1/performance_tests.py`
- Create: `apps/backend/tests/test_performance_script_api.py`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/script-review.tsx`
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/performance-tests/[testId]/scripts/[scriptId]/page.tsx`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-detail.tsx`
- Modify: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Produces: `POST /projects/{project_id}/performance-tests/{test_id}/scripts/generate`
- Produces: `GET /projects/{project_id}/performance-tests/{test_id}/scripts`
- Produces: `GET /projects/{project_id}/performance-tests/{test_id}/scripts/{script_id}`
- Produces: `PATCH /projects/{project_id}/performance-tests/{test_id}/scripts/{script_id}/configuration`
- Produces: `POST /projects/{project_id}/performance-tests/{test_id}/scripts/{script_id}/confirm`

- [ ] Write failing repository/service/API tests for version increments, immutable confirmed versions, re-render on structured edits, validation errors, and project isolation.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement script repository, service orchestration, schemas, and endpoints.
- [ ] Add API client contracts and read-only script review UI with structured configuration editing and confirmation.
- [ ] Extend frontend contract tests and run backend/frontend focused suites until green.

### Task 3: Immutable Runs and Locust LocalRunner

**Files:**
- Create: `apps/backend/app/repositories/performance_run_repo.py`
- Create: `apps/backend/app/services/performance_testing/run_service.py`
- Create: `apps/backend/app/services/performance_testing/runner.py`
- Create: `apps/backend/app/services/performance_testing/runtime.py`
- Create: `apps/backend/app/services/performance_testing/stats_collector.py`
- Modify: `apps/backend/app/schemas/performance_test.py`
- Modify: `apps/backend/app/api/v1/performance_tests.py`
- Modify: `apps/backend/app/main.py`
- Create: `apps/backend/tests/test_performance_run_service.py`
- Create: `apps/backend/tests/test_performance_runtime.py`

**Interfaces:**
- Produces: `create_run(project_id, test_id, script_id, actor) -> dict`
- Produces: `stop_run(project_id, run_id, actor) -> dict`
- Produces: `recover_interrupted_runs() -> int`
- Produces: runtime CLI `python -m app.services.performance_testing.runtime --run-dir <path>`

- [ ] Write failing tests for confirmed-script enforcement, immutable snapshots, secret runtime injection boundaries, status transitions, stop requests, and startup interruption recovery.
- [ ] Write a local HTTP fixture runtime test that executes a short real Locust run and asserts Locust-native totals.
- [ ] Run focused tests and verify missing behavior failures.
- [ ] Implement run persistence, artifact directories, subprocess lifecycle, LocalRunner runtime, stats projection, and startup recovery.
- [ ] Add run create/get/list/stop endpoints and run all focused tests until green.

### Task 4: Realtime Statistics and Artifacts

**Files:**
- Create: `apps/backend/app/services/performance_testing/artifacts.py`
- Create: `apps/backend/app/api/v1/performance_run_events.py`
- Modify: `apps/backend/app/api/v1/performance_tests.py`
- Modify: `apps/backend/app/api/v1/router.py`
- Create: `apps/backend/tests/test_performance_run_events.py`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/run-workspace.tsx`
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/performance-test-runs/[runId]/page.tsx`
- Modify: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Produces: `GET /projects/{project_id}/performance-test-runs/{run_id}`
- Produces: `GET /projects/{project_id}/performance-test-runs/{run_id}/events`
- Produces: `GET /projects/{project_id}/performance-test-runs/{run_id}/artifacts/{artifact_name}`

- [ ] Write failing API tests for project isolation, SSE initial snapshot/update/terminal events, reconnection sequence IDs, and artifact allowlisting.
- [ ] Run focused tests and verify failures.
- [ ] Implement SSE polling over persisted snapshots and safe CSV/JSON/HTML artifact responses.
- [ ] Build Overview, Statistics, Charts, Failures, Exceptions, Logs, and Download tabs with reconnecting event consumption.
- [ ] Run backend and frontend focused suites until green.

### Task 5: Goal Evaluation and Analysis

**Files:**
- Create: `apps/backend/app/services/performance_testing/reporting.py`
- Create: `apps/backend/app/services/performance_testing/analysis_service.py`
- Create: `apps/backend/app/repositories/performance_analysis_repo.py`
- Modify: `apps/backend/app/schemas/performance_test.py`
- Modify: `apps/backend/app/api/v1/performance_tests.py`
- Create: `apps/backend/tests/test_performance_reporting.py`
- Create: `apps/backend/tests/test_performance_analysis.py`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/run-workspace.tsx`

**Interfaces:**
- Produces: `evaluate_goals(summary: dict, goal: dict) -> GoalEvaluation`
- Produces: `extract_analysis_facts(run: dict, artifacts: dict) -> AnalysisFacts`
- Produces: `POST /projects/{project_id}/performance-test-runs/{run_id}/analysis`
- Produces: `GET /projects/{project_id}/performance-test-runs/{run_id}/analysis`

- [ ] Write failing tests for each goal threshold, no-goal state, fact whitelist/redaction, evidence validation, repeated analysis versions, and deterministic fallback reports.
- [ ] Run focused tests and verify failures.
- [ ] Implement deterministic goal evaluation and sanitized fact extraction.
- [ ] Integrate the existing configured model path when available and persist a fallback analysis when unavailable or invalid.
- [ ] Add AI Analysis UI and run focused suites until green.

### Task 6: Task Center, Logs, Limits, and Permissions

**Files:**
- Modify: `apps/backend/app/services/performance_testing/run_service.py`
- Modify: `apps/backend/app/services/task_service.py`
- Modify: `apps/backend/app/repositories/operation_log_repo.py`
- Modify: `apps/backend/app/core/config.py`
- Create: `apps/backend/tests/test_performance_integration.py`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-list.tsx`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-detail.tsx`

**Interfaces:**
- Consumes: existing task and operation-log service contracts.
- Produces: configurable maximum users, spawn rate, duration, timeout, retained runs, and concurrent runs.

- [ ] Write failing integration tests for task lifecycle mirroring, operation logs, admin-only mutations, read-only access, concurrency limits, input ceilings, and cleanup policy.
- [ ] Run focused tests and verify failures.
- [ ] Implement task/log integration, configuration limits, permission checks, and retention cleanup.
- [ ] Surface disabled actions and traceable backend errors in project pages.
- [ ] Run focused tests until green.

### Task 7: Full Validation and Spec Closure

**Files:**
- Modify: `docs/superpowers/specs/2026-07-13-locust-performance-testing-module-design.md`
- Create: `docs/superpowers/specs/2026-07-14-locust-performance-testing-completion-report.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: verified completion evidence mapped to Spec section 32.

- [ ] Run all performance backend tests with `pytest -q tests/test_performance*.py`.
- [ ] Run the complete backend test suite and record unrelated failures separately.
- [ ] Run frontend contract tests, type checking, linting, and production build.
- [ ] Execute a local end-to-end smoke run against a disposable HTTP server and verify script confirmation, run completion, SSE snapshots, artifacts, goal status, and fallback analysis.
- [ ] Update the Spec status only for acceptance items backed by fresh evidence and write the completion report.
