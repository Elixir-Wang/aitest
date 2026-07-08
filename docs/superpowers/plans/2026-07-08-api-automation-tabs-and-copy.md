# API Automation Tabs And Copy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adjust the all-project API automation page so it has two tabs, "接口集" and "用例集", and the interface-set list uses the requested copy and columns.

**Architecture:** Keep this as a frontend-only change unless implementation uncovers a missing API contract. Reuse the existing `PageShell`/`ModuleTabs`, `ListToolbar`, table, selection hook, and API client functions; do not create new backend routes or rename backend models for a copy-only UI change. Treat existing `ApiAutomationCaseSet.case_count` as the displayed "接口数量" only on the "接口集" tab because the user request is phrased as a UI label change, not a backend data-model change.

**Tech Stack:** Next.js client component, React state, existing shadcn-style UI components, Node test runner, Biome.

## Global Constraints

- Follow `AGENTS.md`: read actual interfaces before changing them; reuse existing interfaces; verify actively.
- Scope is `D:\project\test_project`.
- Do not modify unrelated backend API automation behavior.
- Keep existing project aggregation behavior: the all-project page loads active projects and flattens `listApiAutomationCaseSets(projectId)`.
- Use existing frontend route `apps/frontend/src/app/(main)/automation/api/page.tsx`.

---

## File Structure

- Modify: `apps/frontend/src/app/(main)/automation/api/page.tsx`
  - Owns all-project API automation list UI.
  - Add local module tabs `["接口集", "用例集"]`.
  - Rename visible copy on the default "接口集" tab.
  - Remove "项目" and "状态" columns from the interface-set table.
  - Keep project selection in the creation dialog because creation still requires a project ID.
- Create: `apps/frontend/tests/api-automation-page-contract.test.mjs`
  - Locks the requested UI contract using source-level tests consistent with the existing frontend tests.
  - Verifies tab labels, create label, dialog title, table headers, removed columns, and user-facing copy.
- No change: `apps/frontend/src/lib/api-client.ts`
  - Existing `ApiAutomationCaseSet`, `listApiAutomationCaseSets`, and `createApiAutomationCaseSet` contracts are sufficient.
- No change: backend files under `apps/backend`
  - The request is currently UI copy/navigation structure only.

## Task 1: Add Contract Test For API Automation Page

**Files:**
- Create: `apps/frontend/tests/api-automation-page-contract.test.mjs`

**Interfaces:**
- Consumes: source file `../src/app/(main)/automation/api/page.tsx`
- Produces: failing contract tests for the requested UI changes.

- [ ] **Step 1: Write the failing test**

Create `apps/frontend/tests/api-automation-page-contract.test.mjs`:

```js
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/automation/api/page.tsx", import.meta.url), "utf8");

test("api automation all-project page exposes interface-set and case-set tabs", () => {
  assert.match(pageSource, /const apiAutomationTabs = \["接口集", "用例集"\];/);
  assert.match(pageSource, /activeTab=\{activeTab\}/);
  assert.match(pageSource, /onTabChange=\{setActiveTab\}/);
  assert.match(pageSource, /tabs=\{apiAutomationTabs\}/);
});

test("interface-set tab uses requested labels and removes project and status columns", () => {
  assert.match(pageSource, /createLabel="新建接口集"/);
  assert.match(pageSource, /title="接口集列表"/);
  assert.match(pageSource, /<DialogTitle>新建接口集<\/DialogTitle>/);
  assert.match(pageSource, /<FieldLabel htmlFor="api-case-set-name">接口集名称<\/FieldLabel>/);
  assert.match(pageSource, /<TableHead>接口集名称<\/TableHead>/);
  assert.match(pageSource, /<TableHead>接口数量<\/TableHead>/);
  assert.doesNotMatch(pageSource, /<TableHead>项目<\/TableHead>/);
  assert.doesNotMatch(pageSource, /<TableHead>状态<\/TableHead>/);
  assert.doesNotMatch(pageSource, /<TableCell>\{projectNameById\.get\(item\.project_id\) \?\? item\.project_id\}<\/TableCell>/);
  assert.doesNotMatch(pageSource, /<Badge variant="secondary">\{statusLabel\(item\.status\)\}<\/Badge>/);
});

test("case-set tab is present as a separate placeholder without changing backend contracts", () => {
  assert.match(pageSource, /activeTab === "用例集"/);
  assert.match(pageSource, /接口用例集/);
  assert.match(pageSource, /后续在这里维护接口用例集/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd apps/frontend
node --test tests/api-automation-page-contract.test.mjs
```

Expected: FAIL because the current page has no `apiAutomationTabs`, still shows `项目` and `状态`, and still uses "新建接口用例集".

- [ ] **Step 3: Commit**

```powershell
git add apps/frontend/tests/api-automation-page-contract.test.mjs
git commit -m "test: lock api automation tab copy contract"
```

## Task 2: Add Tabs And Update Interface-Set Copy

**Files:**
- Modify: `apps/frontend/src/app/(main)/automation/api/page.tsx`

**Interfaces:**
- Consumes: `PageShell` props `tabs`, `activeTab`, `onTabChange`.
- Produces: active tab state `"接口集" | "用例集"` and the requested visible copy.

- [ ] **Step 1: Add tab state**

Add near existing constants:

```ts
const apiAutomationTabs = ["接口集", "用例集"];
```

Add inside `Page()` state declarations:

```ts
const [activeTab, setActiveTab] = useState(apiAutomationTabs[0]);
```

- [ ] **Step 2: Wire tabs through `PageShell`**

Change `PageShell` props from:

