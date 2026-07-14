# Performance Request Auto-Mock Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove performance-test request-source configuration, generate editable request values from OpenAPI schemas and examples, hide empty request sections, and treat the two cybertron headers as ordinary performance-test headers.

**Architecture:** Keep request generation centralized in the backend preview service. The frontend consumes one endpoint-derived preview and conditionally renders only populated request sections. Delete the unused source-case field from the new-project schema and contracts without a migration or compatibility layer.

**Tech Stack:** FastAPI, Pydantic, SQLite seed schema, Next.js, React, TypeScript, Node test runner, pytest.

## Global Constraints

- Do not preserve `source_api_test_case_id` in performance-test schemas, APIs, persistence, or UI.
- Do not create a database migration; this is a new project and the seed schema is the source of truth.
- Prefer OpenAPI examples, then defaults/enums, then schema-valid generated values.
- Generated request values remain editable.
- Do not modify unrelated API-automation authentication behavior.
- Do not create Git commits unless explicitly requested.

---

### Task 1: Remove Performance Source-Case Contracts

**Files:**
- Modify: `apps/backend/tests/test_performance_testing.py`
- Modify: `apps/backend/app/schemas/performance_test.py`
- Modify: `apps/backend/app/services/performance_testing/service.py`
- Modify: `apps/backend/app/repositories/performance_test_repo.py`
- Modify: `apps/backend/app/seed/schema.py`
- Modify: `apps/backend/tests/test_performance_integration.py`

**Interfaces:**
- Consumes: `PerformanceRequestPreviewIn(endpoint_id: str)`.
- Produces: performance create/update/output contracts without `source_api_test_case_id`.

- [ ] Replace the source-case merge test with a preview test that passes only `endpoint_id` and asserts OpenAPI-derived request data.
- [ ] Add schema assertions that `source_api_test_case_id` is rejected as an extra input field and absent from output serialization.
- [ ] Run `apps/backend/.venv/Scripts/python.exe -m pytest tests/test_performance_testing.py -q` from `apps/backend`; expect failures referencing the old field and merge behavior.
- [ ] Delete the field from Pydantic models, repository insert/serialization, validation parameters, service create/update flow, and SQLite seed schema.
- [ ] Update direct SQL test inserts to match the reduced table definition.
- [ ] Re-run the targeted backend test and expect it to pass.

### Task 2: Strengthen Schema Mocking and Header Rules

**Files:**
- Modify: `apps/backend/tests/test_performance_testing.py`
- Modify: `apps/backend/tests/test_performance_script_generation.py`
- Modify: `apps/backend/app/services/performance_testing/service.py`
- Modify: `apps/backend/app/services/performance_testing/plan_builder.py`
- Modify: `apps/backend/app/services/performance_testing/run_service.py`

**Interfaces:**
- Consumes: OpenAPI parameter and request-body schemas stored on API endpoints.
- Produces: editable `PerformanceRequestConfig` using example/default/enum/schema-valid fallback values.

- [ ] Add tests covering example, default, enum, constrained scalar, array, object, and optional-property behavior.
- [ ] Add a test asserting `cybertron-robot-key` and `cybertron-robot-token` appear in preview headers without warnings.
- [ ] Add a script-plan test asserting both headers survive plan construction.
- [ ] Run the targeted backend tests and verify the cybertron and schema cases fail first.
- [ ] Remove both cybertron names from performance-test sensitive-header sets and remove their runtime override path.
- [ ] Refine recursive schema value generation so explicit examples win, required object properties are populated, and generated scalar values respect common constraints.
- [ ] Re-run targeted tests and expect them to pass.

### Task 3: Simplify the Performance Form

**Files:**
- Modify: `apps/frontend/tests/performance-testing-contract.test.mjs`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-form.tsx`

**Interfaces:**
- Consumes: `previewPerformanceRequest(projectId, { endpoint_id })`.
- Produces: a form with editable, conditionally visible request sections.

- [ ] Add contract assertions that the form does not import/load API test cases, does not contain “请求数据来源”, and does not emit `source_api_test_case_id`.
- [ ] Add contract assertions for non-empty checks guarding Path, Query, Headers, and Request Body editors.
- [ ] Run `node --test tests/performance-testing-contract.test.mjs` from `apps/frontend`; expect failures against the current form.
- [ ] Remove test-case state, loading, filtering, change confirmation, payload fields, and TypeScript contract fields.
- [ ] Add small helpers that detect non-empty objects and meaningful body values, and render each JSON editor only when populated.
- [ ] Preserve user editing after preview generation and keep success status codes visible.
- [ ] Re-run the frontend contract test and expect it to pass.

### Task 4: Verify the Focused Slice

**Files:**
- Verify: `apps/backend/tests/test_performance_testing.py`
- Verify: `apps/backend/tests/test_performance_script_generation.py`
- Verify: `apps/backend/tests/test_performance_integration.py`
- Verify: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Consumes all previous task outputs.
- Produces a verified endpoint-only performance-test creation flow.

- [ ] Run focused backend performance tests with the existing virtual-environment Python.
- [ ] Run the frontend performance contract test.
- [ ] Run the repository-configured frontend type check or build if available.
- [ ] Run the repository-configured backend formatter/linter if available.
- [ ] Run `git diff --check` and inspect `git status --short` to confirm unrelated dirty files were not reverted.
