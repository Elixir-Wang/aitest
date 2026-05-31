# Site Exploration AgentPlan Page Status Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or an equivalent task-by-task workflow. Keep the patch narrow. Do not remove page-level status from `AgentPlan`.

**Goal:** Fix the inconsistent exploration overview state where a module is shown as `已完成` while its explored page is shown as `待探索`.

**Architecture:** Backend remains the status authority for the detail API. Page artifact facts may keep `status: explored`, but the detail API must return an `AgentPlan` display status such as `completed`. Frontend adds a compatibility fallback for historical or stale responses that still contain `explored`.

**Primary Spec:** `docs/superpowers/specs/2026-05-30-site-exploration-agent-plan-page-status-normalization-spec.md`

---

## File Map

- Modify: `apps/backend/app/services/exploration_service.py`
  - Normalize page status at the detail API boundary.
  - Map `explored` to `completed`.
- Modify: `apps/backend/app/schemas/exploration.py`
  - Change API display default for `ExplorationPageOut.status` from `explored` to `completed`.
- Modify: `apps/backend/tests/test_exploration_service.py`
  - Add coverage for `explored -> completed` in run detail output.
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - Add frontend fallback mapping `explored -> completed`.
- Optional modify: `apps/backend/app/services/site_exploration_orchestrator.py`
  - Only if current detail output is produced there instead of `exploration_service.py`.
- Optional modify: `apps/backend/tests/test_site_exploration_orchestrator.py`
  - Only if orchestrator status publishing needs explicit regression coverage.
- Optional modify: `apps/frontend/src/components/ui/agent-plan.tsx`
  - Only if status normalization is moved into the shared component.

---

## Design Decisions

- Keep page-level status visible.
- Do not delete the inner status badge from `AgentPlan`.
- Do not infer page completion in the frontend from `steps`, `yaml_path`, `structure_summary`, or module status.
- Preserve `explored` in page YAML and internal artifact facts.
- Expose only display-contract statuses from detail API.
- Treat frontend `explored` support as backward compatibility, not the primary fix.

---

## Task 1: Locate Detail Page Assembly

**Files:**
- `apps/backend/app/services/exploration_service.py`
- `apps/backend/app/repositories/exploration_repo.py`
- `apps/backend/app/services/site_exploration_orchestrator.py`

- [ ] Find the code path used by:

```http
GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/detail
```

- [ ] Identify where `ExplorationPageOut.status` is populated.
- [ ] Confirm whether page status comes from DB rows, page YAML, or orchestrator payloads.
- [ ] Do not change persistence logic during this task.

Acceptance:

- You can point to the exact line where detail response page status is assigned.
- You know whether existing tests construct status from DB fixtures or artifact fixtures.

---

## Task 2: Add Backend Status Normalizer

**Files:**
- `apps/backend/app/services/exploration_service.py`

- [ ] Add a small helper near other detail response normalization helpers:

```python
AGENT_PLAN_DISPLAY_STATUSES = {
    "pending",
    "queued",
    "running",
    "in-progress",
    "stopping",
    "completed",
    "partial",
    "blocked",
    "waiting_human",
    "failed",
    "cancelled",
}


def normalize_page_display_status(status: str | None) -> str:
    normalized = str(status or "").strip()
    if normalized == "explored":
        return "completed"
    if normalized in AGENT_PLAN_DISPLAY_STATUSES:
        return normalized
    return "pending"
```

- [ ] Keep this helper private unless existing service style prefers exported helpers.
- [ ] Do not normalize module `completion_status` with this helper.

Acceptance:

- `normalize_page_display_status("explored") == "completed"`.
- `normalize_page_display_status("blocked") == "blocked"`.
- `normalize_page_display_status(None) == "pending"`.

---

## Task 3: Apply Normalizer to Detail Output

**Files:**
- `apps/backend/app/services/exploration_service.py`

- [ ] Wrap the page status assigned to `ExplorationPageOut` or equivalent dict:

```python
status=normalize_page_display_status(page_status)
```

