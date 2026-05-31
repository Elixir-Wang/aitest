# Site Exploration AgentPlan Backend/Frontend Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or an equivalent task-by-task workflow. Keep changes small, verify each layer, and do not invent frontend-only exploration facts.

**Goal:** Implement the AgentPlan exploration display contract so backend-produced page exploration steps are available in the detail API and realtime stream, and the frontend renders them inside the existing `AgentPlan` without module/page count meta such as `5/5 页`.

**Architecture:** Backend remains the fact producer. Runner and orchestrator produce page-level exploration steps, artifact service persists them in page YAML, detail service returns `pages[].steps`, and SSE emits `step_recorded` increments. Frontend loads the detail snapshot, subscribes to the existing stream, merges module/page/step events, and maps modules/pages/steps into `AgentPlan`. Actions, elements, edges, and blockers stay inside page expanded details.

**Primary Spec:** `docs/superpowers/specs/2026-05-30-site-exploration-agent-plan-backend-frontend-contract-spec.md`

---

## File Map

- Modify: `apps/backend/app/schemas/exploration.py`
  - Add `ExplorationStepOut`.
  - Add `steps` to `ExplorationPageOut`.
- Modify: `apps/backend/runners/playwright/site-explorer.mjs`
  - Emit page-level `steps` in each structured page artifact.
  - Keep existing `log_lines` / `run.log` behavior.
- Modify: `apps/backend/app/services/exploration_artifact_service.py`
  - Persist `steps` inside `pages/*.yaml`.
  - Read old page YAML safely when `steps` is absent.
- Modify: `apps/backend/app/services/exploration_service.py`
  - Return `steps` in `get_project_run_detail`.
  - Derive minimal compatible steps only from real artifacts/logs when runner steps are absent.
- Modify: `apps/backend/app/services/site_exploration_orchestrator.py`
  - Publish `step_recorded` events.
  - Include `steps` in page events when available.
- Modify: `apps/backend/tests/test_exploration_artifact_service.py`
  - Cover page YAML step persistence.
- Modify: `apps/backend/tests/test_exploration_service.py`
  - Cover detail API `pages[].steps`.
- Modify: `apps/backend/tests/test_site_exploration_orchestrator.py`
  - Cover `step_recorded` publishing.
- Modify: `apps/frontend/src/components/ui/agent-plan.tsx`
  - Add subtask step rendering.
  - Support `stopping` and `waiting_human` display if needed.
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - Add page `steps` to local detail type.
  - Merge `step_recorded`.
  - Remove module/page count meta from `AgentPlan`.
- Modify: `apps/frontend/src/lib/api-client.ts`
  - Add shared step types if this file is the current DTO source.

---

## Design Decisions

- `AgentPlan` remains the only exploration overview tree.
- Tree depth remains two primary levels: module -> page.
- Steps render only when a page subtask is expanded.
- Module and page right side show status only.
- Do not render `planned_page_count`, `explored_page_count`, action count, or field count as visible AgentPlan meta.
- Backend must provide steps; frontend must not fabricate them.
- `recent_event` remains a summary fallback, not a replacement for `steps`.
- Old runs without steps must keep working with `steps: []`.

---

## Task 1: Backend Schema Contract

**Files:**
- `apps/backend/app/schemas/exploration.py`

- [ ] Add `ExplorationStepOut`.

Expected shape:

```python
class ExplorationStepOut(BaseModel):
    id: str
    type: str
    title: str
    detail: str = ""
    status: str = "completed"
    occurred_at: str | None = None
    artifact_path: str = ""
    source: str = ""
```

- [ ] Add `steps: list[ExplorationStepOut] = []` to `ExplorationPageOut`.
- [ ] Keep defaults backward compatible.
- [ ] Run backend schema/import tests.

---

## Task 2: Runner Step Production

**Files:**
- `apps/backend/runners/playwright/site-explorer.mjs`

- [ ] Add a small step builder helper.

Step IDs should be stable per page within a run:

```js
step-001
step-002
step-003
```

- [ ] Add page-level steps for:
  - page visit
  - accessibility/DOM snapshot
  - element/action discovery
  - edge creation
  - skipped forbidden paths
  - blocker
  - page artifact completion
- [ ] Attach `steps` to each `pageDoc`.
- [ ] Keep `logEvent(...)` in place so `run.log` remains the audit source.
- [ ] Do not add screenshot, trace, video, or raw HTML dependencies.

Minimal page artifact target:

```json
{
  "page": {},
  "steps": [
    {
      "id": "step-001",
      "type": "visit",
      "title": "进入页面",
      "detail": "访问 https://example.test/users",
      "status": "completed",
      "source": "runner"
    }
  ],
  "accessibility_tree": [],
  "actions": [],
  "relations": {}
}
```

---

## Task 3: Artifact Persistence

**Files:**
- `apps/backend/app/services/exploration_artifact_service.py`
- `apps/backend/tests/test_exploration_artifact_service.py`

- [ ] Add test: writing page artifacts with `steps` persists them to `pages/*.yaml`.
- [ ] Add test: reading old page artifacts without `steps` returns no exception.
- [ ] Ensure `_build_page_payloads` preserves `steps`.
- [ ] Ensure `load_exploration_run_artifacts` returns page content including `steps`.

Acceptance:

- New YAML page files contain `steps`.
- Existing YAML page files without `steps` still load.

---

## Task 4: Detail API Steps

**Files:**
- `apps/backend/app/services/exploration_service.py`
- `apps/backend/tests/test_exploration_service.py`

