## [LRN-20260702-001] correction

**Logged**: 2026-07-02T15:20:00+08:00
**Priority**: high
**Status**: pending
**Area**: backend

### Summary
Page exploration artifacts for the current product flow are project-level artifacts, not run-level page artifacts.

### Details
The user corrected an analysis that assumed page artifacts live under `page_exploration/runs/{run_id}/pages`. In this codebase's intended flow, exploration page artifacts are associated with the project-level `page_exploration/pages` directory. The empty artifact tab should be analyzed as an API/indexing mismatch between project-level artifacts and the UI's listing contract, not as missing run-level files.

### Suggested Action
When debugging exploration artifact display, first identify whether the artifact producer writes project-level or run-level files, then align the backend listing/indexing API to that source of truth.

### Metadata
- Source: user_feedback
- Related Files: apps/backend/app/agents/page_exploration/tools/artifact_tools.py, apps/backend/app/services/exploration/page_exploration_service.py, apps/frontend/src/components/ai-testing/exploration-workspace.tsx
- Tags: exploration-artifacts, project-level-artifacts, correction

---

## [LRN-20260702-003] correction

**Logged**: 2026-07-02T15:28:00+08:00
**Priority**: high
**Status**: pending
**Area**: frontend

### Summary
The exploration detail page no longer exists, so run-level page artifact reads have no active UI owner.

### Details
The user clarified that there is no exploration detail page anymore. The active artifact display should be the project-level exploration artifacts tab only. Any run-level pages endpoint or frontend dependency should be treated as obsolete unless retained temporarily for compatibility.

### Suggested Action
Remove or bypass frontend calls to `/page-exploration/runs/{run_id}/pages` from the active exploration artifact UI. Use project-level page artifact APIs exclusively.

### Metadata
- Source: user_feedback
- Related Files: apps/frontend/src/components/ai-testing/exploration-workspace.tsx, apps/backend/app/api/v1/page_exploration.py
- Tags: exploration-artifacts, removed-detail-page, obsolete-run-pages

---

## [LRN-20260702-002] correction

**Logged**: 2026-07-02T15:25:00+08:00
**Priority**: high
**Status**: pending
**Area**: backend

### Summary
The run-level pages API is deprecated for page exploration artifacts and should not be preserved as the detail-page source.

### Details
The user corrected a recommendation to keep `/page-exploration/runs/{run_id}/pages` for exploration detail pages. In the current intended model, each explored page is written into the project-level `page_exploration/pages` directory. A run can reference or summarize project-level pages, but should not own a separate run-level page artifact tree.

### Suggested Action
Treat run-level pages APIs as legacy compatibility only. New UI and backend flows should read project-level page artifacts, optionally filtered or annotated by `last_explored.run_id` when run context is needed.

### Metadata
- Source: user_feedback
- Related Files: apps/backend/app/services/page_exploration/project_pages_service.py, apps/backend/app/api/v1/page_exploration.py, apps/frontend/src/components/ai-testing/exploration-workspace.tsx
- Tags: exploration-artifacts, deprecated-run-pages, project-level-pages

---
