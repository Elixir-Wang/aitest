# Site Exploration Overview Realtime Stream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move exploration SSE execution information out of the plan tab and into the overview module progress area as a left/right module-tree plus realtime-stream layout.

**Architecture:** Keep the existing `/page-exploration/runs/{runId}/stream` data flow. Extend monitor events to retain optional payload, then reorganize the React rendering in the exploration detail page so the plan tab is static task information and the overview tab owns runtime progress.

**Tech Stack:** Next.js React client component, TypeScript, Tailwind, shadcn-style local UI components, Node contract tests.

---

### Task 1: Contract Test

**Files:**
- Modify: `apps/frontend/tests/exploration-detail-contract.test.mjs`

- [ ] Add assertions that the page source contains `ExplorationModuleProgressPanel`, `ExplorationRealtimeStreamPanel`, `ExplorationToolCallCard`, and `payload?: Record<string, unknown>`.
- [ ] Add assertions that `ExplorationTaskInfoPanel` takes only `run` and no longer renders `ExplorationRealtimeMonitor`.
- [ ] Run `node --test apps/frontend/tests/exploration-detail-contract.test.mjs` and confirm the new assertions fail before implementation.

### Task 2: Monitor Payload and Panels

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Extend `ExplorationMonitorEvent` with `payload?: Record<string, unknown>`.
- [ ] Update `monitorTimelineEvent` to pass through event payload.
- [ ] Replace the overview module progress inline block with `ExplorationModuleProgressPanel`.
- [ ] Change `ExplorationTaskInfoPanel` to accept only `run`.
- [ ] Remove `ExplorationRealtimeMonitor` from the plan tab.

### Task 3: Realtime Stream UI

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Add `ExplorationRealtimeStreamPanel`, `ExplorationEventCard`, `ExplorationToolCallCard`, `EventDetailRow`, and helper functions.
- [ ] Render tool-like events as collapsible cards and ordinary events as compact event cards.
- [ ] Keep running steps highlighted at the top of the right panel.
- [ ] Ensure the panel has bounded scrolling and stacks on narrow screens.

### Task 4: Verification

**Files:**
- Test: `apps/frontend/tests/exploration-detail-contract.test.mjs`

- [ ] Run `node --test apps/frontend/tests/exploration-detail-contract.test.mjs`.
- [ ] Run the relevant frontend test command from `apps/frontend/package.json` if available.
- [ ] Inspect `git diff` and confirm only the intended files changed.
