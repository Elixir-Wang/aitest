import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/automation/api/page.tsx", import.meta.url), "utf8");
const projectPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
  "utf8",
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const sidebarSource = readFileSync(new URL("../src/navigation/sidebar/sidebar-items.ts", import.meta.url), "utf8");
const taskRunningIndicatorSource = readFileSync(
  new URL("../src/components/ai-testing/task-running-indicator.tsx", import.meta.url),
  "utf8",
);

test("api automation interface-set list uses requested create and count copy", () => {
  assert.match(pageSource, /createLabel="新建接口集"/);
  assert.match(pageSource, /<DialogTitle>\{editingSet \? "修改接口集" : "新建接口集"\}<\/DialogTitle>/);
  assert.match(pageSource, /<TableHead>接口数量<\/TableHead>/);
  assert.doesNotMatch(pageSource, /createLabel="新建接口用例集"/);
  assert.doesNotMatch(pageSource, /<DialogTitle>新建接口用例集<\/DialogTitle>/);
  assert.doesNotMatch(pageSource, /<TableHead>用例数量<\/TableHead>/);
});

test("api automation interface-set list removes project and status columns", () => {
  assert.doesNotMatch(pageSource, /<TableHead>项目<\/TableHead>/);
  assert.doesNotMatch(pageSource, /<TableHead>状态<\/TableHead>/);
  assert.doesNotMatch(pageSource, /projectNameById\.get\(item\.project_id\) \?\? item\.project_id/);
  assert.doesNotMatch(pageSource, /<Badge variant="secondary">\{statusLabel\(item\.status\)\}<\/Badge>/);
});

