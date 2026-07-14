# API Scenario Asset Picker Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three-column scenario asset picker with a compact, grouped interface selector matching the existing API asset list.

**Architecture:** Keep all picker state and rendering inside `ApiScenarioAssetPicker`. Derive searchable endpoint groups from each endpoint's first tag, reuse the existing selection array to preserve ordering, and remove all preview-only state and UI.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Radix Dialog, Node test contracts, Biome.

---

### Task 1: Lock the simplified picker contract

**Files:**
- Modify: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

- [ ] **Step 1: Write the failing contract assertions**

Add assertions requiring grouped selection controls and forbidding the old three-column content:

```js
test("scenario asset picker uses a compact grouped interface selector", () => {
  assert.match(scenarioAssetPickerSource, /选择分组/);
  assert.match(scenarioAssetPickerSource, /未找到匹配接口/);
  assert.match(scenarioAssetPickerSource, /ChevronRight/);
  assert.doesNotMatch(scenarioAssetPickerSource, /接口文档/);
  assert.doesNotMatch(scenarioAssetPickerSource, /请求参数/);
  assert.doesNotMatch(scenarioAssetPickerSource, /SelectTrigger/);
});
```

- [ ] **Step 2: Run the contract test and verify failure**

Run: `node --test tests/api-automation-scenario-contract.test.mjs`

Expected: FAIL because the picker still renders the old sidebars, preview sections, and method selector.

### Task 2: Implement grouped endpoint selection

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-asset-picker.tsx`

- [ ] **Step 1: Replace obsolete imports and state**

Use `ChevronDown`, `ChevronRight`, and `Search`; remove `Select` imports, `method`, and `previewId`. Add `expandedGroups` state.

- [ ] **Step 2: Derive searchable endpoint groups**

Create groups from the first trimmed endpoint tag or `未分组`. Search across method, path, summary, description, and tags. Search results force matching groups open.

```ts
const groupedEndpoints = useMemo(() => {
  const keyword = query.trim().toLowerCase();
  const visibleEndpoints = keyword
    ? endpoints.filter((endpoint) =>
        [endpoint.method, endpoint.path, endpoint.summary, endpoint.description, ...endpoint.tags]
          .join(" ")
          .toLowerCase()
          .includes(keyword),
      )
    : endpoints;

  return visibleEndpoints.reduce<Record<string, ApiAutomationEndpoint[]>>((groups, endpoint) => {
    const group = endpoint.tags[0]?.trim() || "未分组";
    groups[group] = [...(groups[group] ?? []), endpoint];
    return groups;
  }, {});
}, [endpoints, query]);
```

- [ ] **Step 3: Add ordered group selection**

Group selection appends only unselected endpoint IDs in visible group order. Group deselection removes only that group's IDs. The group checkbox uses true, false, or `indeterminate` based on selected child count.

- [ ] **Step 4: Replace the dialog body**

Use a single-column `sm:max-w-2xl` dialog with header, search field, independently scrolling group list, and footer. Each group row reuses the API asset list's slate background, chevron, count badge, and checkbox. Expanded endpoint rows show method badge, summary, path, and selected styling.

- [ ] **Step 5: Reset transient state on close**

Route all close actions through a helper that clears query, selected IDs, and expanded groups before invoking `onOpenChange(false)`.

### Task 3: Verify behavior and code quality

**Files:**
- Test: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`
- Test: `apps/frontend/tests/api-scenario-model.test.mjs`
- Check: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-asset-picker.tsx`

- [ ] **Step 1: Run scenario tests**

Run: `node --test tests/api-automation-scenario-contract.test.mjs tests/api-scenario-model.test.mjs`

Expected: all tests pass.

- [ ] **Step 2: Run Biome**

Run: `npx biome check src/components/ai-testing/api-automation/api-scenario-asset-picker.tsx tests/api-automation-scenario-contract.test.mjs`

Expected: no diagnostics.

- [ ] **Step 3: Verify the local page**

Open the scenario editor on `http://localhost:3000`, launch the asset picker, and verify the single-column grouped list, group selection, individual selection, search expansion, scrolling, and footer selection count.
