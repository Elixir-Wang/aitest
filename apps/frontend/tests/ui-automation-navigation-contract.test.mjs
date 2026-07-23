import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const sidebarSource = fs.readFileSync(new URL("../src/navigation/sidebar/sidebar-items.ts", import.meta.url), "utf8");
const pageSource = fs.readFileSync(new URL("../src/app/(main)/automation/ui/page.tsx", import.meta.url), "utf8");
const detailSource = fs.readFileSync(
  new URL("../src/components/ai-testing/ui-automation/ui-automation-asset-detail.tsx", import.meta.url),
  "utf8",
);
const runDetailSource = fs.readFileSync(
  new URL("../src/components/ai-testing/ui-automation/ui-automation-run-detail.tsx", import.meta.url),
  "utf8",
);
const apiClientSource = fs.readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("UI automation navigation is available", () => {
  const uiAutomationItem = sidebarSource.match(/title: "UI 自动化",[\s\S]*?url: "\/automation\/ui",[\s\S]*?\n\s*},/);

  assert.ok(uiAutomationItem, "UI 自动化导航项应存在");
  assert.doesNotMatch(uiAutomationItem[0], /comingSoon:\s*true/);
  assert.doesNotMatch(uiAutomationItem[0], /disabled:\s*true/);
});

test("UI automation asset list reuses the API automation list structure without dropping content", () => {
  assert.match(pageSource, /<ListToolbar/);
  assert.match(pageSource, /createLabel="新建 UI 自动化"/);
  assert.match(pageSource, /const selection = useLocalTableSelection<UiAutomationRow>/);
  assert.match(pageSource, /selectedCount=\{selection\.selectedCount\}/);
  assert.match(pageSource, /aria-label="选择全部 UI 自动化用例"/);
  assert.match(pageSource, /selection\.toggleAll\(Boolean\(checked\)\)/);
  assert.match(pageSource, /selection\.toggleOne\(row\.id, Boolean\(checked\)\)/);
  assert.match(pageSource, /<div className="overflow-hidden rounded-lg border">/);
  assert.match(pageSource, /<TableHead>用例名称<\/TableHead>/);
  assert.doesNotMatch(pageSource, /<TableHead>项目<\/TableHead>/);
  assert.match(pageSource, /<TableHead>入口路径<\/TableHead>/);
  assert.match(pageSource, /<TableHead>步骤<\/TableHead>/);
  assert.match(pageSource, /<TableHead className="w-20">执行<\/TableHead>/);
  assert.doesNotMatch(pageSource, /<FieldLabel>项目<\/FieldLabel>/);
  assert.doesNotMatch(pageSource, /<FieldLabel>运行环境<\/FieldLabel>/);
});

