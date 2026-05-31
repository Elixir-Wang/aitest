# Site Exploration Log View Redesign Implementation Plan

> **For agentic workers:** implement task-by-task. Read the primary spec first, keep `run.log` as the only log fact source, and do not invent frontend-only exploration facts.

**Goal:** Redesign the exploration log tab from raw text rows into a structured event view with summary, filters, expandable details, and raw log fallback.

**Architecture:** Keep the existing exploration log API and `logs/run.log` artifact. First implement a frontend parser/view layer that turns JSON Lines or stable text log rows into typed display entries. Backend changes are optional and limited to returning derived `entries` later; no new log store, no merge into `operation_logs`.

**Primary Spec:** `docs/superpowers/specs/2026-05-30-site-exploration-log-view-redesign-spec.md`

---

## File Map

- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - Replace the current raw log table with structured log summary, filters, event list, expandable details, and raw log fallback.
- Create or modify: `apps/frontend/src/components/ai-testing/exploration-log/`
  - Add focused exploration log components if the page file becomes too large.
- Modify: `apps/frontend/src/lib/api-client.ts`
  - Add shared exploration log entry types only if this file is the current DTO source.
- Optional modify: `apps/backend/app/services/exploration_service.py`
  - Return derived `entries` and `summary` from existing `run.log` if frontend parsing proves too brittle.
- Optional modify: `apps/backend/app/schemas/exploration.py`
  - Add response fields only if backend-derived entries are implemented.
- Test: frontend validation command from `apps/frontend/package.json`.

---

## Design Decisions

- `logs/run.log` remains the authoritative log artifact.
- Do not create `events.jsonl`.
- Do not insert exploration process events into `operation_logs`.
- Default view is structured events, not raw `pre` text.
- Raw `run.log` remains available as a fallback.
- JSON log lines should be parsed losslessly where possible.
- Unknown or unparsable lines should still appear as raw events.
- Frontend must not infer business meaning beyond the explicit log fields.
- System logs are a UX reference only; exploration logs keep page/action/artifact semantics.

---

## Task 1: Inspect Current Log Payloads

**Files:**
- `apps/backend/data/projects/*/exploration/*/logs/run.log`
- `apps/backend/runners/playwright/site-explorer.mjs`
- `apps/backend/app/services/exploration_service.py`
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Inspect several current `run.log` files.
- [ ] Confirm whether log lines are JSON Lines, stable text prefixes, or mixed.
- [ ] Confirm current frontend `ExplorationLog` type fields.
- [ ] Confirm existing parser behavior in `parseLogEntries`.
- [ ] Document the supported parsing formats in code comments near the parser.

Verification:

```bash
rg -n "function parseLogEntries|type ExplorationLog|ExplorationLogPanel" 'apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx'
find apps/backend/data/projects -path '*/exploration/*/logs/run.log' -maxdepth 8 | head
```

---

## Task 2: Define Frontend Event Types And Parser

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Optional create: `apps/frontend/src/components/ai-testing/exploration-log/exploration-log-parser.ts`

- [ ] Add `ExplorationLogEntry` type with:
  - `id`
  - `timestamp`
  - `type`
  - `level`
  - `pageId`
  - `pageTitle`
  - `url`
  - `actionName`
  - `result`
  - `artifactPath`
  - `summary`
  - `raw`
  - `payload`
- [ ] Parse JSON Lines produced by runner `logEvent`.
- [ ] Preserve all original JSON fields in `payload`.
- [ ] Map known event names to Chinese labels.
- [ ] Map event type to category:
  - 页面
  - 动作
  - 产物
  - 阻塞
  - 错误
  - 安全拦截
  - 运行
- [ ] For unparsable lines, return an entry with `type: "raw"` and `level: "info"`.
- [ ] Ensure parser never throws for malformed lines.

Acceptance:

- Existing `run.log` content produces entries.
- Malformed lines are visible instead of breaking the tab.
- JSON payload fields remain available for details.

---

## Task 3: Build Log Summary Header

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Optional create: `apps/frontend/src/components/ai-testing/exploration-log/exploration-log-summary.tsx`

- [ ] Add a compact summary header above the list.
- [ ] Show:
  - run status
  - entry count
  - page event count
  - action event count
  - blocker count
  - error count
  - last event time
- [ ] Keep the layout dense and consistent with existing `ShellSection` and cards.
- [ ] Do not duplicate metrics already prominent in the overview tab unless they help log triage.

