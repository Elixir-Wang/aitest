# SSE Explicit Timing Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SSE metrics explicitly bind to the originating SSE interface and consistently calculate request-relative and event-to-event timings across generation, confirmation, runtime, aggregation, and display.

**Architecture:** Extend the existing `PerformanceSseMetric` contract with backward-compatible category and timing metadata. Reuse the current matcher and generated Locust runtime for base metrics, add one deterministic derived metric, and expose human-readable timing semantics through existing API rows and React confirmation UI.

**Tech Stack:** Python 3.13, Pydantic, Locust, pytest, React, TypeScript, Node contract tests.

## Global Constraints

- Preserve existing stored SSE configurations through defaults and normalization.
- Do not use scenario step 01 as the origin of step 02 SSE metrics.
- Reuse existing matcher, candidate generation, rendering, and statistics paths.
- Write a failing test before every behavior change.
- Do not modify the existing user-owned `apps/backend/data/ai_testing.db` change.

---

### Task 1: Timing Contract

**Files:**
- Modify: `apps/backend/app/schemas/performance_test.py`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Test: `apps/backend/tests/test_performance_sse.py`

**Interfaces:**
- Produces: `PerformanceSseMetric.category`, `PerformanceSseMetric.timing`, and request-relative defaults.

- [ ] Add failing schema tests for timing defaults and explicit source request IDs.
- [ ] Run `rtk pytest -q apps/backend/tests/test_performance_sse.py` and confirm failure.
- [ ] Add the minimal Pydantic timing models and TypeScript contract.
- [ ] Re-run the focused backend tests and confirm pass.

### Task 2: Candidate Generation And Confirmation

**Files:**
- Modify: `apps/backend/app/services/performance_testing/sse_metric_generation.py`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-sse-metrics-config.tsx`
- Test: `apps/backend/tests/test_performance_sse_metric_generation.py`
- Test: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Consumes: timing contract from Task 1.
- Produces: candidates and applied metrics carrying source request semantics.

- [ ] Add failing backend and frontend contract tests for source interface and formula metadata.
- [ ] Run focused Python and Node tests and confirm failure.
- [ ] Attach timing metadata to structural, AI, and custom candidates.
- [ ] Display and preserve timing metadata in the confirmation dialog.
- [ ] Re-run focused tests and confirm pass.

### Task 3: Runtime And Derived Timing

**Files:**
- Modify: `apps/backend/app/services/performance_testing/script_renderer.py`
- Modify: `apps/backend/app/services/performance_testing/headless_worker.py`
- Test: `apps/backend/tests/test_performance_sse.py`

**Interfaces:**
- Produces: `connection_ms`, request metadata, and `derived:llm_start_to_first_content` values.

- [ ] Add failing runtime tests for connection latency and derived timing.
- [ ] Run the focused test and confirm failure.
- [ ] Record response-header timing and calculate non-negative derived values.
- [ ] Aggregate `derived_metrics` with stable derived IDs.
- [ ] Re-run focused tests and confirm pass.

### Task 4: API And Result Presentation

**Files:**
- Modify: `apps/backend/app/api/v1/performance_runs.py`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/locust-console.tsx`
- Test: `apps/backend/tests/test_performance_run_api.py`
- Test: `apps/frontend/tests/performance-run-detail-contract.test.mjs`

**Interfaces:**
- Consumes: aggregated base and derived metrics.
- Produces: rows containing timing source and formula for display.

- [ ] Add failing API and frontend contract tests for source interface and formula.
- [ ] Run focused tests and confirm failure.
- [ ] Enrich SSE metric rows and render timing semantics.
- [ ] Re-run focused tests and confirm pass.

### Task 5: Regression Verification

**Files:**
- Verify: `apps/backend/tests/test_performance_sse.py`
- Verify: `apps/backend/tests/test_performance_sse_metric_generation.py`
- Verify: `apps/backend/tests/test_performance_run_api.py`
- Verify: `apps/frontend/tests/performance-testing-contract.test.mjs`
- Verify: `apps/frontend/tests/performance-run-detail-contract.test.mjs`

- [ ] Run all focused backend SSE tests.
- [ ] Run both frontend contract suites.
- [ ] Run backend formatting or lint checks already configured by the repository.
- [ ] Review `git diff` and confirm `apps/backend/data/ai_testing.db` remains untouched.
