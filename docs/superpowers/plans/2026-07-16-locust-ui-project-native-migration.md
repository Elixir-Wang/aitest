# Locust UI Project-Native Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the standalone Locust Web UI flow with a project-owned Chinese run page while retaining Locust execution and statistics.

**Architecture:** FastAPI remains the control plane. A dedicated performance Worker runs Locust without its Web UI, persists run state and sampled statistics, and exposes project APIs. The React frontend renders Overview, Statistics, Charts, Failures, Exceptions, logs, and reports from those APIs.

**Tech Stack:** FastAPI, SQLite repositories, Python Locust 2.45.0, React/Next.js, existing project UI components, SSE with polling fallback.

## Global Constraints

- Keep Locust pinned at `2.45.0`.
- Do not start or proxy Locust Web UI for the new flow.
- Do not run long-lived Locust work inside the FastAPI event loop.
- Preserve existing confirmed-script, endpoint, environment, and project-permission rules.
- Keep existing user modifications in unrelated files intact.
- Use the project's current UI components and Chinese copy conventions.

---

### Task 1: Define persistent run and statistics contracts

**Files:**
- Inspect: `apps/backend/app/core/db.py`
- Inspect: `apps/backend/app/repositories/performance_testing_repo.py`
- Create or modify: `apps/backend/app/repositories/performance_run_repo.py`
- Create or modify: `apps/backend/app/schemas/performance_run.py`
- Test: `apps/backend/tests/test_performance_run_repo.py`

**Interfaces:**
- Produce `create_run`, `get_run`, `update_run_status`, `append_stats`, `upsert_failure`, `upsert_exception`, and `list_events` repository functions.
- Use statuses `created`, `starting`, `running`, `stopping`, `completed`, `stopped`, `failed`, and `cancelled`.
- Persist `run_id`, project/test/script IDs, load/runtime configuration, timestamps, error code/message, latest summary, stats samples, failures, exceptions, and events.

- [ ] Write failing repository tests for run creation, legal status transitions, stats persistence, failure aggregation, exception aggregation, and event ordering.
- [ ] Run `pytest tests/test_performance_run_repo.py -q` and confirm the tests fail because the repository contract is absent.
- [ ] Add the smallest repository/schema implementation following existing SQLite repository patterns.
- [ ] Run the same test file and confirm all tests pass.

### Task 2: Build the headless Locust Worker boundary

**Files:**
- Create: `apps/backend/app/services/performance_testing/headless_worker.py`
- Modify: `apps/backend/app/services/performance_testing/runner.py`
- Modify: `apps/backend/app/services/performance_testing/locust_session.py`
- Test: `apps/backend/tests/test_headless_worker.py`

**Interfaces:**
- Produce `start_headless_run(run_id, run_dir, runtime_payload, load_config)`, `stop_headless_run(run_id)`, and `collect_run_result(run_id)`.
- Worker must run outside the FastAPI request handler, use `Environment`/Runner or an equivalent headless Locust invocation, and never create a Web UI port.
- Worker events must update the repository contracts from Task 1.

- [ ] Write failing tests for headless startup, status updates, failure capture, stop behavior, and report paths.
- [ ] Run `pytest tests/test_headless_worker.py -q` and confirm failure before implementation.
- [ ] Implement a worker adapter that loads the existing generated script and runtime configuration, starts Locust headlessly, captures logs, and writes state/events.
- [ ] Implement graceful stop followed by bounded force cleanup without relying on `active_sessions.json` as the source of truth.
- [ ] Run the worker tests and existing `tests/test_locust_session.py`.

### Task 3: Add project performance-run APIs

**Files:**
- Modify: `apps/backend/app/api/v1/performance_runs.py`
- Modify: `apps/backend/app/services/performance_testing/service.py`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Test: `apps/backend/tests/test_performance_run_api.py`
- Test: `apps/frontend/tests/performance-run-api-contract.test.mjs`

**Interfaces:**
- Add `POST /projects/{project_id}/performance-tests/{test_id}/runs` returning immediately with `{id, status}`.
- Add `GET /projects/{project_id}/performance-test-runs/{run_id}`.
- Add `GET /projects/{project_id}/performance-test-runs/{run_id}/stats`.
- Add `GET /projects/{project_id}/performance-test-runs/{run_id}/events` as SSE with polling fallback support.
- Add `POST /projects/{project_id}/performance-test-runs/{run_id}/stop`.
- Add `POST /projects/{project_id}/performance-test-runs/{run_id}/reset-stats`.
- Add report list/download endpoints with project permission checks.

- [ ] Write failing API tests for immediate run creation, permission denial, status reads, stop idempotency, reset behavior, SSE event shape, and protected report downloads.
- [ ] Run the backend and frontend contract tests to verify the missing endpoints fail.
- [ ] Implement API handlers using the existing script/environment validation path and Task 1/2 interfaces.
- [ ] Ensure all failures return structured `code`, `message`, and `trace_id` values.
- [ ] Run the API tests and existing performance API tests.

### Task 4: Implement the project-native run page

**Files:**
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/performance-tests/[testId]/runs/[runId]/page.tsx`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-run-detail.tsx`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-run-overview.tsx`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-run-statistics.tsx`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-run-charts.tsx`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-run-failures.tsx`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-run-exceptions.tsx`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-detail.tsx`
- Test: `apps/frontend/tests/performance-run-detail-contract.test.mjs`

**Interfaces:**
- Consume Task 3 API client functions and render Chinese project-native UI.
- Render controls, overview, Statistics, Charts, Failures, Exceptions, logs, and reports.
- Disable controls from server status, not only local loading state.

- [ ] Write failing source/component contract tests for route wiring, Chinese labels, status controls, statistics sections, charts, failures, exceptions, report downloads, and absence of `window.open`/Locust UI session calls.
- [ ] Run the frontend contract test and confirm failure before components exist.
- [ ] Implement the page using existing `ShellSection`, table, tabs, chart, button, badge, and toast patterns.
- [ ] Implement SSE subscription with one-second polling fallback and cleanup on unmount.
- [ ] Replace the current direct Locust UI launch action with navigation to the project-native run page.
- [ ] Run the targeted frontend tests and a production type/build check if available.

### Task 5: Migrate reports, logs, and remove the old UI dependency

**Files:**
- Modify: `apps/backend/app/services/performance_testing/headless_worker.py`
- Modify: `apps/backend/app/api/v1/performance_runs.py`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-run-detail.tsx`
- Test: `apps/backend/tests/test_performance_run_reports.py`
- Test: `apps/frontend/tests/performance-run-reports-contract.test.mjs`

**Interfaces:**
- Reports expose only files owned by the run directory after permission validation.
- Logs expose structured event records and bounded raw log attachments.
- New runs never create `locust-ui-session`, Web UI ports, or browser popups.

- [ ] Write failing tests for report generation, report listing, path traversal rejection, redacted log output, and old UI endpoint non-use.
- [ ] Run the tests and confirm the expected failures.
- [ ] Implement report persistence/download and sensitive-value redaction.
- [ ] Remove the new-flow dependency on `active_sessions.json`, retaining only compatibility cleanup for old runs.
- [ ] Run all targeted backend/frontend tests, `git diff --check`, and the relevant build/type commands.

## Final Verification

- Run `pytest` for all new performance-run and worker tests.
- Run existing performance script and API tests.
- Run all new frontend contract tests.
- Verify no new code references `window.open(session.url)`, `createLocustUiSession`, or Locust UI proxy routes.
- Verify a run creates no Locust Web UI listening port.
- Verify a run survives a frontend refresh and its final report remains downloadable.
- Review the final diff without touching unrelated user changes.