- [ ] If pages are returned as dicts, normalize before returning the detail DTO.
- [ ] Do not mutate loaded YAML content in place unless that object is only a response DTO.
- [ ] Preserve `steps`, `recent_event`, `blocker_reason`, `yaml_path`, and `structure_summary` unchanged.

Acceptance:

- Detail API returns `completed` for pages whose stored or artifact status is `explored`.
- Detail API still returns `blocked` for blocked pages.
- Existing page steps still appear.

---

## Task 4: Adjust API Schema Default

**Files:**
- `apps/backend/app/schemas/exploration.py`

- [ ] Change `ExplorationPageOut.status` default from:

```python
status: str = "explored"
```

to:

```python
status: str = "completed"
```

- [ ] Leave step default statuses unchanged.
- [ ] Do not change runner page artifact defaults in this task.

Acceptance:

- API schema defaults no longer expose `explored` as the default display value.
- Old page YAML without explicit status still remains loadable.

---

## Task 5: Add Backend Regression Tests

**Files:**
- `apps/backend/tests/test_exploration_service.py`

- [ ] Add a test named:

```python
test_run_detail_normalizes_explored_page_status_to_completed
```

- [ ] Use the existing test setup style in this file.
- [ ] Create or reuse a run detail fixture with a page status of `explored`.
- [ ] Assert the detail response page status is `completed`.
- [ ] Assert a blocked page remains `blocked` if an easy fixture path exists.
- [ ] Assert page `steps` are preserved if the test fixture includes steps.

Acceptance:

- The new test fails before Tasks 2-3.
- The new test passes after Tasks 2-3.
- No existing exploration service tests regress.

---

## Task 6: Add Frontend Compatibility Mapping

**Files:**
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] In `normalizeAgentPlanStatus`, add:

```ts
if (status === "explored") {
  return "completed";
}
```

- [ ] Add it before the final `return "pending"`.
- [ ] Do not map unknown statuses to completed.
- [ ] Do not infer completion from page steps or module status.

Acceptance:

- Historical API payloads with `page.status = "explored"` display page status as `已完成`.
- Unknown statuses still display as `待探索`.

---

## Task 7: Verify Realtime/Refresh Consistency

**Files:**
- `apps/backend/app/services/site_exploration_orchestrator.py`
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Confirm current `page_completed` SSE event emits `status: completed`.
- [ ] Confirm detail snapshot after refresh emits `status: completed` for explored pages.
- [ ] Do not change SSE event shape unless it emits `explored` in any page event used by the frontend.

Acceptance:

- During realtime updates, page shows `已完成`.
- After browser refresh, the same page still shows `已完成`.
- No flicker back to `待探索` after snapshot reload.

---

## Task 8: Run Verification

**Backend commands:**

Run focused tests first:

```bash
cd apps/backend
uv run pytest tests/test_exploration_service.py
```

If orchestrator was touched:

```bash
cd apps/backend
uv run pytest tests/test_site_exploration_orchestrator.py
```

**Frontend commands:**

Run focused lint:

```bash
cd apps/frontend
npm run lint -- src/app/\(main\)/projects/\[projectId\]/exploration/\[runId\]/page.tsx
```

Optional manual verification:

- Open a completed exploration run with page artifact status `explored`.
- Confirm module badge shows `已完成`.
- Expand the module.
- Confirm page badge shows `已完成`.
- Confirm page steps remain visible.
- Refresh the browser.
- Confirm the page badge still shows `已完成`.

---

## Completion Criteria

- Backend detail API does not expose `explored` as `pages[].status`.
- Frontend can still tolerate `explored` from historical/stale payloads.
- Page-level status remains visible in `AgentPlan`.
- Module/page/step structure remains unchanged.
- Tests or focused lint pass.
- No historical YAML files are rewritten.

---

## Rollback Plan

If the backend normalization causes an unexpected consumer issue:

- Keep the frontend compatibility mapping.
- Revert only the detail API status normalization.
- Add a follow-up API field such as `raw_status` or `artifact_status` for consumers that truly require `explored`.

Do not remove page-level status as a rollback unless the product spec is changed first.
