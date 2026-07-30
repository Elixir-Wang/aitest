import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const readSource = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

const automationPageSource = readSource("../src/app/(main)/projects/[projectId]/automation/api/page.tsx");
const scenarioListSource = readSource("../src/components/ai-testing/api-automation/api-scenario-list.tsx");
const scenarioEditorSource = readSource("../src/components/ai-testing/api-automation/api-scenario-editor.tsx");
const scenarioCanvasSource = readSource("../src/components/ai-testing/api-automation/api-scenario-canvas.tsx");
const scenarioEditorHookSource = readSource("../src/components/ai-testing/api-automation/use-api-scenario-editor.ts");
const scenarioAssetPickerSource = readSource(
  "../src/components/ai-testing/api-automation/api-scenario-asset-picker.tsx",
);
const scenarioStepConfigSource = readSource("../src/components/ai-testing/api-automation/api-scenario-step-config.tsx");
const scenarioVersionPanelSource = readSource(
  "../src/components/ai-testing/api-automation/api-scenario-version-panel.tsx",
);
const scenarioRunDrawerSource = readSource("../src/components/ai-testing/api-automation/api-scenario-run-drawer.tsx");
const newScenarioPageSource = readSource(
  "../src/app/(main)/projects/[projectId]/automation/api/scenarios/new/page.tsx",
);
const editScenarioPageSource = readSource(
  "../src/app/(main)/projects/[projectId]/automation/api/scenarios/[scenarioId]/page.tsx",
);
const clientSource = readSource("../src/lib/api-client.ts");

