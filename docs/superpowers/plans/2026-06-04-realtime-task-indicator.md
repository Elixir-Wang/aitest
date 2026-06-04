# Realtime Task Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove continuous polling from the top task indicator and make exploration start/restart tasks appear immediately.

**Architecture:** Use one-time `/tasks/running` initialization, immediate frontend store updates for exploration start/stop actions, and a backend SSE stream for authoritative task state changes. The first implementation scope is exploration task lifecycle events only; other modules keep using existing task list APIs until their action matrix is confirmed.

**Tech Stack:** FastAPI `StreamingResponse`, in-memory Python subscriber bus, Next.js client components, Zustand store, EventSource, Biome, pytest.

---

## File Structure

- Modify `apps/backend/app/services/task_service.py`
  - Add helper functions that can serialize one task by source, expose active-status checks, and support event publishing without duplicating task shape logic.
- Create `apps/backend/app/services/task_event_bus.py`
  - Provide an in-memory pub/sub bus for normalized task events.
- Modify `apps/backend/app/api/v1/tasks.py`
  - Add `GET /tasks/stream` SSE endpoint.
- Modify `apps/backend/app/services/exploration/service.py`
  - Publish exploration task events when `/start` and `/stop` change lifecycle state.
- Modify `apps/backend/app/services/exploration/site_orchestrator.py`
  - Publish exploration task events when the runner transitions to running or terminal states.
- Modify `apps/backend/tests/test_task_service.py`
  - Add focused tests for task serialization and active/non-active event decisions.
- Create `apps/backend/tests/test_task_event_bus.py`
  - Test publish/subscribe and visibility filtering helpers.
- Modify `apps/frontend/src/stores/running-task-store.ts`
  - Add event-oriented helpers while preserving current API.
- Modify `apps/frontend/src/components/ai-testing/task-running-indicator.tsx`
  - Replace interval polling with one-time load plus EventSource subscription.
- Modify `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - Immediately update the top indicator after start/stop succeeds.

## Task 1: Backend Task Serialization Helpers

**Files:**
- Modify: `apps/backend/app/services/task_service.py`
- Test: `apps/backend/tests/test_task_service.py`

- [ ] **Step 1: Add failing tests for single task lookup and active status**

Append these tests to `apps/backend/tests/test_task_service.py`:

```python
def test_get_task_by_source_returns_normalized_exploration_task(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db)
        db.execute(
            """
            INSERT INTO project_environments (id, project_id, name, site_url, created_by)
            VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO exploration_runs (id, project_id, environment_id, title, status, result_summary, created_by)
            VALUES ('run-1', 'project-1', 'env-1', '首页探索', 'queued', '探索任务已提交，等待执行。', 'u-admin')
            """
        )

    task = task_service.get_task_by_source(ACTOR, source_type="exploration_run", source_id="run-1")

    assert task is not None
    assert task["id"] == "exploration:run-1"
    assert task["status"] == "queued"
    assert task["status_group"] == "running"
    assert task["status_label"] == "排队中"
    assert task["detail_url"] == "/projects/project-1/exploration/run-1"


def test_is_active_task_status_matches_running_indicator_contract() -> None:
    assert task_service.is_active_task_status("exploration_run", "queued") is True
    assert task_service.is_active_task_status("exploration_run", "running") is True
    assert task_service.is_active_task_status("exploration_run", "stopping") is True
    assert task_service.is_active_task_status("exploration_run", "pending") is False
    assert task_service.is_active_task_status("exploration_run", "completed") is False
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_task_service.py -q
```

Expected: fail with missing `get_task_by_source` and `is_active_task_status`.

- [ ] **Step 3: Implement task helpers**

In `apps/backend/app/services/task_service.py`, add:

```python
STATUS_META_BY_SOURCE_TYPE = {
    "exploration_run": EXPLORATION_STATUS,
    "knowledge_build": KNOWLEDGE_STATUS,
    "requirement_file": REQUIREMENT_FILE_STATUS,
    "requirement_merge": REQUIREMENT_MERGE_STATUS,
}