```tsx
description="查看接口用例集、生成状态和用例数量。"
title="接口自动化"
```

to:

```tsx
activeTab={activeTab}
breadcrumbs={["测试资产", "接口自动化"]}
description="查看接口集和用例集。"
onTabChange={setActiveTab}
tabs={apiAutomationTabs}
title="接口自动化"
```

- [ ] **Step 3: Rename create/list/dialog copy on the interface-set tab**

Replace these user-facing strings:

```tsx
createLabel="新建接口用例集"
title="接口用例集列表"
<DialogTitle>新建接口用例集</DialogTitle>
<DialogDescription>填写名称、选择所属项目并补充备注。</DialogDescription>
<FieldLabel htmlFor="api-case-set-name">用例集名称</FieldLabel>
placeholder="搜索用例集或项目"
toast.error("请填写用例集名称");
toast.success("接口用例集已创建");
```

with:

```tsx
createLabel="新建接口集"
title="接口集列表"
<DialogTitle>新建接口集</DialogTitle>
<DialogDescription>填写名称、选择所属项目并补充备注。</DialogDescription>
<FieldLabel htmlFor="api-case-set-name">接口集名称</FieldLabel>
placeholder="搜索接口集或备注"
toast.error("请填写接口集名称");
toast.success("接口集已创建");
```

- [ ] **Step 4: Run focused test**

Run:

```powershell
cd apps/frontend
node --test tests/api-automation-page-contract.test.mjs
```

Expected: still FAIL until table columns and case-set tab content are updated in Task 3.

## Task 3: Split Interface-Set And Case-Set Tab Content

**Files:**
- Modify: `apps/frontend/src/app/(main)/automation/api/page.tsx`

**Interfaces:**
- Consumes: existing `filteredRows`, `selection`, and `formatDateTime`.
- Produces: interface-set table with columns: checkbox, 接口集名称, 备注, 接口数量, 更新时间, 操作.

- [ ] **Step 1: Wrap current table section in the default tab**

Wrap the current `ShellSection` that contains `ListToolbar` and the table:

```tsx
{activeTab === "接口集" ? (
  <ShellSection>
    ...
  </ShellSection>
) : null}
```

- [ ] **Step 2: Remove project/status table headers and cells**

Change the table headers to:

```tsx
<TableHead className="w-10">...</TableHead>
<TableHead>接口集名称</TableHead>
<TableHead>备注</TableHead>
<TableHead>接口数量</TableHead>
<TableHead>更新时间</TableHead>
<TableHead className="w-16">操作</TableHead>
```

Remove these row cells:

```tsx
<TableCell>{projectNameById.get(item.project_id) ?? item.project_id}</TableCell>
<TableCell>
  <Badge variant="secondary">{statusLabel(item.status)}</Badge>
</TableCell>
```

Change:

```tsx
<TableCell>{item.case_count}</TableCell>
```

to keep the value but align with the new header:

```tsx
<TableCell>{item.case_count}</TableCell>
```

- [ ] **Step 3: Update table colspans**

Change loading and empty-state colspans from `8` to `6`:

```tsx
{loading ? <TableLoadingRow colSpan={6} label="接口集加载中" /> : null}
...
<TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
  暂无接口集。可新建接口集后进入详情维护接口资产。
</TableCell>
```

- [ ] **Step 4: Add a separate "用例集" tab placeholder**

After the interface-set `ShellSection`, add:

```tsx
{activeTab === "用例集" ? (
  <ShellSection>
    <div className="min-h-32 rounded-lg border border-dashed p-6 text-muted-foreground text-sm">
      后续在这里维护接口用例集。
    </div>
  </ShellSection>
) : null}
```

- [ ] **Step 5: Remove now-unused imports/helpers**

If the page no longer renders status badges, remove:

```ts
import { Badge } from "@/components/ui/badge";
```

Keep `statusLabel` only if it remains part of search behavior. If search should no longer include status after removing the status column, change filtered rows from:

```ts
[item.name, item.notes, projectNameById.get(item.project_id) ?? "", statusLabel(item.status)]
```

to:

```ts
[item.name, item.notes]
```

Then delete `statusLabels` and `statusLabel`.

- [ ] **Step 6: Run focused test**

Run:

```powershell
cd apps/frontend
node --test tests/api-automation-page-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/frontend/src/app/(main)/automation/api/page.tsx apps/frontend/tests/api-automation-page-contract.test.mjs
git commit -m "feat: split api automation interface and case tabs"
```

## Task 4: Verify Frontend Formatting And Existing Contracts

**Files:**
- Verify only.

**Interfaces:**
- Consumes: frontend package scripts.
- Produces: confidence that the page compiles under project style checks and the new contract is stable.

- [ ] **Step 1: Run focused API automation contract**

```powershell
cd apps/frontend
node --test tests/api-automation-page-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 2: Run related existing frontend contracts**

```powershell
cd apps/frontend
node --test tests/test-case-set-dialog-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 3: Run Biome check for touched files**

```powershell
cd apps/frontend
npx biome check "src/app/(main)/automation/api/page.tsx" "tests/api-automation-page-contract.test.mjs"
```

Expected: PASS.

## Self-Review

- Spec coverage: The plan covers deleting visible "项目" and "状态" columns, changing "用例数量" to "接口数量", changing "新建接口用例集" to "新建接口集", and adding two tabs under "接口自动化".
- Placeholder scan: No `TBD`, `TODO`, or unspecified "handle edge cases" steps.
- Type consistency: Uses existing `ApiAutomationCaseSet.case_count` and existing `PageShell` tab interface.
