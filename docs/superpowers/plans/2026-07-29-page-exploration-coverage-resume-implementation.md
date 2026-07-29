# Page Exploration Coverage Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make exploration coverage visible and durable after every action, and make “继续探索” resume the saved Loop checkpoint instead of deleting and restarting it.

**Architecture:** Keep Schema 4.0 page YAML as discovered page facts, use project `exploration-coverage.yaml` as the authoritative completed/pending coverage ledger, and keep run `loop_state.json` as the resumable execution checkpoint. Expose a compact coverage summary through the existing page-exploration API and render it in the run detail UI.

**Tech Stack:** FastAPI, Python dataclasses, YAML/JSON file storage, React/Next.js, pytest, Node contract tests.

## Global Constraints

- Preserve high business coverage; do not replace traversal with sampling.
- Do not delete or overwrite unrelated existing workspace changes.
- Every started step must receive exactly one terminal event.
- Persist verified coverage immediately instead of waiting for normal Loop completion.
- “继续探索” preserves checkpoint; “重新探索” remains an explicit separate operation.
- Reuse Schema 4.0 page artifacts; do not introduce another page artifact schema.

---

### Task 1: Durable Per-Action Coverage

**Files:**
- Modify: `apps/backend/app/services/page_exploration/loop/service.py`
- Modify: `apps/backend/app/services/page_exploration/coverage_registry.py`
- Test: `apps/backend/tests/services/page_exploration/test_loop_service_runtime.py`
- Test: `apps/backend/tests/services/page_exploration/test_coverage_registry.py`

**Interfaces:**
- Produces: immediate `update_coverage(...)` calls after verified actions.
- Produces: compact `coverage_summary(coverage: dict) -> dict`.

- [ ] Write failing tests for immediate verified-action persistence and summary counts.
- [ ] Run focused tests and confirm failures.
- [ ] Implement minimal per-action persistence and summary calculation.
- [ ] Run focused tests and confirm passes.

### Task 2: Closed Step Lifecycle

**Files:**
- Modify: `apps/backend/app/services/page_exploration/loop/service.py`
- Test: `apps/backend/tests/services/page_exploration/test_loop_service_runtime.py`

**Interfaces:**
- Produces: terminal `step_skipped`, `step_blocked`, or `step_failed` for every early branch.

- [ ] Write failing tests for skip and blocked lifecycle closure.
- [ ] Run focused tests and confirm failures.
- [ ] Publish terminal events and plan updates before every early continue.
- [ ] Run focused tests and confirm passes.

### Task 3: Real Checkpoint Resume

**Files:**
- Modify: `apps/backend/app/services/page_exploration/loop/service.py`
- Modify: `apps/backend/app/services/page_exploration/service.py`
- Modify: `apps/backend/app/services/page_exploration/runner.py`
- Modify: `apps/backend/app/api/v1/page_exploration/runs.py`
- Test: `apps/backend/tests/services/page_exploration/test_loop_service_runtime.py`
- Test: `apps/backend/tests/test_page_exploration_service.py`

**Interfaces:**
- Produces: `resume: bool = False` run start option.
- Consumes: `load_checkpoint(run_dir)`.
- Preserves: run artifacts when resume is requested.

- [ ] Write failing service and Loop resume tests.
- [ ] Run focused tests and confirm failures.
- [ ] Load checkpoint, normalize executing items to pending, and continue from saved frontier.
- [ ] Split continue and restart behavior at the service/API boundary.
- [ ] Run focused tests and confirm passes.

### Task 4: Coverage API and UI

**Files:**
- Modify: `apps/backend/app/api/v1/page_exploration/pages.py`
- Modify: `apps/backend/app/services/page_exploration/service.py`
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Test: `apps/backend/tests/test_page_exploration_api.py`
- Test: `apps/frontend/tests/exploration-run-detail-contract.test.mjs`

**Interfaces:**
- Produces: `GET /page-exploration/projects/{project_id}/coverage`.
- Produces: summary and page/action status lists for the current project.

- [ ] Write failing API and frontend contract tests.
- [ ] Run focused tests and confirm failures.
- [ ] Add service/API response from project coverage plus resumable checkpoint metadata.
- [ ] Add coverage summary cards and completed/pending action groups to run detail.
- [ ] Run focused tests and confirm passes.

### Task 5: Schema 4.0 Report Accuracy

**Files:**
- Modify: `apps/backend/app/services/page_exploration/report_writer.py`
- Test: `apps/backend/tests/services/page_exploration/test_report_writer.py`

**Interfaces:**
- Consumes: top-level Schema 4.0 `elements` and `page.normalized_path`.

- [ ] Write failing report tests for element count, path, and no false empty message.
- [ ] Run focused tests and confirm failures.
- [ ] Adapt report rendering and quality warnings to Schema 4.0.
- [ ] Run focused tests and confirm passes.

### Task 6: Focused Regression Verification

**Files:**
- Verify only.

- [ ] Run page exploration Loop, coverage, report, API, and frontend contract tests.
- [ ] Run Python compile checks for changed backend modules.
- [ ] Run `git diff --check` for changed files.
- [ ] Review final diff without modifying unrelated workspace changes.
