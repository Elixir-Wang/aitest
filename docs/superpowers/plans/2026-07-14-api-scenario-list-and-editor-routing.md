# API 场景列表与独立编辑页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将接口自动化“场景编排”改造成项目列表同款场景列表，并让新建和编辑进入独立编排页面。

**Architecture:** 主接口自动化页面只负责场景列表查询、筛选、选择和删除；新的 `ApiScenarioEditor` 组件独立维护场景基础信息、步骤、校验、发布和运行状态。新建与编辑路由共享编辑器，新建首次保存时先创建场景再替换步骤，并将 URL 替换为编辑路由。

**Tech Stack:** Next.js 16 App Router、React 19、TypeScript、Tailwind CSS、现有 shadcn UI 组件、Node.js contract tests、Biome。

## Global Constraints

- 复用现有 API 客户端函数，不新增或猜测后端接口。
- 列表交互和视觉结构复用项目列表的 `ListToolbar`、`Table`、`Checkbox`、`RowActions` 模式。
- 新建页面保存前不得产生后端场景记录。
- 其他接口自动化页签及运行详情查询参数行为保持不变。
- 不引入新的 npm 依赖。
- 未经用户明确要求，不创建 Git commit。

---

## File Structure

- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-list.tsx`
  - 只负责场景列表展示、搜索、选择、删除和路由跳转。
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`
  - 负责新建/编辑模式的数据加载、表单状态、步骤编排、保存、校验、发布和运行。
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/scenarios/new/page.tsx`
  - 提供新建场景页面壳并传入 `projectId`。
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/scenarios/[scenarioId]/page.tsx`
  - 提供编辑场景页面壳并传入 `projectId`、`scenarioId`。
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx`
  - 移除场景编辑状态与三栏 UI，保留场景列表页签并支持 `tab=scenarios`。
- Modify: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`
  - 将旧单页契约改为列表、路由和编辑器拆分契约。

---

### Task 1: Add Failing Route And Component Contracts

**Files:**
- Modify: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

**Interfaces:**
- Consumes: 现有 Node.js `node:test` 文件读取契约模式。
- Produces: 对列表组件、编辑器组件、新建路由、编辑路由和主页面集成方式的静态契约。

- [ ] **Step 1: Replace the single-page source setup**

将测试文件顶部改为读取拆分后的源文件：

```js
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const readSource = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

const automationPageSource = readSource("../src/app/(main)/projects/[projectId]/automation/api/page.tsx");
const scenarioListSource = readSource(
  "../src/components/ai-testing/api-automation/api-scenario-list.tsx",
);
const scenarioEditorSource = readSource(
  "../src/components/ai-testing/api-automation/api-scenario-editor.tsx",
);
const newScenarioPageSource = readSource(
  "../src/app/(main)/projects/[projectId]/automation/api/scenarios/new/page.tsx",
);
const editScenarioPageSource = readSource(
  "../src/app/(main)/projects/[projectId]/automation/api/scenarios/[scenarioId]/page.tsx",
);
const clientSource = readSource("../src/lib/api-client.ts");
```

- [ ] **Step 2: Add the list and route contracts**

```js
test("scenario tab renders a project-list style scenario list", () => {
  assert.match(automationPageSource, /tab=scenarios|scenarios/);
  assert.match(automationPageSource, /ApiScenarioList/);
  assert.match(scenarioListSource, /ListToolbar/);
  assert.match(scenarioListSource, /新建场景/);
  assert.match(scenarioListSource, /场景名称/);
  assert.match(scenarioListSource, /步骤数/);
  assert.match(scenarioListSource, /更新时间/);
  assert.match(scenarioListSource, /RowActions/);
  assert.match(scenarioListSource, /deleteApiAutomationScenario/);
});

test("new and existing scenarios use dedicated editor routes", () => {
  assert.match(newScenarioPageSource, /ApiScenarioEditor/);
  assert.match(newScenarioPageSource, /新建接口场景/);
  assert.match(editScenarioPageSource, /ApiScenarioEditor/);
  assert.match(editScenarioPageSource, /scenarioId/);
  assert.match(scenarioListSource, /scenarios\/new/);
  assert.match(scenarioListSource, /scenarios\/\$\{scenario\.id\}/);
});
```

- [ ] **Step 3: Move the lifecycle contract to the editor component**

