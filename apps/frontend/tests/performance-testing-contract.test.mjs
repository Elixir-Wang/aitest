import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";

const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const sidebarSource = readFileSync(new URL("../src/navigation/sidebar/sidebar-items.ts", import.meta.url), "utf8");
const formSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/performance-test-form.tsx", import.meta.url),
  "utf8",
);
const listPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/performance-tests/page.tsx", import.meta.url),
  "utf8",
);
const allListPageSource = readFileSync(
  new URL("../src/app/(main)/performance-tests/page.tsx", import.meta.url),
  "utf8",
);
const globalCreatePageSource = readFileSync(
  new URL("../src/app/(main)/performance-tests/new/page.tsx", import.meta.url),
  "utf8",
);
const stageEditorSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/load-stage-editor.tsx", import.meta.url),
  "utf8",
);
const dataEditorSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/performance-data-editor.tsx", import.meta.url),
  "utf8",
);
const allListSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/all-performance-test-list.tsx", import.meta.url),
  "utf8",
);
const projectListSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/performance-test-list.tsx", import.meta.url),
  "utf8",
);
const scriptReviewSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/script-review.tsx", import.meta.url),
  "utf8",
);
const scriptPageSource = readFileSync(
  new URL(
    "../src/app/(main)/projects/[projectId]/performance-tests/[testId]/scripts/[scriptId]/page.tsx",
    import.meta.url,
  ),
  "utf8",
);
const detailSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/performance-test-detail.tsx", import.meta.url),
  "utf8",
);

test("performance testing sidebar entry is enabled and project scoped", () => {
  assert.match(
    sidebarSource,
    /title: "性能测试",\s*url: "\/projects\/:projectId\/performance-tests",\s*icon: Gauge,\s*projectScoped: true,/,
  );
  assert.doesNotMatch(sidebarSource, /title: "性能测试",[\s\S]{0,160}?comingSoon: true/);
});

test("performance testing API client exposes preview and CRUD contracts", () => {
  assert.match(apiClientSource, /export function previewPerformanceRequest/);
  assert.match(apiClientSource, /performance-tests\/request-preview/);
  assert.match(apiClientSource, /export function listPerformanceTests/);
  assert.match(apiClientSource, /export function createPerformanceTest/);
  assert.match(apiClientSource, /export function deletePerformanceTest/);
});

test("performance create form reuses endpoint and environment assets without secret fields", () => {
  assert.match(formSource, /apiRequest<ApiProject\[]>\("\/projects"\)/);
  assert.match(formSource, /listApiAutomationEndpoints\(selectedProjectId\)/);
  assert.match(formSource, /listApiAutomationEnvironments\(selectedProjectId\)/);
  assert.match(formSource, /previewPerformanceRequest\(selectedProjectId/);
  assert.match(formSource, /固定负载/);
  assert.match(formSource, /手动梯度/);
  assert.match(formSource, /压力测试/);
  assert.match(formSource, /峰值测试/);
  assert.match(formSource, /耐久测试/);
  assert.doesNotMatch(formSource, /LoadProfileRail/);
  assert.doesNotMatch(formSource, /password|token|cookie|api_key/i);
});

test("performance request configuration is endpoint-only and hides empty sections", () => {
  assert.doesNotMatch(formSource, /请求数据来源/);
  assert.doesNotMatch(formSource, /listApiAutomationTestCases/);
  assert.doesNotMatch(formSource, /sourceCaseId|source_api_test_case_id|endpointCases|changeSourceCase/);
  assert.doesNotMatch(apiClientSource, /source_api_test_case_id/);
  assert.match(formSource, /hasEntries\(preview\?\.request_config\.path_parameters\)/);
  assert.match(formSource, /hasEntries\(preview\?\.request_config\.query_parameters\)/);
  assert.match(formSource, /hasEntries\(preview\?\.request_config\.headers\)/);
  assert.match(formSource, /hasBody\(preview\?\.request_config\.body\)/);
});

test("global performance create route owns project selection and structured editors", () => {
  assert.match(globalCreatePageSource, /<PerformanceTestForm/);
  assert.match(globalCreatePageSource, /useSearchParams/);
  assert.match(stageEditorSource, /目标用户数/);
  assert.match(stageEditorSource, /保持时长/);
  assert.match(dataEditorSource, /JSON 数据列表/);
  assert.match(dataEditorSource, /CSV 文件/);
});

test("performance list route renders the project-scoped list component", () => {
  assert.match(listPageSource, /<PerformanceTestList projectId=\{params\.projectId\} \/>/);
});

test("global performance route renders the cross-project task list", () => {
  assert.match(allListPageSource, /projectScope="all"/);
  assert.match(allListPageSource, /<AllPerformanceTestList \/>/);
});

test("performance lists use native shell sections and expose creation actions", () => {
  assert.match(allListSource, /ShellSection/);
  assert.match(allListSource, /新建性能测试/);
  assert.match(allListSource, /performance-tests\/new/);
  assert.match(projectListSource, /ShellSection/);
  assert.match(projectListSource, /createLabel="新建性能测试"/);
});

test("performance script API and review route support generation, edits, and confirmation", () => {
  assert.match(apiClientSource, /export function generatePerformanceScript/);
  assert.match(apiClientSource, /export function updatePerformanceScriptConfiguration/);
  assert.match(apiClientSource, /export function confirmPerformanceScript/);
  assert.match(scriptPageSource, /<ScriptReview/);
  assert.match(scriptReviewSource, /validation_status/);
  assert.match(scriptReviewSource, /确认脚本/);
  assert.match(detailSource, /generatePerformanceScript/);
});

test("confirmed performance script launches the native Locust UI", () => {
  assert.match(apiClientSource, /export function createPerformanceRun/);
  assert.match(apiClientSource, /export function createLocustUiSession/);
  assert.match(apiClientSource, /locust_ui_path/);
  assert.match(scriptReviewSource, /启动 Locust UI/);
  assert.match(scriptReviewSource, /createLocustUiSession/);
  assert.match(scriptReviewSource, /window\.open\(session\.url/);
});

test("performance run workspace and stats UI are gone", () => {
  assert.equal(
    existsSync(new URL("../src/components/ai-testing/performance-testing/run-workspace.tsx", import.meta.url)),
    false,
  );
  assert.equal(
    existsSync(
      new URL("../src/app/(main)/projects/[projectId]/performance-test-runs/[runId]/page.tsx", import.meta.url),
    ),
    false,
  );
  assert.doesNotMatch(apiClientSource, /PerformanceRunStats/);
  assert.doesNotMatch(apiClientSource, /PerformanceAnalysis/);
  assert.doesNotMatch(apiClientSource, /streamPerformanceRun/);
  assert.doesNotMatch(detailSource, /listPerformanceRuns/);
});