def is_active_task_status(source_type: str, status: str) -> bool:
    status_meta = STATUS_META_BY_SOURCE_TYPE.get(source_type)
    if not status_meta:
        return False
    status_group, _label = status_meta.get(status, (status, status))
    return status_group in RUNNING_GROUPS


def get_task_by_source(actor, *, source_type: str, source_id: str) -> dict | None:
    tasks = _collect_visible_tasks(actor)
    for task in tasks:
        if task["source_type"] == source_type and task["source_id"] == source_id:
            return task
    return None
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_task_service.py -q
```

Expected: all tests in `test_task_service.py` pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add apps/backend/app/services/task_service.py apps/backend/tests/test_task_service.py
git commit -m "test: add task serialization helpers"
```

## Task 2: Backend Task Event Bus

**Files:**
- Create: `apps/backend/app/services/task_event_bus.py`
- Test: `apps/backend/tests/test_task_event_bus.py`

- [ ] **Step 1: Write tests for publish and subscribe**

Create `apps/backend/tests/test_task_event_bus.py`:

```python
from app.services import task_event_bus


def test_publish_sends_event_to_subscriber() -> None:
    subscriber = task_event_bus.subscribe()
    try:
        task_event_bus.publish({"type": "task_updated", "task": {"id": "exploration:run-1"}})
        event = next(subscriber)
    finally:
        subscriber.close()

    assert event == {"type": "task_updated", "task": {"id": "exploration:run-1"}}


def test_publish_task_removed_event() -> None:
    subscriber = task_event_bus.subscribe()
    try:
        task_event_bus.publish_task_removed("exploration:run-1")
        event = next(subscriber)
    finally:
        subscriber.close()

    assert event == {"type": "task_removed", "task_id": "exploration:run-1"}
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_task_event_bus.py -q
```

Expected: fail because `task_event_bus` does not exist.

- [ ] **Step 3: Implement event bus**

Create `apps/backend/app/services/task_event_bus.py`:

```python
from collections.abc import Iterator
from contextlib import suppress
from queue import Queue
from threading import Lock
from typing import Any

TaskEvent = dict[str, Any]

_subscribers: set[Queue[TaskEvent]] = set()
_lock = Lock()


def publish(event: TaskEvent) -> None:
    with _lock:
        subscribers = list(_subscribers)
    for subscriber in subscribers:
        subscriber.put(event)


def publish_task_updated(task: dict) -> None:
    publish({"type": "task_updated", "task": task})


def publish_task_removed(task_id: str) -> None:
    publish({"type": "task_removed", "task_id": task_id})


def subscribe() -> Iterator[TaskEvent]:
    queue: Queue[TaskEvent] = Queue()
    with _lock:
        _subscribers.add(queue)
    try:
        while True:
            yield queue.get()
    finally:
        with suppress(KeyError):
            with _lock:
                _subscribers.remove(queue)
```

- [ ] **Step 4: Run event bus tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_task_event_bus.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add apps/backend/app/services/task_event_bus.py apps/backend/tests/test_task_event_bus.py
git commit -m "feat: add task event bus"
```

## Task 3: Task SSE Endpoint

**Files:**
- Modify: `apps/backend/app/api/v1/tasks.py`
- Test: `apps/backend/tests/test_task_event_bus.py`

- [ ] **Step 1: Add event formatting test**

Append to `apps/backend/tests/test_task_event_bus.py`:

```python
from app.api.v1.tasks import format_sse_event


def test_format_sse_event_uses_json_event_payload() -> None:
    event = {"type": "task_updated", "task": {"id": "exploration:run-1", "title": "首页探索"}}

    payload = format_sse_event(event)

    assert payload.startswith("event: task_updated\n")
    assert '"id":"exploration:run-1"' in payload
    assert payload.endswith("\n\n")
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_task_event_bus.py -q
```

Expected: fail because `format_sse_event` does not exist.

- [ ] **Step 3: Add stream endpoint**

Modify `apps/backend/app/api/v1/tasks.py`:

```python
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.dependencies.auth import current_user
from app.services import task_event_bus, task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/running")
def list_running_tasks(project_id: str | None = Query(default=None), actor=Depends(current_user)) -> list[dict]:
    return task_service.list_running_tasks(actor, project_id=project_id)


