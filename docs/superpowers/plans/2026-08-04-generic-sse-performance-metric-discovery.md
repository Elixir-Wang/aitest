# Generic SSE Performance Metric Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed LLM SSE metric generation with evidence-based generic candidate discovery, deterministic replay validation, and recoverable frontend drafts.

**Architecture:** The backend first aggregates real SSE events into safe facts, then combines deterministic structural candidates with an AI ranking that may only reference those facts. The API returns candidates and validation evidence; the frontend lets users select and edit candidates before converting them into the existing `PerformanceSseConfig`, preserving the current Locust runtime contract.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, Next.js/React, TypeScript, Node contract tests.

## Global Constraints

- Do not require `call_llm_start`, `first_answer`, `answer`, or `query_end`.
- AI may return zero through eight candidates.
- AI may reference only server-generated event facts.
- Every selectable candidate must be replayed against the captured sample.
- Existing saved `PerformanceSseConfig` values and runtime behavior remain compatible.
- AI metadata must not be written into the formal runtime configuration.
- Closing the dialog must not discard an unapplied candidate draft.
- Do not modify unrelated existing workspace changes.
- Do not create commits unless the user explicitly requests them.

---

### Task 1: Generic Event Facts and Structural Candidates

**Files:**
- Modify: `apps/backend/app/services/performance_testing/sse_metric_generation.py`
- Test: `apps/backend/tests/test_performance_sse_metric_generation.py`

**Interfaces:**
- Produces: `extract_sse_event_facts(events: list[CapturedSseEvent]) -> list[dict[str, Any]]`
- Produces: `build_structural_sse_candidates(events: list[CapturedSseEvent], facts: list[dict[str, Any]]) -> list[dict[str, Any]]`
- Produces: stable fact fields used by the AI and API response.

- [ ] **Step 1: Write failing fact extraction tests**

Add tests proving that repeated enum values are aggregated, first/last offsets are retained, non-empty content is represented without exposing the full body, and high-cardinality random values are not promoted as equality facts.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
rtk pytest apps/backend/tests/test_performance_sse_metric_generation.py -q
```

Expected: new tests fail because fact extraction and structural candidate functions do not exist.

- [ ] **Step 3: Implement minimal event fact extraction**

Implement deterministic traversal of safe JSON scalar fields, aggregation by normalized event match signature, stable `fact_id` generation, content-presence metadata, and high-cardinality filtering.

- [ ] **Step 4: Write failing structural candidate tests**

Cover first non-empty output, terminal singleton events, start/end naming pairs, heartbeat exclusion, and an event stream with no recommendable candidate.

- [ ] **Step 5: Implement structural candidate generation**

Generate neutral candidates from facts without asserting unsupported business semantics. Return zero candidates when only protocol noise exists.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run the same pytest command and expect all tests in the module to pass.

### Task 2: AI Fact-Reference Contract and Candidate Merge

**Files:**
- Modify: `apps/backend/app/agents/performance_testing/sse_metric_generation.py`
- Modify: `apps/backend/app/services/performance_testing/sse_metric_generation.py`
- Test: `apps/backend/tests/test_performance_sse_metric_generation.py`

**Interfaces:**
- Produces: AI response containing zero through eight candidate suggestions referencing `fact_id`.
- Produces: `merge_sse_metric_candidates(...)` that rejects unknown facts and deduplicates identical match rules.
- Consumes: event facts from Task 1.

- [ ] **Step 1: Write failing AI contract tests**

Test zero candidates, one candidate, unknown `fact_id`, duplicate AI and structural rules, and AI exceptions.

- [ ] **Step 2: Run focused tests and verify RED**

Expected failures must show the old minimum-two fixed metric contract or missing fact validation.

- [ ] **Step 3: Replace the fixed AI schema and prompt**

Define generic categories, require `fact_id`, remove fixed metric names, and instruct the model that an empty candidate list is valid.

- [ ] **Step 4: Implement candidate merge and scoring**

Resolve each accepted `fact_id` to a server-owned `PerformanceSseMatch`, merge identical normalized rules, retain structural evidence, and cap output at eight candidates.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the backend generation test module and confirm the AI failure path still returns structural candidates or an event catalog without fixed metrics.

### Task 3: Generic Replay and Generation API Result

**Files:**
- Modify: `apps/backend/app/schemas/performance_test.py`
- Modify: `apps/backend/app/services/performance_testing/sse_metric_generation.py`
- Modify: `apps/backend/app/api/v1/performance_tests.py`
- Test: `apps/backend/tests/test_performance_sse_metric_generation.py`
- Test: relevant performance API test module if the endpoint response is asserted there.

**Interfaces:**
- Produces: generic candidate response with `sample_summary`, `event_facts`, `candidates`, `end_rule_candidate`, `analysis`, `result_status`, and `messages`.
- Keeps: candidate revalidation through existing `candidate_sse` input for edited formal drafts.
- Removes: overall validity dependency on `REQUIRED_METRIC_IDS`.

- [ ] **Step 1: Write failing replay and response tests**

Test one valid metric, arbitrary metric IDs, no candidate result, partial validation, and formal candidate revalidation without fixed IDs.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: old `REQUIRED_METRIC_IDS` behavior marks arbitrary valid metrics invalid.

- [ ] **Step 3: Generalize validation**

Set candidate validity from the candidate's own match result. For a formal selected configuration, require every selected metric and configured end rule to match.

- [ ] **Step 4: Build the new discovery response**

Return evidence-rich candidates while preserving a compatibility `candidate_sse` only when selected formal rules are being revalidated.

- [ ] **Step 5: Run backend generation and API tests**

Confirm the endpoint serializes generic candidates and historical formal configs still validate.

### Task 4: Frontend API Types and Candidate Conversion

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Produces: TypeScript types matching the Task 3 response.
- Produces: candidate-to-`PerformanceSseMetric` conversion inputs used by the UI.

- [ ] **Step 1: Write failing contract assertions**

Assert that generic candidate, fact, analysis, and result status fields exist and fixed generation-source-only handling is removed from the SSE result type.

- [ ] **Step 2: Run the frontend contract test and verify RED**

Run:

```powershell
rtk node --test apps/frontend/tests/performance-testing-contract.test.mjs
```

- [ ] **Step 3: Update API client types**

Model candidates, validation evidence, facts, analysis mode, optional formal revalidation response, and messages.

- [ ] **Step 4: Run the contract test and verify GREEN**

Confirm the Node contract test passes.

### Task 5: Candidate Selection and Recoverable Dialog Draft

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/performance-testing/performance-sse-metrics-config.tsx`
- Modify: `apps/frontend/tests/performance-testing-contract.test.mjs`

