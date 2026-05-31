# Site Exploration Realtime Stream AgentPlan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed exploration-detail polling with a realtime SSE stream, and render backend-produced module/page progress through the existing `AgentPlan` component.

**Architecture:** Keep the existing detail API as the authoritative snapshot. Add a lightweight in-process exploration event bus and an SSE endpoint scoped by `run_id`. The exploration orchestrator publishes structured run/module/page/action/blocker events while it writes DB/YAML facts. The frontend loads the initial detail snapshot, subscribes to the SSE stream, incrementally merges events into local state, and maps modules/pages into `AgentPlan` tasks/subtasks. Actions and elements remain page details, not primary tree nodes.

**Tech Stack:** FastAPI, Python threading/queue, SQLite services, existing Playwright runner/orchestrator, Next.js App Router, React, `motion/react`, shadcn/ui, Biome.

---

## File Map

- Create: `apps/backend/app/services/exploration_event_bus.py`
  - Owns per-run subscribers, event publishing, timeout heartbeats, and cleanup.
- Modify: `apps/backend/app/api/v1/exploration.py`
  - Adds `GET /projects/{project_id}/exploration-runs/{run_id}/stream` SSE endpoint.
- Modify: `apps/backend/app/schemas/exploration.py`
  - Adds typed realtime event payload schemas if needed by route tests and docs.
- Modify: `apps/backend/app/services/site_exploration_orchestrator.py`
  - Publishes lifecycle, module, page, blocker, and finish events.
- Modify: `apps/backend/app/services/exploration_service.py`
  - Optionally adds permission-safe stream snapshot helpers if the route needs them.
- Modify: `apps/backend/tests/test_exploration_api.py`
  - Covers stream authorization and SSE response framing.
- Modify: `apps/backend/tests/test_site_exploration_orchestrator.py`
  - Covers event publishing around run start, blocked finish, completed finish, and cancellation.
- Modify: `apps/frontend/src/components/ui/agent-plan.tsx`
  - Keep reusable component API; only adjust if current props cannot express module/page metadata.
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - Removes fixed polling for exploration overview, subscribes to SSE, maps detail modules/pages to `AgentPlan`.
- Modify: `apps/frontend/src/lib/api-client.ts`
  - Adds stream URL helper if current API helper style supports endpoint centralization.

---

## Task 1: Backend Event Bus

**Files:**
- Create: `apps/backend/app/services/exploration_event_bus.py`
- Test: focused unit tests can live in `apps/backend/tests/test_exploration_api.py` or a new `test_exploration_event_bus.py`

- [ ] **Step 1: Add event bus tests**

Cover:

- subscribers receive events published for the same `run_id`
- subscribers do not receive events for other runs
- unsubscribe cleanup removes stale queues
- events are JSON-serializable dictionaries with `type`, `run_id`, and `payload`

- [ ] **Step 2: Implement in-process event bus**

Implement a small service with:

```python
subscribe(run_id: str) -> Iterator[dict]
publish(run_id: str, event_type: str, payload: dict) -> None
close(run_id: str) -> None
```

Use `queue.Queue` and a lock-protected `dict[str, set[Queue]]`. Keep it intentionally in-process for this phase.

- [ ] **Step 3: Add heartbeat support**

If no event arrives within a short interval, the stream generator should emit a comment heartbeat such as:

```text
: keep-alive
```

This prevents proxy/client idle disconnects while exploration is running.

---

## Task 2: SSE API Endpoint

**Files:**
- Modify: `apps/backend/app/api/v1/exploration.py`
- Modify: `apps/backend/tests/test_exploration_api.py`

- [ ] **Step 1: Add route tests**

Cover:

- unauthenticated users cannot open the stream
- authorized users can open the stream for a visible run
- SSE output uses `text/event-stream`
- a published event is formatted as:

```text
event: page_discovered
data: {"type":"page_discovered",...}
```

- [ ] **Step 2: Implement stream route**

Add:

```http
GET /projects/{project_id}/exploration-runs/{run_id}/stream
```

The route must call the same authorization path as `get_project_run_detail` before subscribing.

- [ ] **Step 3: Format SSE events safely**

Serialize each event as compact JSON. Do not stream passwords, tokens, cookies, storage state, or raw secret fields.

- [ ] **Step 4: Close behavior**

When `run_completed`, `run_failed`, or `run_cancelled` is emitted, the stream may send the terminal event and then close. The frontend can reconnect only if the run is still active.

---

## Task 3: Orchestrator Event Publishing

**Files:**
- Modify: `apps/backend/app/services/site_exploration_orchestrator.py`
- Modify: `apps/backend/tests/test_site_exploration_orchestrator.py`

- [ ] **Step 1: Add publishing tests around existing run states**

Tests should verify that:

- queued -> running publishes `run_started`
- planned module seeding publishes `module_discovered` or `module_updated`
- blocked CLI result publishes `blocker_detected` and `run_failed`
- completed result publishes module/page updates and `run_completed`
- stopping publishes `run_cancelled`

