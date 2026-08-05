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
  assert.match(pageSource, /selectedCount=\{selectedAssetRows\.length\}/);
  assert.match(pageSource, /onBatchDelete=\{\(\) => requestDelete\(selectedAssetRows\)\}/);
  assert.match(pageSource, /aria-label="选择全部 UI 自动化用例"/);
  assert.match(pageSource, /toggleAllAssets\(Boolean\(checked\)\)/);
  assert.match(pageSource, /selection\.toggleOne\(row\.id, Boolean\(checked\)\)/);
  assert.match(pageSource, /<div className="overflow-x-auto rounded-lg border">/);
  assert.match(pageSource, />用例名称<\/TableHead>/);
  assert.match(pageSource, />所属项目<\/TableHead>/);
  assert.doesNotMatch(pageSource, />入口路径<\/TableHead>/);
  assert.match(pageSource, />步骤数<\/TableHead>/);
  assert.match(pageSource, />更新时间<\/TableHead>/);
  assert.match(pageSource, /formatDateTime\(updatedAtForRow\(row\) \|\| null\)/);
  assert.match(pageSource, /placeholder="搜索用例名称、所属项目或状态"/);
  assert.match(pageSource, /<TableHead className="w-20">操作<\/TableHead>/);
  assert.match(pageSource, /<RowActions/);
  assert.match(pageSource, /label: "查看详情"[\s\S]*?icon: Eye/);
  assert.match(pageSource, /label: "执行"[\s\S]*?icon: Play/);
  assert.match(pageSource, /label: "删除"[\s\S]*?icon: Trash2[\s\S]*?destructive: true/);
  assert.match(pageSource, /<AlertDialogTitle>删除 UI 自动化资产？<\/AlertDialogTitle>/);
  assert.doesNotMatch(pageSource, /<FieldLabel>项目<\/FieldLabel>/);
  assert.doesNotMatch(pageSource, /<FieldLabel>运行环境<\/FieldLabel>/);
});