test("UI automation create dialog selects the real generation inputs", () => {
  assert.match(pageSource, /<DialogTitle>新建 UI 自动化<\/DialogTitle>/);
  assert.match(pageSource, /<FieldLabel htmlFor="ui-automation-project">项目<\/FieldLabel>/);
  assert.match(pageSource, /<FieldLabel htmlFor="ui-automation-source">测试用例<\/FieldLabel>/);
  assert.doesNotMatch(pageSource, /ui-automation-case-set/);
  assert.match(pageSource, /apiRequest<ApiManualTestCase\[]>\(`\/projects\/\$\{nextProjectId\}\/test-cases`\)/);
  assert.match(pageSource, /value=\{testCase\.id\}/);
  assert.match(pageSource, /item\.status === "approved"/);
  assert.doesNotMatch(pageSource, /createdRuns/);
  assert.doesNotMatch(pageSource, /用例集 ·/);
  assert.match(pageSource, /<FieldLabel htmlFor="ui-automation-environment">运行环境<\/FieldLabel>/);
  assert.match(pageSource, /createUiAutomationGenerationRun/);
  assert.match(pageSource, /listUiAutomationGenerationRuns/);
  assert.match(pageSource, /generationRun\.status !== "completed"/);
  assert.doesNotMatch(pageSource, /setRun\(createdRuns\[0\]/);
});

test("UI automation execution chooses an environment outside the aggregate list", () => {
  assert.match(pageSource, /<DialogTitle>执行 UI 自动化<\/DialogTitle>/);
  assert.match(pageSource, /<FieldLabel htmlFor="ui-automation-run-environment">运行环境<\/FieldLabel>/);
  assert.match(pageSource, /createUiAutomationExecutionRun/);
});

test("API client exposes UI automation asset, generation, and execution contracts", () => {
  assert.match(apiClientSource, /export function listUiAutomationAssets/);
  assert.match(apiClientSource, /export function listUiAutomationGenerationRuns/);
  assert.match(apiClientSource, /export function createUiAutomationGenerationRun/);
  assert.match(apiClientSource, /export function getUiAutomationGenerationRun/);
  assert.match(apiClientSource, /export function createUiAutomationExecutionRun/);
  assert.match(apiClientSource, /export function getUiAutomationExecutionRun/);
  assert.match(apiClientSource, /export function getUiAutomationAsset/);
  assert.match(apiClientSource, /export function listUiAutomationAssetGenerationRuns/);
  assert.match(apiClientSource, /export function listUiAutomationAssetExecutionRuns/);
  assert.match(apiClientSource, /export function getUiAutomationRunLogs/);
  assert.match(apiClientSource, /export function getUiAutomationLiveView/);
  assert.match(apiClientSource, /export function deleteUiAutomationExecutionRun/);
});

test("UI automation asset detail has overview and execution tabs", () => {
  assert.match(detailSource, /<TabsTrigger value="overview">概览<\/TabsTrigger>/);
  assert.match(detailSource, /<TabsTrigger value="runs">执行<\/TabsTrigger>/);
  assert.doesNotMatch(detailSource, /生成资产/);
  assert.match(detailSource, /searchParams\.get\("tab"\)/);
  assert.match(detailSource, /listUiAutomationAssetExecutionRuns/);
  assert.match(detailSource, /deleteUiAutomationExecutionRun/);
  assert.match(detailSource, /选择全部已完成的运行记录/);
  assert.match(detailSource, /删除选中的运行记录/);
  assert.doesNotMatch(detailSource, /listUiAutomationAssetFiles/);
});

test("UI automation asset detail keeps a compact header", () => {
  assert.doesNotMatch(detailSource, /UI \/ ASSET/);
  assert.doesNotMatch(detailSource, /复制资产 ID/);
  assert.doesNotMatch(detailSource, /这条测试现在走到哪里了？/);
  assert.doesNotMatch(detailSource, /title="刷新"/);
  assert.match(detailSource, /grid grid-cols-3 gap-2 lg:flex lg:flex-nowrap lg:justify-end/);
  assert.match(detailSource, /返回列表/);
  assert.match(detailSource, /重新生成/);
  assert.match(detailSource, /执行测试/);
  assert.match(detailSource, /text-lg tracking-tight sm:text-xl/);
  assert.doesNotMatch(detailSource, /资产可执行/);
  assert.doesNotMatch(detailSource, /生成校验/);
  assert.doesNotMatch(detailSource, /Locator 证据/);
  assert.doesNotMatch(detailSource, /运行结果/);
  assert.match(detailSource, /<FieldLabel htmlFor="ui-asset-run-environment">运行环境<\/FieldLabel>/);
  assert.match(detailSource, /apiRequest<ExplorationEnvironment\[\]>/);
  assert.doesNotMatch(detailSource, /<DialogTitle>选择运行环境<\/DialogTitle>/);
});

test("UI automation asset detail declares its environment panel before rendering it", () => {
  const declaration = detailSource.indexOf("function EnvironmentPanel");
  const component = detailSource.indexOf("export function UiAutomationAssetDetail");
  const usage = detailSource.indexOf("<EnvironmentPanel");

  assert.ok(declaration >= 0, "EnvironmentPanel 声明应存在");
  assert.ok(declaration < component, "EnvironmentPanel 应在主组件之前声明");
  assert.ok(usage > component, "主组件应渲染 EnvironmentPanel");
  assert.equal(detailSource.match(/function EnvironmentPanel/g)?.length, 1);
});

test("UI automation run detail exposes logs and browser evidence", () => {
  assert.match(runDetailSource, /getUiAutomationRunLogs/);
  assert.match(runDetailSource, /artifacts\/trace/);
  assert.match(runDetailSource, /artifacts\/screenshot/);
  assert.match(runDetailSource, /运行日志/);
  assert.match(runDetailSource, /浏览器证据/);
  assert.match(runDetailSource, /实时查看/);
  assert.match(runDetailSource, /浏览器操作过程/);
  assert.match(runDetailSource, /liveView\.stream_path/);
  assert.doesNotMatch(runDetailSource, /结构化结果/);
  assert.doesNotMatch(runDetailSource, /JSON\.stringify\(run\.result/);
});
