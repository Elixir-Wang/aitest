# SSE Timing Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct SSE first-content timing, add paired LLM-to-content latency, clarify connection timing, and align counts during manual stop.

**Architecture:** Keep raw event timing in the generated Locust runtime. Extend measurement aggregation with one deterministic derived metric and let the run API attach display semantics and count bounds. The frontend remains a renderer of explicit backend metadata.

**Tech Stack:** Python, Locust, FastAPI, pytest, TypeScript, React, Node contract tests.

## Global Constraints

- Do not add an implicit `query_end` metric.
- Do not calculate paired latency by subtracting aggregate percentiles.
- Preserve existing user-configured metric IDs and goals.
- Do not weaken SSE failures or assertions.

---

### Task 1: First Non-Empty Content

**Files:**
- Modify: `apps/backend/app/services/performance_testing/sse_metric_generation.py`
- Test: `apps/backend/tests/test_performance_sse_metric_generation.py`

**Interfaces:**
- Consumes: discovered SSE event samples.
- Produces: first-content match `{source: data_json, path: $.data.answer, operator: non_empty}`.

- [ ] Add a failing test asserting generated first-content rules use `$.data.answer` with `non_empty`.
- [ ] Run `uv run pytest tests/test_performance_sse_metric_generation.py -q` and verify failure.
- [ ] Update deterministic generation/normalization to emit the confirmed rule.
- [ ] Re-run the test and verify pass.

### Task 2: Paired LLM Output Delta

**Files:**
- Modify: `apps/backend/app/services/performance_testing/script_renderer.py`
- Modify: `apps/backend/app/services/performance_testing/headless_worker.py`
- Test: `apps/backend/tests/test_performance_sse.py`

**Interfaces:**
- Consumes: per-request observed configured metrics.
- Produces: `derived_metrics.llm_start_to_first_content_ms` and aggregate metric `derived:llm_start_to_first_content`.

- [ ] Add failing runtime and aggregation tests using empty answer, `call_llm_start`, then non-empty answer.
- [ ] Verify tests fail because no derived metric exists and empty answer matches incorrectly.
- [ ] Calculate the paired delta only when both events exist in the same measurement.
- [ ] Aggregate the derived values with normal SSE percentiles.
- [ ] Re-run targeted tests and verify pass.

### Task 3: Display Semantics And Count Boundary

**Files:**
- Modify: `apps/backend/app/api/v1/performance_runs.py`
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/locust-console.tsx`
- Test: `apps/backend/tests/test_performance_run_api.py`
- Test: `apps/frontend/tests/performance-run-detail-contract.test.mjs`

**Interfaces:**
- Consumes: generated plan transport and completed HTTP SSE request count.
- Produces: request stat `timing_semantics=connection` and SSE metric attempts capped to completed HTTP requests.

- [ ] Add failing backend and frontend contract tests.
- [ ] Mark streaming request rows as connection latency.
- [ ] Cap SSE summary display counts to the completed SSE HTTP request count.
- [ ] Render a visible `建连耗时` label for streaming HTTP rows.
- [ ] Re-run backend and frontend tests.

### Task 4: Regenerate And Verify

**Files:**
- Update generated database script through `script_service.generate_script`.

**Interfaces:**
- Consumes: fixed generator and current `test1` configuration.
- Produces: validated script `perfscript-e0fe26f5630b566f`.

- [ ] Regenerate the current script.
- [ ] Verify first-content uses non-empty answer and no `query_end` metric exists.
- [ ] Run targeted backend/frontend regressions and TypeScript checks.
- [ ] Perform a single live SSE validation and inspect paired event ordering.
