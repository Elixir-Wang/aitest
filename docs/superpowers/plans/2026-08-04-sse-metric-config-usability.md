# SSE Metric Config Usability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve SSE metric configuration readability and make the ignore missing-policy behavior distinct from record-null.

**Architecture:** Keep the existing API schema and component structure. Add presentation helpers and accessible field labels in the frontend, then filter ignored missing metrics before measurements are persisted by the generated Locust runtime.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Python, pytest, Node test runner.

## Global Constraints

- Preserve all existing SSE configuration field names and enum values.
- Do not overwrite unrelated uncommitted changes.
- Reuse the existing contract tests and SSE runtime tests.
- Do not add dependencies or introduce a new component abstraction.

---

### Task 1: Add failing usability contracts

**Files:**
- Modify: `apps/frontend/tests/performance-testing-contract.test.mjs`
- Modify: `apps/backend/tests/test_performance_sse.py`

**Interfaces:**
- Consumes: Existing component source contract and generated Locust script.
- Produces: Assertions for field labels, user-facing policy copy, sample evidence placement, and ignore-policy filtering.

- [ ] Add frontend source assertions for `高级匹配规则`, all visible labels, and new missing-policy copy.
- [ ] Add backend renderer assertion that ignored metrics are excluded from reported missing IDs.
- [ ] Run both focused tests and confirm they fail for the intended missing behavior.

### Task 2: Improve metric-card information hierarchy

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-sse-metrics-config.tsx`

**Interfaces:**
- Consumes: `PerformanceSseMetric` and validation evidence already available in the component.
- Produces: Business-readable condition summary and accessible advanced controls.

- [ ] Add a concise match-summary formatter.
- [ ] Replace the raw rule line with a labeled trigger-condition block.
- [ ] Rename the details section and add labels linked to every control.
- [ ] Move sample JSON into an independent `查看命中事件` details section.
- [ ] Replace ambiguous missing-policy option text and add explanatory copy.
- [ ] Run the frontend contract test and confirm it passes.

### Task 3: Implement true ignore semantics

**Files:**
- Modify: `apps/backend/app/services/performance_testing/script_renderer.py`
- Test: `apps/backend/tests/test_performance_sse.py`

**Interfaces:**
- Consumes: Existing `missing_policy` values in generated runtime config.
- Produces: `missing_metric_ids` containing only `record_null` and `fail_request` misses.

- [ ] Keep a complete internal list of unmatched metrics.
- [ ] Derive reportable missing IDs by excluding metrics with `missing_policy == "ignore"`.
- [ ] Derive request-failing IDs from unmatched metrics with `missing_policy == "fail_request"`.
- [ ] Persist only reportable missing IDs in the measurement payload.
- [ ] Run focused backend tests and confirm they pass.

### Task 4: Verify the complete change

**Files:**
- Verify only; no planned modifications.

**Interfaces:**
- Consumes: Completed frontend and backend changes.
- Produces: Fresh test and formatting evidence.

- [ ] Run the frontend performance contract test.
- [ ] Run the backend SSE test module.
- [ ] Run Biome check on the modified frontend files.
- [ ] Review the final diff for unrelated changes.