**Interfaces:**
- Consumes: generic discovery response from Task 4.
- Produces: existing `PerformanceSseConfig` through `onChange` only after selected candidates validate.

- [ ] **Step 1: Write failing frontend contract assertions**

Assert copy and state hooks for `查看生成结果`, `暂存并关闭`, pending validation, selected candidates, and success messaging without warning-loop Toasts.

- [ ] **Step 2: Run the frontend contract test and verify RED**

Expected: assertions fail against the current modal-only `candidate_sse` implementation.

- [ ] **Step 3: Implement candidate draft state**

Store discovery result, selected suggestion keys, editable formal draft, verification state, and request fingerprint independently from dialog visibility.

- [ ] **Step 4: Implement candidate list UI**

Show recommendation level, reason, uncertainty, sample sequence, elapsed time, hit count, event facts, and an add-as-custom action for non-recommended facts.

- [ ] **Step 5: Implement close and reopen behavior**

Closing the dialog retains the draft. The page-level primary action changes to `查看生成结果`, `继续编辑`, or `查看并应用` according to state.

- [ ] **Step 6: Implement revalidation and application**

Convert only selected candidates to formal metrics with stable backend-provided IDs, revalidate edited rules, and apply only when every selected metric and configured end rule passes.

- [ ] **Step 7: Run the frontend contract test and verify GREEN**

Confirm the updated contract assertions pass.

### Task 6: Regression Verification

**Files:**
- Test only unless a directly related regression is found.

**Interfaces:**
- Verifies all earlier tasks together.

- [ ] **Step 1: Run backend focused tests**

```powershell
rtk pytest apps/backend/tests/test_performance_sse_metric_generation.py apps/backend/tests/test_performance_sse.py -q
```

- [ ] **Step 2: Run frontend focused tests**

```powershell
rtk node --test apps/frontend/tests/performance-testing-contract.test.mjs
```

- [ ] **Step 3: Run backend formatting or lint checks configured by the repository**

Use only existing project commands from `apps/backend/pyproject.toml`; do not add a formatter.

- [ ] **Step 4: Run frontend type or lint checks configured by the repository**

Use only existing scripts from `apps/frontend/package.json`; do not modify unrelated failures.

- [ ] **Step 5: Review final diff**

Confirm no user-modified data files or generated project artifacts were changed, and verify the implementation matches every acceptance criterion in the approved design spec.
