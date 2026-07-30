# AI Drawer Handle Layout Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the drawer header whitespace caused by the Vaul handle and move the plan copy action into the header.

**Architecture:** Keep Vaul `handleOnly` so body text remains selectable. Position a wrapper element absolutely at the drawer edge and keep `DrawerHandle` inside it, preventing Vaul's `position: relative` rule from affecting header layout. Render the existing `OneClipboard` action in the header only when a plan exists.

**Tech Stack:** React, TypeScript, Vaul, Tailwind CSS, Node test runner, Biome.

## Global Constraints

- Reuse the existing `DrawerHandle` and `OneClipboard` components.
- Preserve native text selection in drawer content.
- Do not change drawer generation, apply, discard, or close behavior.

---

### Task 1: Lock the corrected layout contract

**Files:**
- Modify: `apps/frontend/tests/api-scenario-ai-generation-drawer-contract.test.mjs`

- [ ] Assert the drag handle is inside an absolutely positioned wrapper.
- [ ] Assert the copy action is rendered inside `DrawerHeader`.
- [ ] Assert the copy action is no longer rendered inside `DrawerFooter`.
- [ ] Run the contract test and confirm it fails before implementation.

### Task 2: Correct the drawer header layout

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`

- [ ] Wrap `DrawerHandle` with an absolutely positioned edge container.
- [ ] Remove absolute positioning from `DrawerHandle` itself.
- [ ] Move `OneClipboard` from the footer into the header.
- [ ] Run contract tests, TypeScript, and Biome lint.
