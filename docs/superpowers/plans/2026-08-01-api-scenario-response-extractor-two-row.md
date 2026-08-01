# API Scenario Response Extractor Two-Row Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed four-column response extractor row with a readable two-row card that preserves existing extraction data and runtime behavior.

**Architecture:** Keep `ExtractorEditor` in the existing scenario step configuration component. Each extractor renders a two-row grid: variable name/source on row one and a full-width source-specific path control on row two. The existing `ApiAutomationScenarioExtractor` shape remains unchanged; `required` becomes visible through the existing checkbox component.

**Tech Stack:** React, TypeScript/TSX, Tailwind utility classes, existing shadcn UI components, Node contract tests.

## Global Constraints

- Do not change backend extraction semantics or API payload shape.
- Preserve historical `expression ?? path` display compatibility.
- Keep the existing source values: `response.body`, `response.header`, and `response.status`.
- Do not alter unrelated uncommitted changes in the repository.
- Do not commit changes unless explicitly requested.

---

### Task 1: Add failing response extractor UI contracts

**Files:**
- Modify: `apps/frontend/tests/api-scenario-step-config-contract.test.mjs`

**Interfaces:**
- Consumes: source text of `api-scenario-step-config.tsx`.
- Produces: static contracts for two-row structure, labels, source-specific path behavior, and required toggle.

- [ ] **Step 1: Add a two-row layout contract**

Assert the extractor editor source contains separate row markers/classes and the labels `保存为`, `来源`, and `提取路径`.

- [ ] **Step 2: Add source-specific behavior contracts**

Assert the source includes conditional handling for `response.status` and source-specific placeholders for Body and Header.

- [ ] **Step 3: Add required-field contract**

Assert the source binds a checkbox to `extractor.required` and preserves `required: true` when adding a new extractor.

- [ ] **Step 4: Run the focused test and verify RED**

Run: `npm test -- --runInBand tests/api-scenario-step-config-contract.test.mjs`

Expected: the new contracts fail against the current fixed-grid implementation.

### Task 2: Implement the two-row extractor card

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-step-config.tsx:850-906`

**Interfaces:**
- Consumes: existing `ApiAutomationScenarioExtractor`, `Input`, `Select`, `Checkbox`, `Button`, and `replaceAt` helpers.
- Produces: responsive two-row editor that emits the same extractor objects through `onChange`.

- [ ] **Step 1: Replace the fixed four-column wrapper**

Render each extractor as a two-row grid with `min-w-0`, removing the fixed `150px 170px 1fr 36px` layout.

- [ ] **Step 2: Add explicit field labels**

Label the variable input `保存为`, the source selector `来源`, and the path control `提取路径`.

- [ ] **Step 3: Make path controls source-aware**

Use `expression ?? path` as the value. Show `$.data.id` for Body, `Header 名称` for Header, and disable the path input for Status with `自动取 HTTP 状态码`.

- [ ] **Step 4: Expose required behavior**

Add a checkbox labeled `未提取到时终止步骤`, defaulting to true for legacy records where `required` is undefined, and update only the `required` field.

- [ ] **Step 5: Preserve delete behavior and key stability**

Keep the existing delete callback and extractor key strategy; ensure the delete button remains aligned at the right side of the card.

### Task 3: Verify behavior and formatting

**Files:**
- Test: `apps/frontend/tests/api-scenario-step-config-contract.test.mjs`
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-step-config.tsx`

- [ ] **Step 1: Run the focused contract test**

Run: `npm test -- --runInBand tests/api-scenario-step-config-contract.test.mjs`

Expected: PASS.

- [ ] **Step 2: Run related scenario model tests**

Run: `npm test -- --runInBand tests/api-scenario-model.test.mjs tests/api-scenario-ai-generation-drawer-contract.test.mjs`

Expected: PASS with no changes to runtime serialization behavior.

- [ ] **Step 3: Inspect the final diff**

Run: `git diff -- apps/frontend/src/components/ai-testing/api-automation/api-scenario-step-config.tsx apps/frontend/tests/api-scenario-step-config-contract.test.mjs`

Confirm only the intended UI and test files changed, and no backend files were modified.