@router.get("/stream")
def stream_tasks(actor=Depends(current_user)) -> StreamingResponse:
    def event_stream():
        for event in task_event_bus.subscribe():
            if _event_visible_to_actor(event, actor):
                yield format_sse_event(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def format_sse_event(event: dict) -> str:
    event_type = str(event.get("type") or "message")
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_type}\ndata: {data}\n\n"


def _event_visible_to_actor(event: dict, actor) -> bool:
    task = event.get("task")
    if isinstance(task, dict):
        project_id = task.get("project_id")
        if not project_id:
            return True
        return task_service.actor_can_see_project(actor, project_id)
    return True
```

Keep the existing `list_tasks(...)` endpoint below this block if it already exists in the file.

- [ ] **Step 4: Add actor visibility helper**

In `apps/backend/app/services/task_service.py`, add:

```python
def actor_can_see_project(actor, project_id: str) -> bool:
    with connect() as db:
        project_names = _visible_project_names(db, actor)
    return project_id in project_names
```

- [ ] **Step 5: Run backend tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_task_service.py tests/test_task_event_bus.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add apps/backend/app/api/v1/tasks.py apps/backend/app/services/task_service.py apps/backend/tests/test_task_event_bus.py
git commit -m "feat: stream task events"
```

## Task 4: Publish Exploration Task Events

**Files:**
- Modify: `apps/backend/app/services/exploration/service.py`
- Modify: `apps/backend/app/services/exploration/site_orchestrator.py`
- Test: `apps/backend/tests/test_task_service.py`

- [ ] **Step 1: Add a helper for publishing active or removed exploration task**

In `apps/backend/app/services/exploration/service.py`, import:

```python
from app.services import task_event_bus, task_service
```

Add:

```python
def _publish_exploration_task_event(actor, run_id: str, status: str) -> None:
    task_id = f"exploration:{run_id}"
    if not task_service.is_active_task_status("exploration_run", status):
        task_event_bus.publish_task_removed(task_id)
        return
    task = task_service.get_task_by_source(actor, source_type="exploration_run", source_id=run_id)
    if task:
        task_event_bus.publish_task_updated(task)
```

- [ ] **Step 2: Publish after start and stop**

In `start_project_run(...)`, after operation log recording and before `return result`, add:

```python
    _publish_exploration_task_event(actor, run_id, result["status"])
```

In `stop_project_run(...)`, after operation log handling and before returning the result, add:

```python
    _publish_exploration_task_event(actor, run_id, result["status"])
```

- [ ] **Step 3: Add orchestrator publish helper**

In `apps/backend/app/services/exploration/site_orchestrator.py`, import:

```python
from app.services import task_event_bus, task_service
```

Add:

```python
def _publish_task_event_from_run(run) -> None:
    task_id = f"exploration:{run['id']}"
    if not task_service.is_active_task_status("exploration_run", run["status"]):
        task_event_bus.publish_task_removed(task_id)
        return
    actor = {"id": run["created_by"], "role": "admin", "project_scope": "全部项目"}
    task = task_service.get_task_by_source(actor, source_type="exploration_run", source_id=run["id"])
    if task:
        task_event_bus.publish_task_updated(task)
```

- [ ] **Step 4: Call orchestrator helper after status changes**

Call `_publish_task_event_from_run(run)` after the orchestrator reloads a run following each state transition:

- after the run is updated to `running`;
- after terminal updates to `completed`, `partial`, `blocked`, or `cancelled`.

If the code path currently holds an older `run` row, reload it with `exploration_repo.find_by_id(db, run_id)` before publishing.

