# API Scenario Suite Batch Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace one-off scenario selection with reusable API scenario suites that can be run repeatedly, producing a new batch report for every execution.

**Architecture:** Add suite and suite-item persistence while keeping `api_batch_runs` as immutable execution instances. Running a suite creates a new batch and immediately creates existing single-scenario child runs from current saved scenario content. The frontend mirrors the scenario orchestration list with create/edit/delete/run actions.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, Next.js, React, TypeScript, Node contract tests.

## Global Constraints

- A suite uses exactly one API environment.
- A scenario may appear only once within a suite.
- Suites are reusable and each execution creates a new batch and report.
- Scenario execution uses current saved content at run submission time.
- Child runs execute serially in suite item order.
- Deleting a suite must preserve historical batches and reports.
- Do not modify unrelated uncommitted workspace changes.
- Do not commit unless explicitly requested.

---

### Task 1: Suite Persistence and Validation

**Files:**
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/repositories/api_automation_repo.py`
- Modify: `apps/backend/app/schemas/api_automation.py`
- Test: `apps/backend/tests/test_api_automation_batch_runs.py`

**Interfaces:**
- Produces repository CRUD for suites and ordered suite items.
- Produces `ApiScenarioSuiteCreateIn` and `ApiScenarioSuiteUpdateIn`.

- [ ] Add failing tests for suite creation, ordered items, duplicate rejection, update, and delete preservation.
- [ ] Run the focused backend tests and confirm failures are caused by missing suite support.
- [ ] Add `api_scenario_suites`, `api_scenario_suite_items`, and nullable `api_batch_runs.suite_id` schema support.
- [ ] Add repository create/find/list/update/delete and item replacement functions.
- [ ] Add request schemas that reject duplicate scenario IDs.
- [ ] Run focused tests and confirm persistence tests pass.

### Task 2: Suite Service and Routes

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Test: `apps/backend/tests/test_api_automation_batch_runs.py`

**Interfaces:**
- Produces suite CRUD service functions.
- Produces `run_api_scenario_suite(project_id, suite_id, actor)`.
- Produces `/api-scenario-suites` CRUD routes and `/{suite_id}/runs` route.

- [ ] Add failing service tests for project validation, unique scenarios, repeated execution, current saved content, and serial order.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement suite serialization including ordered scenarios and latest batch.
- [ ] Implement suite CRUD with environment and project validation.
- [ ] Refactor batch creation to accept a suite and create a new batch per invocation.
- [ ] Add suite routes and preserve batch list/detail routes.
- [ ] Run focused backend tests.

### Task 3: Frontend API Contract

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/tests/api-automation-batch-run-contract.test.mjs`

**Interfaces:**
- Produces `ApiAutomationScenarioSuite`.
- Produces create/list/update/delete/run suite client functions.

- [ ] Update contract tests to require suite types and CRUD/run client functions.
- [ ] Run the Node contract test and confirm it fails against the old one-off API.
- [ ] Add the minimal API client types and functions.
- [ ] Run the contract test and confirm it passes.

### Task 4: Reusable Suite List UI

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-batch-run-list.tsx`
- Test: `apps/frontend/tests/api-automation-batch-run-contract.test.mjs`

**Interfaces:**
- Consumes suite CRUD/run API client functions.
- Produces a scenario-list-style suite table and create/edit dialog.

- [ ] Add failing contract assertions for search, new suite, edit, run, delete, environment selection, and scenario uniqueness copy.
- [ ] Run the contract test and confirm failures.
- [ ] Replace direct scenario selection with suite list state and loading.
- [ ] Add create/edit dialog with one environment and unique scenario multi-selection.
- [ ] Add row actions for edit, run, and delete.
- [ ] Show latest batch result and report link without restoring the old recent-batches section.
- [ ] Run contract tests and targeted Biome checks.

### Task 5: Regression Verification

**Files:**
- Verify: `apps/backend/tests/test_api_automation_batch_runs.py`
- Verify: `apps/backend/tests/test_report_center_service.py`
- Verify: `apps/frontend/tests/api-automation-batch-run-contract.test.mjs`
- Verify: `apps/frontend/tests/report-center-contract.test.mjs`

- [ ] Run focused backend batch and report tests.
- [ ] Run adjacent API automation backend tests.
- [ ] Run frontend contract tests.
- [ ] Run targeted Biome checks for touched frontend files.
- [ ] Run Python compile checks and `git diff --check`.
- [ ] Verify the suite list and report center in the local browser.
