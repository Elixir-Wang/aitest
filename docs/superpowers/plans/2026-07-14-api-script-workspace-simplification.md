# API Script Workspace Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove script code viewing across frontend and backend, move script execution beside deletion, and remove the requested configuration and footer controls without affecting generation or execution.

**Architecture:** Delete the dedicated script-file preview request from the API boundary inward, while retaining generated file paths used by runtime operations. Simplify the existing test-script workspace in place and derive readiness from the selected script record instead of preview file contents.

**Tech Stack:** Next.js 16, React 19, TypeScript, Node test runner, FastAPI, pytest.

## Global Constraints

- Preserve existing uncommitted work in all touched files.
- Do not remove generated script files or `test_file_path` / `data_file_path` fields.
- Do not modify script generation, script execution, run history, or environment data models.
- Do not create commits unless the user explicitly requests them.

---

### Task 1: Lock Frontend Simplification Contract

**Files:**
- Modify: `apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs`

**Interfaces:**
- Consumes: source text from the API automation project page and API client.
- Produces: failing assertions that define the removed preview API and the new action layout.

- [ ] **Step 1: Replace the existing script preview assertions**

Update the script-generation contract to assert that generation and execution remain, while preview state and requests are absent:

```js
assert.match(projectPageSource, /handleRun\(runTargetScriptIds\)/);
assert.doesNotMatch(projectPageSource, /getApiAutomationScriptFiles/);
assert.doesNotMatch(projectPageSource, /scriptCodeOpen/);
assert.doesNotMatch(projectPageSource, /查看代码/);
assert.doesNotMatch(apiClientSource, /ApiAutomationScriptFile/);
assert.doesNotMatch(apiClientSource, /getApiAutomationScriptFiles/);
```

- [ ] **Step 2: Add layout and copy-removal assertions**

Add assertions covering the requested UI:

```js
assert.match(projectPageSource, /删除[\s\S]*执行脚本/);
assert.doesNotMatch(projectPageSource, /修改环境配置/);
assert.doesNotMatch(projectPageSource, /新建接口环境/);
assert.doesNotMatch(projectPageSource, /前置检查 \{scriptReadinessChecks/);
assert.doesNotMatch(projectPageSource, /runTargetCaseCount/);
```

- [ ] **Step 3: Run the frontend contract and verify RED**

Run from `apps/frontend`:

```powershell
rtk node --test tests/api-automation-interface-set-copy-contract.test.mjs
```

Expected: FAIL because preview imports, state, dialog, API client method, environment button, and footer summary still exist.

### Task 2: Remove Frontend Preview and Reposition Execution

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Test: `apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs`

**Interfaces:**
- Consumes: `ApiAutomationScript.test_file_path`, `runTargetScriptIds`, `readyToRun`, and `handleRun`.
- Produces: a page with delete and execute actions together and no script-file preview request.

- [ ] **Step 1: Delete preview API client surface**

Remove `ApiAutomationScriptFile` and `getApiAutomationScriptFiles` from `api-client.ts`, including the `/api-scripts/${scriptId}/files` request.

- [ ] **Step 2: Delete preview imports and state**

Remove `ApiAutomationScriptFile`, `getApiAutomationScriptFiles`, `scriptFiles`, `activeScriptFileKey`, `scriptCodeOpen`, and `activeScriptFile` from the page.

- [ ] **Step 3: Delete preview loading effect and dialog**

Remove the `useEffect` that loads script files and the complete `<Dialog open={scriptCodeOpen} ...>` block titled “脚本代码”.

- [ ] **Step 4: Preserve readiness without preview data**

Replace the file readiness check with the script record:

```ts
const scriptReadinessChecks = [
  { label: "已选择运行环境", ready: Boolean(selectedEnvironment) },
  { label: "API Base URL 已配置", ready: Boolean(selectedEnvironment?.api_base_url.trim()) },
  { label: "身份凭证配置可用", ready: Boolean(selectedEnvironment) },
  { label: "脚本文件已生成", ready: Boolean(activeScript?.test_file_path.trim()) },
];
```