- [ ] **Step 5: Run backend tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_task_service.py tests/test_task_event_bus.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add apps/backend/app/services/exploration/service.py apps/backend/app/services/exploration/site_orchestrator.py
git commit -m "feat: publish exploration task events"
```

## Task 5: Frontend Store Event Helpers

**Files:**
- Modify: `apps/frontend/src/stores/running-task-store.ts`

- [ ] **Step 1: Extend store with source clearing helper**

Modify `apps/frontend/src/stores/running-task-store.ts`:

```ts
interface RunningTaskState {
  tasks: RunningTaskItem[];
  upsertTask: (task: RunningTaskItem) => void;
  removeTask: (taskId: string) => void;
  clearTasksBySource: (source: string) => void;
  replaceTasksBySource: (source: string, tasks: RunningTaskItem[]) => void;
}
```

Add implementation:

```ts
  clearTasksBySource: (source) =>
    set((state) => ({
      tasks: state.tasks.filter((item) => !item.id.startsWith(sourcePrefix(source))),
    })),
```

- [ ] **Step 2: Run focused frontend check**

Run:

```powershell
cd apps/frontend
npx biome check src/stores/running-task-store.ts
```

Expected: pass.

- [ ] **Step 3: Commit**

Run:

```powershell
git add apps/frontend/src/stores/running-task-store.ts
git commit -m "feat: add running task store helpers"
```

## Task 6: Replace Indicator Polling With SSE

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/task-running-indicator.tsx`

- [ ] **Step 1: Add event types and converter**

In `task-running-indicator.tsx`, add:

```ts
type ApiTaskEvent =
  | { type: "task_updated"; task: ApiTaskItem }
  | { type: "task_removed"; task_id: string };
```

Keep `toRunningTask(item)` as the conversion function for both initial load and SSE updates.

- [ ] **Step 2: Remove the interval**

Replace:

```ts
  useEffect(() => {
    void loadRunningTasks();
    const timer = window.setInterval(() => {
      void loadRunningTasks();
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(timer);
    };
  }, [loadRunningTasks]);
```

with:

```ts
  useEffect(() => {
    void loadRunningTasks();
  }, [loadRunningTasks]);
```

Remove `POLL_INTERVAL_MS`.

- [ ] **Step 3: Add EventSource subscription**

Add store access:

```ts
  const upsertTask = useRunningTaskStore((state) => state.upsertTask);
  const removeTask = useRunningTaskStore((state) => state.removeTask);
```

Add effect:

```ts
  useEffect(() => {
    if (!hasAuthHydrated || !hasProjectHydrated || !token) {
      return;
    }

    const source = new EventSource(`${API_BASE_URL}/tasks/stream`);

    source.addEventListener("task_updated", (event) => {
      const payload = JSON.parse(event.data) as ApiTaskEvent;
      if (payload.type === "task_updated") {
        upsertTask(toRunningTask(payload.task));
        setError("");
      }
    });

    source.addEventListener("task_removed", (event) => {
      const payload = JSON.parse(event.data) as ApiTaskEvent;
      if (payload.type === "task_removed") {
        removeTask(`backend:${payload.task_id}`);
        setError("");
      }
    });

    source.onerror = () => {
      setError("任务状态同步中断，请刷新后重试。");
    };

    return () => {
      source.close();
    };
  }, [hasAuthHydrated, hasProjectHydrated, removeTask, token, upsertTask]);
```

Import `API_BASE_URL` from `@/lib/api-client`; it is already exported by `apps/frontend/src/lib/api-client.ts`.

- [ ] **Step 4: Confirm no interval remains**

Run:

```powershell
rg -n "setInterval|POLL_INTERVAL_MS" apps/frontend/src/components/ai-testing/task-running-indicator.tsx
```

Expected: no matches.

- [ ] **Step 5: Run focused frontend check**

Run:

```powershell
cd apps/frontend
npx biome check src/components/ai-testing/task-running-indicator.tsx src/lib/api-client.ts
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add apps/frontend/src/components/ai-testing/task-running-indicator.tsx apps/frontend/src/lib/api-client.ts
git commit -m "feat: subscribe task indicator to events"
```

## Task 7: Immediate Exploration Start And Stop Updates

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] **Step 1: Import task store helpers**

Add imports:

```ts
import { createRunningTaskId, useRunningTaskStore } from "@/stores/running-task-store";
```

The exploration detail page currently does not import `createRunningTaskId`; add it with `useRunningTaskStore` in the same import.

- [ ] **Step 2: Add conversion helper**