- [ ] Add test: `get_project_run_detail` returns `pages[].steps`.
- [ ] Add test: old page YAML without steps returns `steps: []`.
- [ ] In `_load_run_artifacts`, read `content.get("steps", [])`.
- [ ] Normalize every step to the schema fields.
- [ ] Do not synthesize fake browser actions.

Allowed fallback:

- If `steps` is absent but `recent_event` exists from real data, return one summary-like step only if it is explicitly sourced from persisted artifact/log data.
- Otherwise return an empty list.

---

## Task 5: Orchestrator Step Events

**Files:**
- `apps/backend/app/services/site_exploration_orchestrator.py`
- `apps/backend/tests/test_site_exploration_orchestrator.py`

- [ ] Add `_publish_step_event(run_id, module_key, page_id, step)`.
- [ ] Publish `step_recorded` for each real page step after page artifacts are accepted.
- [ ] Include `steps` in `_publish_page_event` payload when the page payload has them.
- [ ] Ensure terminal event is still published after DB/artifact persistence.
- [ ] Ensure `exploration_event_bus.close(run_id)` still happens after terminal events.

Event shape:

```json
{
  "type": "step_recorded",
  "run_id": "explore-123",
  "payload": {
    "module_key": "user",
    "page_id": "page-001",
    "step": {
      "id": "step-001",
      "type": "visit",
      "title": "进入页面",
      "detail": "访问 /users",
      "status": "completed",
      "source": "runner"
    }
  }
}
```

---

## Task 6: AgentPlan Component

**Files:**
- `apps/frontend/src/components/ui/agent-plan.tsx`

- [ ] Add `AgentPlanStep` type.
- [ ] Add `steps?: AgentPlanStep[]` to `AgentPlanSubtask`.
- [ ] Render steps inside expanded subtask details.
- [ ] Keep rendering compact; no table.
- [ ] Add status labels/styles for `stopping` and `waiting_human` if the component accepts them directly.
- [ ] Keep status icon behavior deterministic:
  - `queued`, `running`, `in-progress`, `stopping` animate.
  - `completed`, `partial`, `blocked`, `failed`, `cancelled`, `waiting_human` are static.

Rendering target:

```text
页面标题                              已完成
  进入页面：访问 /users
  采集页面结构
  识别动作：发现“新增用户”按钮
```

---

## Task 7: Frontend Detail Type and Mapping

**Files:**
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Optional: `apps/frontend/src/lib/api-client.ts`

- [ ] Add `steps` to page detail type.
- [ ] Add `ExplorationStep` frontend type.
- [ ] Update `buildAgentPlanTasks`.
- [ ] Remove module meta entries:
  - `${module.explored_page_count}/${module.planned_page_count || "?"} 页`
  - `${module.action_count} 动作`
  - `${module.field_count} 字段`
- [ ] Ensure module/page right side only shows status.
- [ ] Map page `steps` into `AgentPlanSubtask.steps`.
- [ ] Keep page `description` as `recent_event || structure_summary || blocker_reason || ""`.

Important display rule:

```ts
meta: []
```

or omit `meta` entirely for module nodes unless there is a non-count, high-signal status reason.

---

## Task 8: Frontend SSE Step Merge

**Files:**
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Add `step_recorded` branch to `applyStreamEvent`.
- [ ] Implement `mergeStepEvent(detail, event)`.
- [ ] Locate target page by `module_key/module_id` and `page_id`.
- [ ] If page exists, append or update step by ID.
- [ ] If page does not exist, do not invent a page unless the event includes enough page identity and current merge policy already allows placeholders.
- [ ] Deduplicate by `step.id`.
- [ ] On stream close, call silent detail reload as current code already does.

Merge rule:

```ts
same step id -> replace
new step id -> append
missing step id -> ignore
```

---

## Task 9: Page Copy Cleanup

**Files:**
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Change exploration overview copy from:

```text
展示模块、页面进度和最近页面
```

to:

```text
展示模块、页面状态和页面探索步骤
```

- [ ] Ensure no visible text in the AgentPlan area says `页面进度`, `5/5 页`, `动作`, or `字段` as primary progress meta.

---

## Task 10: Verification

### Backend

Run focused tests from `apps/backend`:

```bash
python -m pytest \
  tests/test_exploration_artifact_service.py \
  tests/test_exploration_service.py \
  tests/test_site_exploration_orchestrator.py \
  tests/test_exploration_event_bus.py \
  -q
```

### Frontend

Run the available frontend checks from `apps/frontend`. Prefer project scripts:

```bash
pnpm lint
pnpm typecheck
```

If scripts differ, inspect `package.json` and run the matching checks.

### Manual UI Verification

- Open an exploration run detail page.
- Confirm `AgentPlan` renders module -> page.
- Confirm module right side only shows status.
- Confirm page right side only shows status.
- Expand a page and confirm steps are visible.
- Start a new run and confirm steps append through SSE.
- Refresh after completion and confirm steps are restored from detail API.
- Confirm old runs without steps still render without errors.

---

## Rollout Notes

- This is a backward-compatible API expansion.
- Old runs return `steps: []`.
- Frontend must tolerate missing `steps`.
- Do not remove `recent_event`; keep it as a summary fallback.
- Do not change the exploration report tab behavior.
- Do not change YAML fact-source ownership.

---

## Definition of Done

- Backend detail API returns page steps.
- SSE can push `step_recorded`.
- Frontend merges `step_recorded` deterministically.
- `AgentPlan` displays module/page statuses and page steps.
- Count meta such as `5/5 页`, action count, and field count is gone from the AgentPlan overview.
- Focused backend and frontend checks pass, or failures are documented with exact causes.
