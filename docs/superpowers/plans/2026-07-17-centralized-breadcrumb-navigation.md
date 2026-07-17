# Centralized Breadcrumb Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a centralized breadcrumb interface and migrate all exploration list, create, detail, and edit pages to the approved information architecture.

**Architecture:** A navigation module owns fixed section/module hierarchy and exposes semantic builders. Exploration pages provide only dynamic entity data; `PageShell` remains responsible for rendering and workspace synchronization.

**Tech Stack:** Next.js 16, React 19, TypeScript, Node test runner, Biome.

## Global Constraints

- Do not infer product breadcrumbs directly from URL segments.
- Do not insert the selected project name into project-scoped module breadcrumbs.
- Do not modify unrelated dirty files.
- Use loaded entity names for detail and edit breadcrumbs.

---

### Task 1: Breadcrumb Builder Contract

**Files:**
- Create: `apps/frontend/src/navigation/breadcrumbs.ts`
- Create: `apps/frontend/tests/breadcrumb-navigation-contract.test.mjs`

**Interfaces:**
- Produces: `explorationBreadcrumbs.list/create/detail/edit`

- [ ] Write failing builder contract tests.
- [ ] Run the tests and confirm failure.
- [ ] Implement the minimal typed builder.
- [ ] Run the tests and confirm success.

### Task 2: Exploration Route Migration

**Files:**
- Modify: `apps/frontend/src/app/(main)/exploration/page.tsx`
- Modify: `apps/frontend/src/app/(main)/exploration/new/page.tsx`
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/new/page.tsx`
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/edit/page.tsx`
- Modify: `apps/frontend/src/components/ai-testing/exploration-run-create-page.tsx`
- Modify: `apps/frontend/tests/exploration-detail-contract.test.mjs`
- Create: `apps/frontend/tests/exploration-breadcrumb-contract.test.mjs`

**Interfaces:**
- Consumes: `explorationBreadcrumbs`
- Produces: consistent exploration breadcrumb trails

- [ ] Write failing route contract tests.
- [ ] Run the tests and confirm failure.
- [ ] Replace route-local breadcrumb arrays with builders.
- [ ] Build edit breadcrumbs from the loaded task title.
- [ ] Run focused exploration tests.

### Task 3: Verification

**Files:**
- Verify only files changed by this plan.

- [ ] Run Biome checks on changed source and test files.
- [ ] Run all frontend Node contract tests.
- [ ] Run the production build.
- [ ] Review the final diff for unrelated changes.