Add near other exploration helpers:

```ts
const EXPLORATION_TASK_SOURCE = "backend";
const ACTIVE_EXPLORATION_STATUSES = new Set(["queued", "running", "waiting_human", "stopping"]);

function toExplorationRunningTask(run: ExplorationRun) {
  return {
    id: createRunningTaskId(EXPLORATION_TASK_SOURCE, `exploration:${run.id}`),
    projectId: run.project_id,
    projectName: run.project_name,
    title: run.title,
    moduleLabel: "站点探索",
    status: run.status,
    statusLabel: statusLabels[run.status] ?? run.status,
    updatedAt: run.updated_at,
  };
}
```

- [ ] **Step 3: Wire store in component**

Inside the page component, add:

```ts
  const upsertRunningTask = useRunningTaskStore((state) => state.upsertTask);
  const removeRunningTask = useRunningTaskStore((state) => state.removeTask);
```

- [ ] **Step 4: Update start flow immediately**

After `setRun(updated)` in `startExploration()`, add:

```ts
      upsertRunningTask(toExplorationRunningTask(updated));
```

- [ ] **Step 5: Update stop flow immediately**

After `setRun(updated)` in `stopExploration()`, add:

```ts
      if (ACTIVE_EXPLORATION_STATUSES.has(updated.status)) {
        upsertRunningTask(toExplorationRunningTask(updated));
      } else {
        removeRunningTask(createRunningTaskId(EXPLORATION_TASK_SOURCE, `exploration:${updated.id}`));
      }
```

- [ ] **Step 6: Run focused frontend check**

Run:

```powershell
cd apps/frontend
npx biome check 'src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx'
```

Expected: pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add 'apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx'
git commit -m "feat: show exploration task immediately"
```

## Task 8: Verification

**Files:**
- Verify touched backend and frontend files.

- [ ] **Step 1: Run backend targeted tests**

Run:

```powershell
cd apps/backend
uv run pytest tests/test_task_service.py tests/test_task_event_bus.py -q
```

Expected: pass.

- [ ] **Step 2: Run frontend targeted checks**

Run:

```powershell
cd apps/frontend
npx biome check src/stores/running-task-store.ts src/components/ai-testing/task-running-indicator.tsx src/lib/api-client.ts 'src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx'
```

Expected: pass.

- [ ] **Step 3: Confirm polling is removed**

Run:

```powershell
rg -n "setInterval|POLL_INTERVAL_MS" apps/frontend/src/components/ai-testing/task-running-indicator.tsx
```

Expected: no matches.

- [ ] **Step 4: Browser smoke test**

Start backend and frontend if needed:

```powershell
cd apps/backend
uv run uvicorn app.main:app --reload --port 8000
```

```powershell
cd apps/frontend
npm run dev
```

In the browser:

- Open an exploration detail page with a pending or completed run.
- Click `开始探索` or `重新探索`.
- Confirm the top task indicator appears immediately.
- Confirm the indicator status changes through SSE without waiting for a 15-second poll.
- Create a new exploration task from the list and confirm the top indicator does not appear just from creation.

- [ ] **Step 5: Final commit if verification fixes were needed**

Run only if Task 8 required additional code changes:

```powershell
git add apps/backend apps/frontend
git commit -m "fix: verify realtime task indicator"
```

## Self-Review

Spec coverage:

- Polling removal is covered by Task 6 and Task 8.
- Immediate exploration start/stop display is covered by Task 7.
- Backend SSE stream is covered by Task 2 and Task 3.
- Exploration lifecycle event publishing is covered by Task 4.
- "Create exploration task does not show top indicator" is preserved by leaving list creation flow out of Task 7 and verifying it in Task 8.

Placeholder scan:

- No implementation steps contain TBD, TODO, or unspecified "handle later" work.
- The non-exploration action matrix remains intentionally outside implementation scope for this first plan.

Type consistency:

- Backend task ids remain API ids such as `exploration:run-1`.
- Frontend store ids for backend tasks remain prefixed as `backend:exploration:run-1`.
- Event payload `task_updated.task` uses the existing `ApiTaskItem` shape.