```js
test("scenario editor supports ordered steps, saving, validation, publishing, and execution", () => {
  assert.match(scenarioEditorSource, /执行步骤/);
  assert.match(scenarioEditorSource, /moveScenarioStep/);
  assert.match(scenarioEditorSource, /createApiAutomationScenario/);
  assert.match(scenarioEditorSource, /replaceApiAutomationScenarioSteps/);
  assert.match(scenarioEditorSource, /validateApiAutomationScenario/);
  assert.match(scenarioEditorSource, /publishApiAutomationScenario/);
  assert.match(scenarioEditorSource, /executeApiAutomationScenario/);
  assert.match(scenarioEditorSource, /router\.replace/);
  assert.match(scenarioEditorSource, /变量绑定/);
  assert.match(scenarioEditorSource, /响应提取/);
});
```

保留现有 API 客户端生命周期端点测试。

- [ ] **Step 4: Run the contract test and verify failure**

Run:

```bash
cd apps/frontend
node --test tests/api-automation-scenario-contract.test.mjs
```

Expected: FAIL，错误为新的列表组件、编辑器组件或路由文件不存在。

---

### Task 2: Build The Scenario List And Integrate The Tab

**Files:**
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-list.tsx`
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx`
- Test: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

**Interfaces:**
- Consumes: `listApiAutomationScenarios(projectId)`、`deleteApiAutomationScenario(projectId, scenarioId)`、`formatDateTime(value)`。
- Produces: `ApiScenarioList({ projectId }: { projectId: string })`。

- [ ] **Step 1: Create the list component state and loader**

创建客户端组件并定义以下状态：

```tsx
type ApiScenarioListProps = {
  projectId: string;
};

export function ApiScenarioList({ projectId }: ApiScenarioListProps) {
  const router = useRouter();
  const [scenarios, setScenarios] = useState<ApiAutomationScenario[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const loadScenarios = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listApiAutomationScenarios(projectId);
      setScenarios(rows);
      setSelectedIds((current) => current.filter((id) => rows.some((scenario) => scenario.id === id)));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "场景列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void loadScenarios();
  }, [loadScenarios]);
```

- [ ] **Step 2: Add filtering, selection, and deletion behavior**

```tsx
const filteredRows = useMemo(() => {
  const keyword = searchText.trim().toLowerCase();
  if (!keyword) return scenarios;
  return scenarios.filter((scenario) =>
    `${scenario.name} ${scenario.description}`.toLowerCase().includes(keyword),
  );
}, [scenarios, searchText]);

const visibleIds = filteredRows.map((scenario) => scenario.id);
const visibleSelectedIds = visibleIds.filter((id) => selectedIds.includes(id));
const allSelected = visibleIds.length > 0 && visibleSelectedIds.length === visibleIds.length;
const partiallySelected = visibleSelectedIds.length > 0 && !allSelected;

async function deleteScenarios(ids: string[]) {
  if (ids.length === 0) return;
  setBusy(true);
  try {
    await Promise.all(ids.map((scenarioId) => deleteApiAutomationScenario(projectId, scenarioId)));
    setSelectedIds([]);
    await loadScenarios();
    toast.success(`已删除 ${ids.length} 个场景`);
  } catch (error) {
    toast.error(error instanceof Error ? error.message : "场景删除失败");
  } finally {
    setBusy(false);
  }
}
```

实现 `toggleOne` 与 `toggleAll`，行为与项目列表一致。

- [ ] **Step 3: Render the project-list style toolbar and table**

使用以下固定字段顺序：复选框、场景名称、描述、步骤数、状态、更新时间、操作。

```tsx
<ListToolbar
  createLabel="新建场景"
  onBatchDelete={() => deleteScenarios(visibleSelectedIds)}
  onCreate={() => router.push(`/projects/${projectId}/automation/api/scenarios/new`)}
  onSearch={setSearchText}
  placeholder="搜索场景名称或描述"
  selectedCount={visibleSelectedIds.length}
  title="场景列表"
/>
```

名称链接和操作菜单使用：

```tsx
const editorHref = `/projects/${projectId}/automation/api/scenarios/${scenario.id}`;

<Link className="block truncate hover:underline" href={editorHref} title={scenario.name}>
  {scenario.name}
</Link>

<RowActions
  actions={[
    { label: "编辑", href: editorHref, icon: Pencil },
    {
      label: "删除",
      destructive: true,
      disabled: busy,
      icon: Trash2,
      onSelect: () => deleteScenarios([scenario.id]),
    },
  ]}
  label={`打开 ${scenario.name} 操作菜单`}
/>
```

状态文案由本地函数统一生成：

