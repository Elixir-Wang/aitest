# Realtime Task Indicator Design

## Goal

Remove the top task indicator's 15-second polling loop and make running background tasks appear immediately after a real task-start action succeeds.

## Problem

The current top task indicator periodically requests `/tasks/running`. This creates delayed feedback: a task that has already been submitted may not appear until the next poll. It also blurs user expectations because some UI actions create business records, while other actions start background execution.

The indicator must not treat every "create" action as a running task. It should only represent active task lifecycles: queued, running, waiting for human action, or stopping.

## Product Rule

A UI action enters the top task indicator only when it starts or changes a background execution lifecycle.

Actions that only create or edit business records must not appear in the top task indicator.

## Initial Action Matrix

| Module | Action | Show In Top Indicator | Reason |
| --- | --- | --- | --- |
| Project | Create project | No | Creates a business record only. |
| Exploration | Create exploration task | No | Saves a pending exploration configuration. |
| Exploration | Start exploration | Yes | Submits a Playwright exploration run. |
| Exploration | Restart exploration | Yes | Clears previous outputs and submits a new run. |
| Exploration | Stop exploration | Update existing task | Moves an existing active run to stopping or cancelled. |
| Requirement | Upload requirement files | Yes | Triggers file conversion work. |
| Requirement | AI analysis | Yes | Starts AI-backed document processing. |
| Requirement | Requirement merge | Yes | Starts requirement merge processing. |
| Requirement | Save Markdown edit | No | Saves content only. |
| Knowledge | Upload knowledge file | Needs decision | Show only if upload triggers background build or parsing. |
| Knowledge | Generate knowledge base | Yes | Starts background knowledge build. |
| Test Case | Create test case | No | Creates a business record only. |
| Automation | Execute automation | Yes | Starts an automation run. |

## Architecture

Use a local-immediate plus server-event-confirmed model.

On initial app load, the top indicator requests `/tasks/running` once to recover active tasks after refresh. It does not start a repeating timer.

When a frontend action successfully calls a task-starting endpoint, the page immediately updates the shared running-task store. This makes the indicator appear without waiting for the backend stream.

The backend exposes a global task SSE endpoint. As task statuses change, the backend publishes task events. The top indicator consumes those events to correct optimistic local state, update labels, and remove tasks when they leave the active lifecycle.

## Frontend Design

`apps/frontend/src/stores/running-task-store.ts` remains the single source for top-indicator state.

Add a small event-oriented API to the store:

- `upsertTask(task)` for task started or task updated.
- `removeTask(taskId)` for task completed, cancelled, failed, or no longer visible.
- `replaceTasksBySource(source, tasks)` for one-time initialization from `/tasks/running`.

`apps/frontend/src/components/ai-testing/task-running-indicator.tsx` changes from polling to event subscription:

- Hydrate auth and project context.
- Request `/tasks/running` once after hydration.
- Open an EventSource connection to `/tasks/stream`.
- Apply task events into the running-task store.
- Reconnect through the browser's EventSource behavior.
- Show a concise sync-error state if the stream fails.
- Do not create a 15-second interval.

Task-starting pages update the store immediately after successful start endpoints:

- Exploration detail `startExploration()` adds the updated `queued` run immediately.
- Exploration detail `stopExploration()` updates or removes the run based on returned status.
- Exploration list `saveExplorationRun()` does not add pending tasks to the indicator.

## Backend Design

Add a task event bus, for example `apps/backend/app/services/task_event_bus.py`.

The event bus publishes normalized task events:

```json
{
  "type": "task_updated",
  "task": {
    "id": "exploration:explore-abc",
    "source_type": "exploration_run",
    "source_id": "explore-abc",
    "project_id": "project-1",
    "project_name": "示例项目",
    "module": "exploration",
    "module_label": "站点探索",
    "title": "首页探索",
    "status": "queued",
    "status_label": "排队中",
    "status_group": "running",
    "summary": "探索任务已提交，等待执行。",
    "updated_at": "2026-06-04 10:00:00",
    "detail_url": "/projects/project-1/exploration/explore-abc"
  }
}
```

When a task exits the active lifecycle, publish:

```json
{
  "type": "task_removed",
  "task_id": "exploration:explore-abc"
}
```

Add `/api/v1/tasks/stream`.

The stream must respect current user visibility. It should only emit events for projects the current actor can see. If filtering cannot be enforced at publish time, filter per subscriber before yielding the SSE message.

## Exploration First Scope

The first implementation should wire this for exploration runs only.

Publish `task_updated` when:

- `/start` changes a run to `queued`.
- The orchestrator changes a run to `running`.
- `/stop` changes a run to `stopping`.

Publish `task_removed` or a final non-active update when:

- A run becomes `completed`.
- A run becomes `partial`.
- A run becomes `blocked`.
- A run becomes `cancelled`.

The top indicator should hide when no active tasks remain.

## Error Handling

If the initial `/tasks/running` request fails, show the current "task status sync failed" state.

If the SSE stream disconnects, keep the current visible tasks and show a subtle sync-error state. Do not start polling as a fallback unless the product explicitly accepts degraded periodic sync.

If a frontend optimistic task is later contradicted by an SSE event, the SSE event wins.

If a user changes the global project context, the top indicator should clear backend-sourced tasks and reload `/tasks/running` once for the new scope, then reconnect the stream with the new scope.

## Testing

Backend tests:

- `/tasks/running` still returns active tasks visible to the actor.
- `/tasks/stream` emits task events only for visible projects.
- Exploration `/start` publishes an active task update.
- Exploration completion publishes task removal or a final non-active event.

Frontend tests:

- The indicator does not call `setInterval`.
- Initial load requests `/tasks/running` once.
- A simulated `task_updated` event makes the indicator visible.
- A simulated `task_removed` event hides it when no tasks remain.
- Creating an exploration task does not show the indicator.
- Starting an exploration task shows the indicator immediately.

## Open Decisions

The action matrix is the main review item. The product owner should confirm which non-exploration actions are true task-start actions before they are wired into the global task stream.

Knowledge upload needs a specific decision: if upload merely stores a file, it should not enter the indicator; if upload triggers parsing or build work, it should.

## Implementation Order

1. Add the backend task event bus and stream endpoint.
2. Publish exploration task events from start, run, stop, and terminal state transitions.
3. Replace frontend polling with one-time initialization plus SSE subscription.
4. Add immediate store updates in exploration start and stop flows.
5. Verify exploration behavior end to end.
6. Extend the same event model to requirement, knowledge, and automation tasks after the action matrix is confirmed.