test("UI automation asset list does not depend on removed page exploration operations", () => {
  assert.doesNotMatch(pageSource, /page-exploration\/projects\/\$\{project\.id\}\/operations/);
  assert.doesNotMatch(pageSource, /operationsArtifact/);
  assert.match(pageSource, /listUiAutomationAssets\(project\.id\)/);
  assert.match(pageSource, /apiRequest<ApiTestCaseSet\[]>[\s\S]*?\.catch\(\(\) => \[\]\)/);
  assert.match(pageSource, /apiRequest<ApiManualTestCase\[]>[\s\S]*?\.catch\(\(\) => \[\]\)/);
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
  assert.match(pageSource, /generationRun\.target_asset_id === asset\.id/);
  assert.match(pageSource, /!generationRun\.target_asset_id/);
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
  assert.match(apiClientSource, /export function createUiAutomationRevisionRun/);
  assert.match(apiClientSource, /\/assets\/\$\{assetId\}\/revision-runs/);
  assert.match(apiClientSource, /export function getUiAutomationGenerationRun/);
  assert.match(apiClientSource, /export function createUiAutomationExecutionRun/);
  assert.match(apiClientSource, /export function getUiAutomationExecutionRun/);
  assert.match(apiClientSource, /export function getUiAutomationAsset/);
  assert.match(apiClientSource, /export function deleteUiAutomationAsset/);
  assert.match(apiClientSource, /export function listUiAutomationAssetGenerationRuns/);
  assert.match(apiClientSource, /export function listUiAutomationAssetExecutionRuns/);
  assert.match(apiClientSource, /export function getUiAutomationRunLogs/);
  assert.match(apiClientSource, /export function getUiAutomationRunDetail/);
  assert.match(apiClientSource, /export function getUiAutomationRunEvents/);
  assert.match(apiClientSource, /export function getUiAutomationLiveView/);
  assert.match(apiClientSource, /export function stopUiAutomationExecutionRun/);
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

test("UI automation asset AI edit collects an instruction before submitting", () => {
  assert.match(detailSource, /AI 修改/);
  assert.match(detailSource, /<DialogTitle[^>]*>AI 修改自动化脚本<\/DialogTitle>/);
  assert.match(
    detailSource,
    /<FieldLabel[^>]*htmlFor="ui-automation-revision-instruction"[^>]*>[\s\S]*?修改要求[\s\S]*?<\/FieldLabel>/,
  );
  assert.match(detailSource, /placeholder="告诉 AI 需要怎样修改脚本"/);
  assert.match(detailSource, /修改完成后运行测试/);
  assert.match(detailSource, /开始修改/);
  assert.doesNotMatch(detailSource, /检测问题：/);
  assert.doesNotMatch(detailSource, /当前资产逻辑保持不变/);
  assert.match(detailSource, /reason_code: "user_requested_change"/);
  assert.match(detailSource, /instruction: revisionInstruction\.trim\(\)/);
  assert.match(detailSource, /run_after_revision: runAfterRevision/);
  assert.match(detailSource, /createUiAutomationRevisionRun/);
  assert.doesNotMatch(detailSource, /createUiAutomationGenerationRun\(projectId/);
});

test("UI automation asset detail keeps a compact header", () => {
  assert.doesNotMatch(detailSource, /UI \/ ASSET/);
  assert.doesNotMatch(detailSource, /复制资产 ID/);
  assert.doesNotMatch(detailSource, /这条测试现在走到哪里了？/);
  assert.doesNotMatch(detailSource, /title="刷新"/);
  assert.match(detailSource, /grid grid-cols-3 gap-2 lg:flex lg:flex-nowrap lg:justify-end/);
  assert.match(detailSource, /返回列表/);
  assert.match(detailSource, /AI 修改/);
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
  assert.match(runDetailSource, /artifacts\/screenshot/);
  assert.doesNotMatch(runDetailSource, /artifacts\/trace/);
  assert.doesNotMatch(runDetailSource, /artifacts\/video/);
  assert.doesNotMatch(runDetailSource, /<video/);
  assert.doesNotMatch(runDetailSource, /trace_path|video_path/);
  assert.match(runDetailSource, /运行日志/);
  assert.match(runDetailSource, /浏览器证据/);
  assert.match(runDetailSource, /参数与步骤结果/);
  assert.doesNotMatch(runDetailSource, /按参数实例查看每个业务步骤的执行结果。/);
  assert.match(runDetailSource, /apiRequest<ExplorationEnvironment\[\]>/);
  assert.match(runDetailSource, /<DetailValue label="运行环境" value={environmentName \|\| "加载中…"} \/>/);
  assert.match(
    runDetailSource,
    /<DetailValue label="执行人" mono value={run.created_by} \/>\s*<DetailValue label="运行 ID" mono value={run.id} \/>/,
  );
  assert.match(runDetailSource, /ordinal={start \+ visibleIndex \+ 1}/);
  assert.doesNotMatch(runDetailSource, /失败于 \$\{iteration\.failed_step_id\}/);
  assert.match(runDetailSource, /filteredIterations/);
  assert.match(runDetailSource, /selectedIteration/);
  assert.match(runDetailSource, /item\.status === "cancelled"/);
  assert.match(runDetailSource, /step\.status === "cancelled" && Boolean\(step\.started_at\)/);
  assert.match(runDetailSource, /执行中被停止/);
  assert.match(runDetailSource, /因运行停止未执行/);
  assert.match(runDetailSource, /旧版资产缺少业务步骤映射/);
  assert.match(runDetailSource, /step-artifacts/);
  assert.match(runDetailSource, /iteration\.error/);
  assert.match(runDetailSource, /该错误发生在首个业务步骤开始前/);
  assert.match(runDetailSource, /实时查看/);
  assert.match(runDetailSource, /浏览器操作过程/);
  assert.match(runDetailSource, /liveView\.stream_path/);
  assert.match(runDetailSource, /h-dvh w-screen max-w-none/);
  assert.match(runDetailSource, /liveView\.width/);
  assert.match(runDetailSource, /liveView\.height/);
  assert.match(runDetailSource, /停止此次运行？/);
  assert.match(runDetailSource, /停止运行/);
  assert.match(runDetailSource, /停止中…/);
  assert.match(runDetailSource, /stopUiAutomationExecutionRun/);
  assert.doesNotMatch(runDetailSource, /结构化结果/);
  assert.doesNotMatch(runDetailSource, /JSON\.stringify\(run\.result/);
});

test("UI automation run detail virtualizes large parameter result sets", () => {
  assert.match(runDetailSource, /VIRTUALIZATION_THRESHOLD = 100/);
  assert.match(runDetailSource, /iterations\.slice\(start, end\)/);
  assert.match(runDetailSource, /iterations\.length \* ITERATION_ROW_HEIGHT/);
});