- [ ] **Step 2: Publish lifecycle events**

Publish:

- `run_started` after DB status becomes `running`
- `run_failed` after blocked/failed state is persisted
- `run_completed` after completed state and outputs are persisted
- `run_cancelled` after cancelled state is persisted

- [ ] **Step 3: Publish module events from real data**

When planned modules are seeded or summary modules are persisted, publish real module records:

```json
{
  "module_id": "...",
  "module_name": "...",
  "planned_page_count": 0,
  "explored_page_count": 0,
  "completion_status": "running"
}
```

- [ ] **Step 4: Publish page events from real data**

When pages are discovered or persisted, publish:

- `page_discovered`
- `page_updated`
- `page_completed`
- `page_blocked`

Each event must include `module_id`, `page_id`, title, URL/path, status, and optional summary fields.

- [ ] **Step 5: Publish actions as detail-only events**

For action observations, publish `action_observed` linked to `module_id` and `page_id`. Do not make actions primary AgentPlan nodes.

---

## Task 4: Frontend Stream Subscription

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Optionally modify: `apps/frontend/src/lib/api-client.ts`

- [ ] **Step 1: Add stream state model**

Keep `ExplorationRunDetail` as the snapshot type. Add local state for the merged realtime detail:

```ts
const [streamDetail, setStreamDetail] = useState<ExplorationRunDetail | null>(null);
```

Initialize it from the detail snapshot.

- [ ] **Step 2: Add EventSource subscription**

Open the stream only for active statuses:

- `queued`
- `running`
- `waiting_human`
- `stopping`
- `in-progress`

Close it on unmount or terminal status.

- [ ] **Step 3: Merge events deterministically**

Implement pure merge helpers:

- `mergeModuleEvent(detail, event)`
- `mergePageEvent(detail, event)`
- `mergeBlockerEvent(detail, event)`
- `mergeRunEvent(detail, event)`

Rules:

- same ID updates existing row
- unknown module creates a module placeholder
- unknown page creates a page placeholder under its module
- terminal run events update `run.status`

- [ ] **Step 4: Handle reconnect**

On stream error:

- close current `EventSource`
- keep rendered state
- if run is still active, retry after a short backoff
- on reconnect, optionally reload detail snapshot once before resubscribing

---

## Task 5: AgentPlan Mapping

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Modify only if necessary: `apps/frontend/src/components/ui/agent-plan.tsx`

- [ ] **Step 1: Restore AgentPlan as the module progress UI**

Replace the temporary custom progress list with:

```tsx
<AgentPlan tasks={agentPlanTasks} emptyLabel="暂无探索模块" />
```

- [ ] **Step 2: Map modules to tasks**

Each module becomes an `AgentPlanTask`:

- `id`: module id
- `title`: module name
- `status`: normalized module status
- `description`: completion summary or entry path
- `meta`: page/action/field counts where useful

- [ ] **Step 3: Map pages to subtasks**

Each page becomes an `AgentPlanSubtask`:

- `id`: page id
- `title`: page title, URL, or entry path
- `status`: normalized page status
- `description`: structure summary, recent event, or blocker reason
- `meta`: page type, URL/path, YAML path

- [ ] **Step 4: Keep actions out of the primary tree**

Do not render action events as separate subtasks. Use them only to update page `description` or page detail metadata.

---

## Task 6: Remove Fixed Polling

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] **Step 1: Remove 3-second overview polling**

Remove the fixed interval refresh for the overview/detail path once SSE is active.

- [ ] **Step 2: Keep manual refresh**

The existing refresh button can remain as a snapshot reload and recovery action.

- [ ] **Step 3: Keep report/log lazy loading**

Report and log tabs can continue loading on tab activation unless separately moved to streams later.

---

## Task 7: Verification

**Backend checks:**

- [ ] Run focused backend tests:

```bash
cd apps/backend
python -m pytest tests/test_exploration_api.py tests/test_site_exploration_orchestrator.py -q
```

- [ ] Run any new event bus tests.

**Frontend checks:**

- [ ] Run Biome on changed frontend files:

```bash
cd apps/frontend
npm run check -- 'src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx' src/components/ui/agent-plan.tsx
```

**Manual smoke:**

- [ ] Start backend and frontend.
- [ ] Create or start an exploration run.
- [ ] Open the exploration detail page.
- [ ] Confirm modules appear without waiting for fixed polling.
- [ ] Confirm running module/page nodes animate in `AgentPlan`.
- [ ] Confirm terminal status closes or stops the stream.
- [ ] Disconnect/reconnect the browser and confirm snapshot recovery works.

---

## Implementation Notes

- Do not introduce `framer-motion`; this project already uses `motion/react`.
- Do not copy demo `initialTasks`; all `AgentPlan` data must come from backend `detail` or SSE events.
- Do not store secrets in stream events.
- Keep the in-process event bus small. If the app later runs multiple backend workers, replace it with Redis pub/sub without changing the frontend event contract.