```tsx
function scenarioStatusLabel(scenario: ApiAutomationScenario) {
  if (scenario.status === "ready") return `已发布 v${scenario.revision}`;
  if (scenario.status === "archived") return "已归档";
  return "未发布";
}
```

空状态文案使用“暂无场景。新建场景后，可组合接口用例并发布运行。”。

- [ ] **Step 4: Replace the old scenario workbench in the main page**

在主页面：

1. 导入 `ApiScenarioList`。
2. 将初始页签映射改为显式函数，至少支持：

```tsx
function tabFromSearchParam(value: string | null) {
  if (value === "cases") return "接口用例";
  if (value === "runs") return "运行记录";
  if (value === "scenarios") return "场景编排";
  return tabs[0];
}
```

3. 使用 `useState(() => tabFromSearchParam(searchParams.get("tab")))` 初始化页签。
4. 将原三栏场景 JSX 替换为：

```tsx
{activeTab === "场景编排" && <ApiScenarioList projectId={projectId} />}
```

5. 从主页面移除仅供编辑器使用的场景 state、`applyScenario`、创建/保存/校验/发布/执行/删除/步骤操作函数和场景详情加载 effect。
6. 主页面保留重新运行场景所需的 `executeApiAutomationScenario` 导入与 `handleRerun` 分支。
7. 主页面初始批量数据加载和 `refresh()` 不再请求 `listApiAutomationScenarios`。

- [ ] **Step 5: Run the list contract subset**

Run:

```bash
cd apps/frontend
node --test --test-name-pattern="scenario tab|dedicated editor routes" tests/api-automation-scenario-contract.test.mjs
```

Expected: 列表契约中与 `ApiScenarioList` 有关的断言通过；路由文件断言仍因文件未创建而失败。

---

### Task 3: Build The Shared Scenario Editor

**Files:**
- Create: `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`
- Test: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

**Interfaces:**
- Consumes: 现有场景 CRUD、步骤替换、校验、发布、执行、接口用例、端点和环境列表 API。
- Produces: `ApiScenarioEditor({ projectId, scenarioId? }: { projectId: string; scenarioId?: string })`。

- [ ] **Step 1: Define editor modes and draft state**

```tsx
type ApiScenarioEditorProps = {
  projectId: string;
  scenarioId?: string;
};

export function ApiScenarioEditor({ projectId, scenarioId }: ApiScenarioEditorProps) {
  const router = useRouter();
  const isNew = !scenarioId;
  const [scenario, setScenario] = useState<ApiAutomationScenario | null>(null);
  const [scenarioName, setScenarioName] = useState("");
  const [scenarioDescription, setScenarioDescription] = useState("");
  const [scenarioVariablesText, setScenarioVariablesText] = useState("{}");
  const [scenarioSteps, setScenarioSteps] = useState<ApiAutomationScenarioStep[]>([]);
  const [activeScenarioStepId, setActiveScenarioStepId] = useState("");
  const [apiTestCases, setApiTestCases] = useState<ApiAutomationTestCase[]>([]);
  const [endpoints, setEndpoints] = useState<ApiAutomationEndpoint[]>([]);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState("");
  const [scenarioValidation, setScenarioValidation] = useState<{
    errors: string[];
    warnings: string[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
```

`applyScenario` 只更新编辑器本地状态，不再维护列表数组。

- [ ] **Step 2: Load editor dependencies and existing scenario**

使用单个 effect 并行加载端点、环境、接口用例；编辑模式额外加载当前场景：

```tsx
const requests = [
  listApiAutomationEndpoints(projectId),
  listApiAutomationEnvironments(projectId),
  listApiAutomationTestCases(projectId),
] as const;

const [endpointRows, environmentRows, apiCaseRows] = await Promise.all(requests);
setEndpoints(endpointRows);
setEnvironments(environmentRows);
setApiTestCases(apiCaseRows);
setSelectedEnvironmentId(environmentRows[0]?.id ?? "");

if (scenarioId) {
  applyScenario(await getApiAutomationScenario(projectId, scenarioId));
}
```

加载失败时显示 toast，并在页面主体显示“场景加载失败”与“返回场景列表”按钮。加载完成前显示带 `Loader2` 的加载状态。

- [ ] **Step 3: Support adding and reordering draft steps**

`addScenarioStep` 不再要求已有后端场景：