- [ ] **Step 5: Move execute beside delete**

Place the existing execute button immediately after the bulk delete button in the left header action group:

```tsx
<Button
  disabled={busy || !readyToRun || runTargetScriptIds.length === 0}
  onClick={() => handleRun(runTargetScriptIds)}
  size="sm"
>
  {busy ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
  {runTargetScriptIds.length > 1 ? `执行 ${runTargetScriptIds.length} 个脚本` : "执行脚本"}
</Button>
```

- [ ] **Step 6: Remove requested controls and footer**

Delete the “修改环境配置/新建接口环境” button and delete the entire bottom action bar that renders environment/script/case counts, readiness progress, and the old execute button.

- [ ] **Step 7: Run the frontend contract and verify GREEN**

Run from `apps/frontend`:

```powershell
rtk node --test tests/api-automation-interface-set-copy-contract.test.mjs
```

Expected: PASS.

### Task 3: Remove Backend Preview Endpoint

**Files:**
- Modify: `apps/backend/tests/test_api_automation_script_generator.py`
- Modify: `apps/backend/app/api/v1/api_automation.py`
- Modify: `apps/backend/app/services/api_automation/service.py`

**Interfaces:**
- Consumes: existing script generation and list APIs.
- Produces: no route or service method capable of returning generated script file contents.

- [ ] **Step 1: Remove preview expectations from the backend test**

Delete these lines from `test_generate_scripts_creates_pytest_project_without_hardcoded_environment`:

```python
files = service.get_api_script_files("project-1", script["id"], ACTOR)
assert {item["kind"] for item in files["files"]} == {"test", "data"}
```

Add a focused source contract test in the same file:

```python
def test_script_file_preview_service_is_not_exposed() -> None:
    assert not hasattr(service, "get_api_script_files")
```

- [ ] **Step 2: Run the backend test and verify RED**

Run from `apps/backend`:

```powershell
rtk .venv\Scripts\python.exe -m pytest tests/test_api_automation_script_generator.py -q
```

Expected: FAIL because `service.get_api_script_files` still exists.

- [ ] **Step 3: Delete route and service method**

Remove the `/api-scripts/{script_id}/files` route from `api_automation.py` and remove `get_api_script_files` from `service.py`. Do not modify `get_api_script`, generation, deletion, or runtime path resolution.

- [ ] **Step 4: Run the backend test and verify GREEN**

Run from `apps/backend`:

```powershell
rtk .venv\Scripts\python.exe -m pytest tests/test_api_automation_script_generator.py -q
```

Expected: PASS.

### Task 4: Validate Integrated Change

**Files:**
- Verify: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx`
- Verify: `apps/frontend/src/lib/api-client.ts`
- Verify: `apps/backend/app/api/v1/api_automation.py`
- Verify: `apps/backend/app/services/api_automation/service.py`

**Interfaces:**
- Consumes: completed frontend and backend changes.
- Produces: type-safe code with no preview symbols or route remnants.

- [ ] **Step 1: Search for removed symbols**

Run from repository root:

```powershell
rtk rg -n "ApiAutomationScriptFile|getApiAutomationScriptFiles|get_api_script_files|scriptCodeOpen|查看代码|api-scripts/\{script_id\}/files" apps/frontend apps/backend
```

Expected: no production-code matches.

- [ ] **Step 2: Run frontend type checking**

Run from `apps/frontend`:

```powershell
rtk npx tsc --noEmit
```

Expected: PASS with exit code 0.

- [ ] **Step 3: Run focused frontend and backend tests together**

Run the frontend contract and backend generator suite again using the commands from Tasks 2 and 3.

- [ ] **Step 4: Inspect the final diff**

Run from repository root:

```powershell
rtk git diff -- apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx apps/frontend/src/lib/api-client.ts apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs apps/backend/app/api/v1/api_automation.py apps/backend/app/services/api_automation/service.py apps/backend/tests/test_api_automation_script_generator.py
```

Expected: only the approved preview removal, action relocation, footer removal, environment button removal, and focused test updates.