test("api automation interface-set name and row actions support entering and editing", () => {
  assert.match(
    pageSource,
    /<Link\s+className="block truncate hover:underline"\s+href=\{`\/projects\/\$\{item\.project_id\}\/automation\/api\?set=\$\{item\.id\}`\}\s+title=\{item\.name\}/,
  );
  assert.match(pageSource, /href: `\/projects\/\$\{item\.project_id\}\/automation\/api\?set=\$\{item\.id\}`/);
  assert.doesNotMatch(pageSource, /router\.push\(`\/projects\/\$\{item\.project_id\}\/automation\/api/);
  assert.match(pageSource, /label: "修改"/);
  assert.match(pageSource, /icon: Pencil/);
  assert.match(pageSource, /onSelect: \(\) => openEditDialog\(item\)/);
  assert.doesNotMatch(pageSource, /label: "删除"/);
  assert.doesNotMatch(pageSource, /icon: Trash2/);
  assert.match(pageSource, /<DialogTitle>\{editingSet \? "修改接口集" : "新建接口集"\}<\/DialogTitle>/);
});

test("api client exposes api automation case-set update contract", () => {
  assert.match(apiClientSource, /export function updateApiAutomationCaseSet/);
  assert.match(apiClientSource, /`\/projects\/\$\{projectId\}\/api-case-sets\/\$\{setId\}`/);
  assert.match(apiClientSource, /method: "PATCH"/);
});

test("sidebar api automation entry opens the aggregate list", () => {
  assert.match(sidebarSource, /title: "接口自动化",\s*url: "\/automation\/api",\s*icon: TestTubeDiagonal,/);
  assert.doesNotMatch(sidebarSource, /title: "接口自动化",\s*url: "\/projects\/:projectId\/automation\/api"/);
});

test("project api automation breadcrumb uses selected interface-set name", () => {
  assert.match(projectPageSource, /const searchParams = useSearchParams\(\);/);
  assert.match(projectPageSource, /const selectedCaseSetId = searchParams\.get\("set"\);/);
  assert.match(projectPageSource, /listApiAutomationCaseSets\(projectId\)/);
  assert.match(projectPageSource, /\.\.\.\(selectedCaseSet \? \[\{ label: selectedCaseSet\.name \}\] : \[\]\)/);
  assert.doesNotMatch(projectPageSource, /\{ label: selectedCaseSet\?\.name \?\? projectName \}/);
});

test("project api automation endpoint detail keeps debug send and removes join-generation action", () => {
  assert.match(projectPageSource, /debugApiAutomationEndpoint/);
  assert.match(projectPageSource, /openEndpointDebugDialog\(activeEndpoint\)/);
  assert.match(projectPageSource, /<DialogTitle>接口调试<\/DialogTitle>/);
  assert.match(projectPageSource, /通过后端代理发送请求/);
  assert.match(projectPageSource, /handleDebugSend/);
  assert.doesNotMatch(projectPageSource, /toggleEndpoint\(activeEndpoint\.id\)/);
  assert.doesNotMatch(projectPageSource, /加入生成/);
  assert.doesNotMatch(projectPageSource, /deleteEndpoints\(\[activeEndpoint\.id\]\)/);
});

test("project api automation debug dialog keeps results visible with compact request body editor", () => {
  assert.match(
    projectPageSource,
    /grid max-h-\[calc\(100vh-2rem\)\] grid-rows-\[auto_minmax\(0,1fr\)_auto\] overflow-hidden/,
  );
  assert.match(projectPageSource, /className="max-h-64 min-h-0 overflow-y-auto font-mono text-xs"/);
  assert.match(projectPageSource, /rows=\{getTextareaRows\(debugForm\.bodyText, 3, 12\)\}/);
  assert.match(projectPageSource, /function getTextareaRows/);
  assert.doesNotMatch(projectPageSource, /className="min-h-44 font-mono text-xs"/);
});

test("project api automation endpoint groups are collapsible with count badges", () => {
  assert.match(projectPageSource, /expandedEndpointGroups/);
  assert.match(projectPageSource, /toggleEndpointGroup\(group\)/);
  assert.match(projectPageSource, /!\s*expandedEndpointGroups\.includes\(group\)/);
  assert.match(projectPageSource, /searchText\.trim\(\) \? false/);
  assert.match(projectPageSource, /aria-label=\{`\$\{group\} 分组/);
  assert.match(projectPageSource, /ChevronDown/);
  assert.match(projectPageSource, /bg-sky-100[\s\S]*text-sky-700/);
  assert.match(projectPageSource, /\{rows\.length\}/);
});

test("project api automation exposes interface environment after interface assets", () => {
  assert.match(
    projectPageSource,
    /const tabs = \["接口资产", "接口环境", "接口用例", "测试脚本", "运行记录", "场景编排"\];/,
  );
  assert.match(projectPageSource, /activeTab === "接口环境"/);
  assert.match(projectPageSource, /activeTab === "接口用例"/);
  assert.match(projectPageSource, /<ShellSection>/);
  assert.match(projectPageSource, /<ListToolbar/);
  assert.match(projectPageSource, /<Table>/);
  assert.match(projectPageSource, /<RowActions/);
  assert.match(projectPageSource, /新建接口环境/);
  assert.match(projectPageSource, /authTypeOptions/);
  assert.match(projectPageSource, /默认请求头（JSON）/);
  assert.doesNotMatch(projectPageSource, /<CardTitle className="text-base">环境详情<\/CardTitle>/);
});

test("project api automation uses selected environment for generate scripts and runs", () => {
  assert.match(projectPageSource, /const \[selectedEnvironmentId, setSelectedEnvironmentId\] = useState\(""\);/);
  assert.match(projectPageSource, /api_environment_id: selectedEnvironment\?\.id \?\? null/);
  assert.doesNotMatch(projectPageSource, /api_environment_id: environments\[0\]\?\.id \?\? null/);
  assert.match(apiClientSource, /export function updateApiAutomationEnvironment/);
  assert.match(apiClientSource, /export function deleteApiAutomationEnvironment/);
});

test("project api automation generation and execution notify the top running task indicator", () => {
  assert.match(taskRunningIndicatorSource, /"api_automation_generation_run"/);
  assert.match(taskRunningIndicatorSource, /"api_automation_run"/);
  assert.match(projectPageSource, /import \{ notifyAiTaskStarted \} from "@\/lib\/ai-task-events";/);
  assert.match(projectPageSource, /toast\.success\("接口用例生成任务已创建"\);\s*notifyAiTaskStarted\(\);/);
  assert.match(projectPageSource, /toast\.success\("执行任务已创建"\);\s*notifyAiTaskStarted\(\);/);
});

test("project api automation endpoint schema detail uses compact badges and response header", () => {
  assert.match(projectPageSource, /function ContentTypeBadge/);
  assert.match(projectPageSource, /rounded-md border bg-muted\/40 px-2 py-1 font-mono/);
  assert.match(projectPageSource, /md:grid-cols-\[minmax\(220px,1\.1fr\)_64px_64px_56px_minmax\(220px,1\.4fr\)\]/);
  assert.match(projectPageSource, /border-b bg-muted\/20 px-4 py-3/);
  assert.match(projectPageSource, /<ContentTypeBadge key=\{contentType\} value=\{contentType\} \/>/);
});