```tsx
function addScenarioStep(caseId: string) {
  const testCase = apiTestCases.find((item) => item.id === caseId);
  if (!testCase) return;
  const id = `apistep-${crypto.randomUUID()}`;
  setScenarioSteps((current) => [
    ...current,
    {
      id,
      scenario_id: scenario?.id ?? "",
      project_id: projectId,
      endpoint_id: testCase.endpoint_id,
      api_test_case_id: testCase.id,
      step_order: current.length,
      name: testCase.title,
      request_overrides: {},
      bindings: [],
      extractors: [],
      assertions: [],
      on_failure: "stop",
      enabled: true,
      created_at: "",
      updated_at: "",
    },
  ]);
  setActiveScenarioStepId(id);
}
```

复用当前 `updateScenarioStep`、`moveScenarioStep`、步骤删除和 JSON 字段编辑行为。

- [ ] **Step 4: Implement create-on-first-save and update-on-later-save**

先校验名称和变量 JSON，再根据模式保存：

```tsx
async function saveScenario(showToast = true) {
  const name = scenarioName.trim();
  if (!name) {
    throw new Error("请填写场景名称");
  }
  const variables = parseJsonObject(scenarioVariablesText, "场景变量");
  let target = scenario;

  if (!target) {
    target = await createApiAutomationScenario(projectId, {
      name,
      description: scenarioDescription.trim(),
      variables,
    });
  } else {
    target = await updateApiAutomationScenario(projectId, target.id, {
      name,
      description: scenarioDescription.trim(),
      variables,
    });
  }

  const saved = await replaceApiAutomationScenarioSteps(
    projectId,
    target.id,
    scenarioSteps.map((step, index) => ({
      id: step.id,
      api_test_case_id: step.api_test_case_id,
      endpoint_id: step.endpoint_id,
      step_order: index,
      name: step.name,
      request_overrides: step.request_overrides,
      bindings: step.bindings,
      extractors: step.extractors,
      assertions: step.assertions,
      on_failure: step.on_failure,
      enabled: step.enabled,
    })),
  );

  applyScenario(saved);
  setScenarioValidation(null);
  if (isNew) {
    router.replace(`/projects/${projectId}/automation/api/scenarios/${saved.id}`);
  }
  if (showToast) toast.success(scenario ? "场景修改已保存" : "场景已创建");
  return saved;
}
```

为避免首次保存后闭包仍判断 `isNew`，实际实现应以 `scenario === null` 的保存前快照 `const creating = !scenario` 决定跳转和 toast。

- [ ] **Step 5: Preserve validation, publishing, and execution**

- 校验：先 `saveScenario(false)`，使用返回的 `saved.id` 调用校验，确保新建模式也能在一次点击中完成保存与校验。
- 发布：先保存，再以返回 ID 发布并 `applyScenario(published)`。
- 运行：仅当 `scenario?.status === "ready"` 且选择环境时启用；创建运行后跳转：

```tsx
router.push(`/projects/${projectId}/automation/api?tab=runs&run=${created.id}`);
```

同时调用 `notifyAiTaskStarted()`，不在编辑器内复制运行详情弹窗。

- [ ] **Step 6: Render the focused two-column editor**

顶部操作区包括：

```tsx
<Button asChild size="sm" variant="ghost">
  <Link href={`/projects/${projectId}/automation/api?tab=scenarios`}>
    <ArrowLeft className="size-4" />
    返回场景列表
  </Link>
</Button>
```

右侧依次显示环境选择、保存、校验、发布、运行。新建未保存时校验、发布、运行禁用；保存始终可用。主体使用：

```tsx
<div className="grid min-h-[620px] lg:grid-cols-[minmax(300px,0.9fr)_minmax(420px,1.1fr)]">
```

左栏复用当前“执行步骤”区域，右栏复用当前场景基础信息、验证结果和步骤 JSON 编辑区域。删除场景按钮不迁移到编辑器。

- [ ] **Step 7: Run the editor lifecycle contract**

Run:

```bash
cd apps/frontend
node --test --test-name-pattern="scenario editor|scenario api client" tests/api-automation-scenario-contract.test.mjs
```

Expected: PASS。

---

### Task 4: Add New And Edit Route Pages

**Files:**
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/scenarios/new/page.tsx`
- Create: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/scenarios/[scenarioId]/page.tsx`
- Test: `apps/frontend/tests/api-automation-scenario-contract.test.mjs`

**Interfaces:**
- Consumes: `ApiScenarioEditor`、`PageShell`、`useProjectName`。
- Produces: 两个可直接刷新和访问的 App Router 页面。

- [ ] **Step 1: Create the new scenario page**