Acceptance:

- User can immediately see whether the run has errors or blockers.
- Empty logs still show a useful state.

---

## Task 4: Add Filters

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Optional create: `apps/frontend/src/components/ai-testing/exploration-log/exploration-log-filters.tsx`

- [ ] Add state for:
  - event category
  - level
  - page
  - keyword
- [ ] Derive page options from parsed entries.
- [ ] Filter by category, level, page, and keyword.
- [ ] Keyword should search summary, raw line, URL, page title, action name, result, artifact path.
- [ ] Add a reset action.

Acceptance:

- User can isolate blockers/errors quickly.
- User can narrow logs to one page.
- No filter combination causes layout overflow.

---

## Task 5: Replace Raw Table With Structured Event List

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Optional create: `apps/frontend/src/components/ai-testing/exploration-log/exploration-log-timeline.tsx`

- [ ] Replace the two-column raw table as the main view.
- [ ] Render each event with:
  - time
  - type badge
  - level badge when warning/error
  - page title or page ID
  - summary
  - artifact/action/result short text when present
- [ ] Keep event rows stable in height before expansion.
- [ ] Use clear empty states for no logs and no filter results.
- [ ] Preserve loading and error states.

Acceptance:

- Main log view is no longer a raw `pre` table.
- Important events are scannable without expanding rows.

---

## Task 6: Add Expandable Details

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Optional create: `apps/frontend/src/components/ai-testing/exploration-log/exploration-log-entry-detail.tsx`

- [ ] Add expand/collapse per event.
- [ ] Detail section shows available fields grouped as:
  - context: page ID, title, URL
  - action: action name, locator hint, role/name if present
  - result: edge ID, target, status, reason
  - artifacts: artifact path or evidence path
  - raw: original log line
- [ ] Render unknown payload fields as compact JSON only in the detail area.
- [ ] Keep long URLs and raw lines wrapped.

Acceptance:

- A user can inspect the exact raw evidence for any summarized event.
- Unknown future fields remain visible.

---

## Task 7: Add Raw Log Fallback View

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] Add a `查看原始日志` toggle, collapsible panel, or secondary tab inside the log panel.
- [ ] Show `log.log_path`.
- [ ] Show full `log.log_content` in a wrapped monospace block.
- [ ] Make raw view available even when structured parsing fails.

Acceptance:

- Full `run.log` remains accessible.
- Raw log does not dominate the default view.

---

## Task 8: Optional Backend-Derived Entries

**Only do this if frontend parsing is brittle after Task 1.**

**Files:**
- Modify: `apps/backend/app/schemas/exploration.py`
- Modify: `apps/backend/app/services/exploration_service.py`
- Modify: `apps/backend/tests/test_exploration_service.py`

- [ ] Add optional `entries` and `summary` fields to `ExplorationLogOut`.
- [ ] Parse `run.log` server-side using the same JSON Lines rules.
- [ ] Return raw log content unchanged.
- [ ] Add tests for JSON line, malformed line, and empty log behavior.
- [ ] Keep response backward compatible.

Verification:

```bash
cd apps/backend
python -m pytest tests/test_exploration_service.py -q
```

---

## Task 9: Frontend Verification

**Files:**
- `apps/frontend/package.json`

- [ ] Run the existing frontend validation command.
- [ ] If lint/typecheck scripts are separate, run both.
- [ ] Start the frontend dev server if needed.
- [ ] Open an existing exploration run detail page.
- [ ] Verify:
  - default structured view renders
  - filters work
  - rows expand
  - raw log is available
  - loading/error/empty states still work

Suggested commands:

```bash
cd apps/frontend
npm run lint
npm run typecheck
```

Use the actual scripts from `package.json` if names differ.

---

## Task 10: Regression Checks

- [ ] Confirm exploration overview tab still renders `AgentPlan`.
- [ ] Confirm exploration report tab still loads lazily.
- [ ] Confirm clicking refresh reloads logs.
- [ ] Confirm old runs with missing or empty `run.log` do not crash.
- [ ] Confirm system logs page is unchanged.
- [ ] Confirm no new backend table or artifact file is introduced.

---

## Completion Criteria

- The exploration log tab defaults to a structured event view.
- Users can filter by event category, level, page, and keyword.
- Users can expand events for context and raw evidence.
- Users can view the complete raw `run.log`.
- Existing log API remains compatible.
- Frontend validation passes, or any remaining validation failure is documented with cause.

