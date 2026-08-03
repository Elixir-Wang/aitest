# Performance SSE AI Metric Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add endpoint-level SSE probing that generates and validates `call_llm_start` and `first_answer` metric rules, then let users review and apply them from the performance-test form.

**Architecture:** A new performance service executes the selected endpoint with streaming enabled, normalizes received SSE frames with client-side offsets, asks the existing performance AI model for a constrained rule suggestion, and deterministically validates the result with the existing SSE matcher. The frontend keeps the accepted configuration in the existing `request_config.sse` shape and uses one summary section plus one Dialog.

**Tech Stack:** FastAPI, Pydantic, requests, LangChain structured output, pytest, Next.js, React, TypeScript, Node contract tests.

## Global Constraints

- Reuse `PerformanceSseConfig`, `PerformanceSseMetric`, `PerformanceSseMatch`, and the existing Locust renderer.
- AI may only return declarative rules; it must not generate Python code.
- Formal elapsed time uses client-side `time.perf_counter()` offsets.
- Existing HTTP and scenario performance-test behavior must remain unchanged.
- Scenario targets do not expose endpoint-level metric generation in this first implementation.
- Existing uncommitted workspace changes must not be reverted or reformatted unnecessarily.

---

### Task 1: Backend probe and rule generation contract

**Files:**
- Modify: `apps/backend/app/schemas/performance_test.py`
- Create: `apps/backend/app/agents/performance_testing/sse_metric_generation.py`
- Create: `apps/backend/app/services/performance_testing/sse_metric_generation.py`
- Modify: `apps/backend/app/api/v1/performance_tests.py`
- Test: `apps/backend/tests/test_performance_sse_metric_generation.py`

**Interfaces:**
- Consumes: endpoint ID, environment ID, current unsaved request parameters, and maximum stream duration.
- Produces: `candidate_sse`, deterministic validation evidence, sample metadata, warnings, and generation source.

- [ ] Write failing schema and service tests for sample normalization, first-match evidence, multiple-answer handling, end-rule validation, and AI fallback.
- [ ] Run the focused backend test and confirm the new API/service symbols are missing.
- [ ] Add constrained input/output Pydantic models.
- [ ] Add SSE streaming capture using client-side offsets and bounded event/frame limits.
- [ ] Add structured AI suggestion with deterministic `event_type` fallback.
- [ ] Replay candidate rules through the existing matcher and reject missing required metrics.
- [ ] Add the authenticated performance API route.
- [ ] Run focused backend tests until green.

### Task 2: Frontend API contract and minimal metric editor

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Create: `apps/frontend/src/components/ai-testing/performance-testing/performance-sse-metrics-config.tsx`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-test-form.tsx`
- Modify: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Consumes: selected project, endpoint, environment, and current unsaved request parameters.
- Produces: a confirmed `PerformanceSseConfig` passed to the existing create-performance-test payload.

- [ ] Add failing contract assertions for the generation API, summary section, Dialog, evidence display, revalidation state, and overwrite protection.
- [ ] Run the frontend contract test and confirm it fails for missing UI/API symbols.
- [ ] Add API client types and generation function.
- [ ] Add one component containing the summary section and Dialog.
- [ ] Support generation, evidence display, advanced rule edits, local replay validation, cancel, apply, and regenerate confirmation.
- [ ] Replace the form's hard-coded OpenAI-style SSE defaults with the confirmed generated configuration while preserving manual fallback.
- [ ] Run the frontend contract test until green.

### Task 3: Integration and regression verification

**Files:**
- Verify all files changed in Tasks 1 and 2.

**Interfaces:**
- Consumes: saved `request_config.sse`.
- Produces: unchanged Locust script generation with generated rules embedded in the existing plan.

- [ ] Run focused backend SSE, script-generation, and performance API tests.
- [ ] Run frontend performance contract tests.
- [ ] Run backend formatting/static checks available in the repository for changed files.
- [ ] Run frontend type checking or build validation available in the repository.
- [ ] Review `git diff --check` and confirm unrelated workspace changes were not modified.