```tsx
"use client";

import { useParams } from "next/navigation";

import { ApiScenarioEditor } from "@/components/ai-testing/api-automation/api-scenario-editor";
import { PageShell } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function NewApiScenarioPage() {
  const params = useParams<{ projectId: string }>();
  const projectName = useProjectName(params.projectId);

  return (
    <PageShell
      breadcrumbs={[
        { label: "项目工作区" },
        { label: "项目", href: "/projects" },
        { label: projectName, href: `/projects/${params.projectId}` },
        { label: "接口自动化", href: `/projects/${params.projectId}/automation/api?tab=scenarios` },
        { label: "新建场景" },
      ]}
      description="组合接口用例、配置变量并定义执行顺序。"
      projectScope="project"
      title="新建接口场景"
    >
      <ApiScenarioEditor projectId={params.projectId} />
    </PageShell>
  );
}
```

- [ ] **Step 2: Create the edit scenario page**

```tsx
"use client";

import { useParams } from "next/navigation";

import { ApiScenarioEditor } from "@/components/ai-testing/api-automation/api-scenario-editor";
import { PageShell } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function EditApiScenarioPage() {
  const params = useParams<{ projectId: string; scenarioId: string }>();
  const projectName = useProjectName(params.projectId);

  return (
    <PageShell
      breadcrumbs={[
        { label: "项目工作区" },
        { label: "项目", href: "/projects" },
        { label: projectName, href: `/projects/${params.projectId}` },
        { label: "接口自动化", href: `/projects/${params.projectId}/automation/api?tab=scenarios` },
        { label: "编辑场景" },
      ]}
      description="维护场景步骤、变量、校验、发布和运行配置。"
      projectScope="project"
      title="编辑接口场景"
    >
      <ApiScenarioEditor projectId={params.projectId} scenarioId={params.scenarioId} />
    </PageShell>
  );
}
```

- [ ] **Step 3: Run the full scenario contract test**

Run:

```bash
cd apps/frontend
node --test tests/api-automation-scenario-contract.test.mjs
```

Expected: PASS，全部场景列表、路由、编辑器和 API 客户端契约通过。

---

### Task 5: Validate Formatting, Types, Build, And Browser Flow

**Files:**
- Modify only if validation exposes issues in files listed above.

**Interfaces:**
- Consumes: 完成后的场景列表和编辑路由。
- Produces: 可构建、可导航且不影响其他接口自动化页签的实现。

- [ ] **Step 1: Run Biome on changed frontend files**

Run:

```bash
cd apps/frontend
npx biome check \
  'src/app/(main)/projects/[projectId]/automation/api/page.tsx' \
  'src/app/(main)/projects/[projectId]/automation/api/scenarios/new/page.tsx' \
  'src/app/(main)/projects/[projectId]/automation/api/scenarios/[scenarioId]/page.tsx' \
  'src/components/ai-testing/api-automation/api-scenario-list.tsx' \
  'src/components/ai-testing/api-automation/api-scenario-editor.tsx' \
  'tests/api-automation-scenario-contract.test.mjs'
```

Expected: PASS，无格式或 lint 错误。

- [ ] **Step 2: Run the complete frontend contract suite**

Run:

```bash
cd apps/frontend
node --test tests/*.test.mjs
```

Expected: PASS；若存在与本次无关的既有失败，只记录，不修改无关模块。

- [ ] **Step 3: Build the frontend**

Run:

```bash
cd apps/frontend
npm run build
```

Expected: Next.js production build completes successfully，新增两个动态路由被正确编译。

- [ ] **Step 4: Verify the browser flow**

在本地前端已运行时使用浏览器验证：

1. 打开 `/projects/{projectId}/automation/api?tab=scenarios`，确认默认激活“场景编排”。
2. 确认列表包含搜索、批量选择、新建、编辑和删除。
3. 点击“新建场景”，确认 URL 进入 `/scenarios/new` 且后端列表数量未立即增加。
4. 填写名称并添加步骤，点击保存，确认 URL 被替换为 `/scenarios/{scenarioId}`。
5. 返回列表，确认新场景出现且步骤数、状态、更新时间正确。
6. 点击场景名称进入编辑页，确认刷新后数据仍可加载。
7. 校验、发布并选择环境运行，确认跳转到 `?tab=runs&run={runId}` 并打开运行详情。
8. 返回场景列表执行单条删除和批量删除，确认列表与选择状态刷新。

- [ ] **Step 5: Review the final diff**

Run:

```bash
git diff --check
git diff --stat
```

Expected: 无空白错误；改动只覆盖计划中的场景列表、编辑器、路由、主页面和契约测试。