test("scenario tab renders a project-list style scenario list", () => {
  assert.match(automationPageSource, /ApiScenarioList/);
  assert.match(automationPageSource, /scenarios/);
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

test("scenario editor supports ordered steps, saving, validation, publishing, and execution", () => {
  assert.match(scenarioEditorSource, /执行链路/);
  assert.match(scenarioEditorSource, /从接口资产添加/);
  assert.match(scenarioEditorSource, /场景变量/);
  assert.match(scenarioEditorSource, /版本记录/);
  assert.match(scenarioEditorSource, /运行场景/);
  assert.match(scenarioEditorSource, /ApiScenarioAssetPicker/);
  assert.match(scenarioEditorSource, /ApiScenarioStepConfig/);
  assert.doesNotMatch(scenarioEditorSource, /listApiAutomationTestCases/);
  assert.match(scenarioEditorHookSource, /useApiScenarioEditor/);
  assert.match(scenarioEditorHookSource, /createApiAutomationScenario/);
  assert.match(scenarioEditorHookSource, /replaceApiAutomationScenarioSteps/);
  assert.match(scenarioEditorHookSource, /validateApiAutomationScenario/);
  assert.match(scenarioEditorHookSource, /publishApiAutomationScenario/);
  assert.match(scenarioEditorHookSource, /executeApiAutomationScenario/);
  assert.match(scenarioEditorHookSource, /listApiAutomationScenarioRevisions/);
  assert.match(scenarioEditorHookSource, /restoreApiAutomationScenarioRevision/);
  assert.match(scenarioEditorHookSource, /getApiAutomationRun/);
  assert.match(scenarioEditorHookSource, /getApiAutomationScenarioRunResult/);
  assert.match(scenarioEditorHookSource, /router\.replace/);
  assert.doesNotMatch(scenarioEditorHookSource, /listApiAutomationTestCases/);
  assert.match(scenarioAssetPickerSource, /搜索接口名称或路径/);
  assert.match(scenarioAssetPickerSource, /添加到链路/);
  assert.match(scenarioStepConfigSource, /请求配置/);
  assert.match(scenarioStepConfigSource, /响应提取/);
  assert.match(scenarioStepConfigSource, /字段类型/);
  assert.match(scenarioStepConfigSource, /基础结构/);
  assert.match(scenarioVersionPanelSource, /恢复为草稿/);
  assert.match(scenarioVersionPanelSource, /当前版本/);
  assert.match(scenarioRunDrawerSource, /回到步骤配置/);
  assert.match(scenarioRunDrawerSource, /请求/);
  assert.match(scenarioRunDrawerSource, /响应/);
  assert.match(scenarioRunDrawerSource, /变量/);
});

test("scenario editor provides a constrained canvas backed by the existing step model", () => {
  assert.match(scenarioEditorSource, /ApiScenarioCanvas/);
  assert.match(scenarioEditorSource, /orchestrationMode/);
  assert.match(scenarioEditorSource, /画布视图/);
  assert.match(scenarioEditorSource, /列表视图/);
  assert.match(scenarioCanvasSource, /@xyflow\/react/);
  assert.match(scenarioCanvasSource, /ReactFlow/);
  assert.match(scenarioCanvasSource, /MiniMap/);
  assert.match(scenarioCanvasSource, /steps\.length > 12/);
  assert.match(scenarioCanvasSource, /自动布局/);
  assert.match(scenarioEditorSource, /隐藏节点配置/);
  assert.match(scenarioEditorSource, /clamp\(360px,32vw,500px\)/);
  assert.match(scenarioEditorSource, /onClearSelection/);
  assert.match(scenarioCanvasSource, /展开节点库/);
  assert.match(scenarioCanvasSource, /paletteOpen/);
  assert.match(scenarioCanvasSource, /panOnScrollMode=\{PanOnScrollMode\.Free\}/);
  assert.match(scenarioCanvasSource, /zoomOnScroll=\{false\}/);
  assert.match(scenarioCanvasSource, /onPaneClick=\{onClearSelection\}/);
  assert.match(scenarioEditorSource, /onDeleteStep=\{\(stepId\)/);
  assert.doesNotMatch(scenarioCanvasSource, /NodeToolbar/);
  assert.match(scenarioCanvasSource, /删除节点/);
  assert.match(scenarioCanvasSource, /\{method\}[\s\S]*?删除节点/);
  assert.match(scenarioCanvasSource, /event\.key !== "Delete" && event\.key !== "Backspace"/);
  assert.match(scenarioCanvasSource, /!canvasRef\.current\?\.contains\(target\)/);
  assert.match(scenarioCanvasSource, /onDeleteStep\(pendingDeleteStep\.id\)/);
  assert.match(scenarioEditorHookSource, /draftVersionRef/);
  assert.match(scenarioEditorHookSource, /draftVersion === draftVersionRef\.current/);
  assert.match(scenarioCanvasSource, /hasAllPositions/);
  assert.match(scenarioCanvasSource, /buildCanvasGraph/);
  assert.match(scenarioCanvasSource, /ResizeObserver/);
  assert.match(scenarioCanvasSource, /resolveColumnCount/);
  assert.match(scenarioCanvasSource, /row % 2 === 0/);
  assert.match(scenarioCanvasSource, /orientCanvasNodes/);
  assert.match(scenarioCanvasSource, /inputPosition/);
  assert.match(scenarioCanvasSource, /outputPosition/);
  assert.match(scenarioCanvasSource, /MIN_READABLE_ZOOM = 0\.7/);
  assert.match(scenarioCanvasSource, /type: "straight"/);
  assert.match(scenarioCanvasSource, /animated: source !== "__start__" && source === activeStepId/);
  assert.doesNotMatch(scenarioCanvasSource, /type: "smoothstep"/);
  assert.doesNotMatch(scenarioCanvasSource, /rankdir: "LR"/);
  assert.match(scenarioCanvasSource, /h-full min-h-0 min-w-0/);
  assert.match(scenarioCanvasSource, /steps\.length/);
  assert.match(scenarioStepConfigSource, /minmax\(140px,0\.8fr\)/);
  assert.match(scenarioCanvasSource, /当前画布沿用现有步骤顺序/);
});

test("scenario editor hides the run footer until a run exists", () => {
  assert.match(scenarioEditorSource, /editor\.latestRunId \? \([\s\S]*?<footer/);
  assert.doesNotMatch(scenarioEditorSource, /尚未运行当前场景/);
  assert.doesNotMatch(scenarioEditorSource, /运行结果将在此处展开/);
});

test("scenario asset picker overrides the base dialog width on desktop", () => {
  assert.match(scenarioAssetPickerSource, /sm:max-w-2xl/);
});

test("scenario asset picker uses a compact grouped interface selector", () => {
  assert.match(scenarioAssetPickerSource, /选择分组/);
  assert.match(scenarioAssetPickerSource, /未找到匹配接口/);
  assert.match(scenarioAssetPickerSource, /ChevronRight/);
  assert.doesNotMatch(scenarioAssetPickerSource, /接口文档/);
  assert.doesNotMatch(scenarioAssetPickerSource, /请求参数/);
  assert.doesNotMatch(scenarioAssetPickerSource, /SelectTrigger/);
});

test("scenario api client exposes transactional step replacement and lifecycle endpoints", () => {
  assert.match(clientSource, /replaceApiAutomationScenarioSteps/);
  assert.match(clientSource, /method: "PUT"/);
  assert.match(clientSource, /\/api-scenarios\/\$\{scenarioId\}\/validate/);
  assert.match(clientSource, /\/api-scenarios\/\$\{scenarioId\}\/publish/);
  assert.match(clientSource, /\/api-scenarios\/\$\{scenarioId\}\/execute/);
  assert.match(clientSource, /confirm_asset_changes/);
  assert.match(clientSource, /source/);
  assert.match(clientSource, /listApiAutomationScenarioRevisions/);
  assert.match(clientSource, /restoreApiAutomationScenarioRevision/);
  assert.match(clientSource, /\/revisions\/\$\{revision\}\/restore/);
  assert.match(clientSource, /getApiAutomationScenarioRunResult/);
  assert.match(clientSource, /\/scenario-result/);
});
