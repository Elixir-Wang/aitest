# Test Point Mind Map Leaf Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the test-point mind map visible when a leaf node is selected.

**Architecture:** Preserve the existing `MindMapTree` selection callback and change only the test-points panel handler that currently switches views. Protect the behavior with the existing source-contract test suite.

**Tech Stack:** React, TypeScript, Node.js test runner

## Global Constraints

- Clicking a test-point leaf node only updates selection highlighting.
- The click does not switch to list view or open details.
- Do not change shared mind-map behavior for other consumers.

---

### Task 1: Preserve Mind Map View on Selection

**Files:**
- Modify: `apps/frontend/tests/test-points-panel-contract.test.mjs`
- Modify: `apps/frontend/src/components/ai-testing/test-points-panel.tsx`

**Interfaces:**
- Consumes: `handleSelectPoint(pointId: string)` and `setSelectedPointId`.
- Produces: Selection that leaves `viewMode` unchanged.

- [ ] **Step 1: Write the failing test**

Add a contract assertion that extracts `handleSelectPoint` and verifies it contains `setSelectedPointId(pointId)` but not `setViewMode("list")`.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/test-points-panel-contract.test.mjs`

Expected: FAIL because the handler still calls `setViewMode("list")`.

- [ ] **Step 3: Write minimal implementation**

Remove only `setViewMode("list")` from `handleSelectPoint`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/test-points-panel-contract.test.mjs`

Expected: PASS with no warnings or failures.
