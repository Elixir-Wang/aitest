# Site Exploration Confirmed Plan Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a human-confirmed exploration plan flow so a run generates a bounded plan first, the user confirms or supplements it, and exploration starts from that confirmed plan.

**Architecture:** Store the first-version plan as `exploration-plan.yaml` under the run artifact root, alongside existing v2 exploration artifacts. Backend exposes generate, update, confirm, and start guards; frontend moves start actions into the `探索计划` Tab and labels execution as `按计划开始探索`.

**Tech Stack:** FastAPI, SQLite-backed run metadata, YAML artifact files, Next.js detail page, Node contract tests, pytest.

---

### Task 1: Backend Plan Artifact Contract

**Files:**
- Modify: `apps/backend/app/services/exploration/service.py`
- Modify: `apps/backend/app/schemas/exploration.py`
- Modify: `apps/backend/app/api/v1/exploration.py`
- Test: `apps/backend/tests/test_exploration_run_restart.py`

- [ ] Add plan schemas for `plan_status`, `items`, and plan item fields.
- [ ] Add service helpers that read/write `exploration-plan.yaml`.
- [ ] Generate plan items from the run boundary and standard capability taxonomy.
- [ ] Confirm the plan before starting exploration.
- [ ] Include the current plan in run detail responses.

### Task 2: Frontend Plan Tab Flow

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Test: `apps/frontend/tests/exploration-detail-contract.test.mjs`

- [ ] Remove the direct header `开始探索` button from the plan/overview actions.
- [ ] Add `生成探索计划`, `添加计划项`, `确认计划`, and `按计划开始探索` actions inside the `探索计划` Tab.
- [ ] Render plan status, item category, title, steps, expected evidence, risk level, and execution policy.
- [ ] Allow first-version manual supplementation by adding one plan item from a compact form.
- [ ] Disable `按计划开始探索` until a confirmed plan exists.

### Task 3: Verification

**Commands:**
- `cd apps/backend && uv run pytest tests/test_exploration_run_restart.py -q`
- `cd apps/frontend && node --test tests/exploration-detail-contract.test.mjs`
- `cd apps/frontend && npm run check -- 'src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx'`

