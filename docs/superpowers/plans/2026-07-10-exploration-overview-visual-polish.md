# Exploration Overview Visual Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the exploration overview hierarchy and execution trace readability without changing its data contract.

**Architecture:** Keep the existing page and component boundaries. Flatten the page wrapper, then express step and transcript relationships with CSS-only rails and existing Lucide icons.

**Tech Stack:** Next.js, React, Tailwind CSS, lucide-react, Node test runner

## Global Constraints

- Do not add dependencies, API fields, components, or state.
- Reuse existing theme tokens and status colors.
- Preserve responsive stacking and independent panel scrolling.

---

### Task 1: Add visual contract coverage

**Files:**
- Modify: `apps/frontend/tests/exploration-detail-contract.test.mjs`

**Interfaces:**
- Consumes: source text from the exploration detail page and task info panel.
- Produces: assertions for the flattened wrapper, step rail, and transcript identity styling.

- [ ] **Step 1: Add assertions for the new class and icon markers**
- [ ] **Step 2: Run `node --test tests/exploration-detail-contract.test.mjs` and confirm the new assertions fail**

### Task 2: Implement the visual polish

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
- Modify: `apps/frontend/src/components/ai-testing/exploration-task-info-panel.tsx`

**Interfaces:**
- Consumes: existing `ExplorationMonitorState`, `ExplorationMonitorStep`, and transcript blocks.
- Produces: the same rendered information and interactions with revised visual hierarchy.

- [ ] **Step 1: Flatten the `ShellSection` wrapper with existing class overrides**
- [ ] **Step 2: Add panel title icons, step count, step rail, and state surfaces**
- [ ] **Step 3: Add Agent identity and tool execution rail styling**
- [ ] **Step 4: Run the focused contract test and confirm it passes**
- [ ] **Step 5: Run the frontend static checks**
- [ ] **Step 6: Inspect desktop and mobile screenshots for overflow and overlap**

## Self-Review

- The plan covers every design requirement without changing behavior or contracts.
- No placeholders, new dependencies, or speculative abstractions are included.
- Existing component inputs and types remain unchanged.
