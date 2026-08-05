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
const editPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/performance-tests/[testId]/edit/page.tsx", import.meta.url),
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
const paramsDialogSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/performance-test-params-dialog.tsx", import.meta.url),
  "utf8",
);
const sseMetricsConfigSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/performance-sse-metrics-config.tsx", import.meta.url),
  "utf8",
);
const scriptPageSource = readFileSync(
  new URL(
    "../src/app/(main)/projects/[projectId]/performance-tests/[testId]/scripts/[scriptId]/page.tsx",
    import.meta.url,
  ),
  "utf8",
);
const runDetailSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/performance-run-detail.tsx", import.meta.url),
  "utf8",
);
const locustConsoleSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/locust-console.tsx", import.meta.url),
  "utf8",
);
const detailPageUrl = new URL(
  "../src/app/(main)/projects/[projectId]/performance-tests/[testId]/page.tsx",
  import.meta.url,
);
const detailComponentUrl = new URL(
  "../src/components/ai-testing/performance-testing/performance-test-detail.tsx",
  import.meta.url,
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

test("performance SSE metrics discover generic candidates and preserve unapplied drafts", () => {
  assert.match(apiClientSource, /export function generatePerformanceSseMetrics/);
  assert.match(apiClientSource, /performance-tests\/sse-metrics\/generate/);
  assert.match(apiClientSource, /export type PerformanceSseMetricCandidate/);
  assert.match(apiClientSource, /export type PerformanceSseMetricTiming/);
  assert.match(apiClientSource, /source_request_name: string \| null/);
  assert.match(apiClientSource, /event_facts: PerformanceSseEventFact\[]/);
  assert.match(apiClientSource, /result_status: "ready" \| "empty" \| "partial" \| "failed"/);
  assert.match(formSource, /<PerformanceSseMetricsConfig/);
  assert.match(sseMetricsConfigSource, /所属接口/);
  assert.match(sseMetricsConfigSource, /开始时间/);
  assert.match(sseMetricsConfigSource, /结束条件/);
  assert.match(sseMetricsConfigSource, /计算方式/);
  assert.match(sseMetricsConfigSource, /业务响应指标/);
  assert.match(sseMetricsConfigSource, /运行样本并发现指标/);
  assert.match(sseMetricsConfigSource, /SSE 指标配置/);
  assert.match(sseMetricsConfigSource, /sm:max-w-3xl/);
  assert.match(sseMetricsConfigSource, /查看生成结果/);
  assert.match(sseMetricsConfigSource, /暂存并关闭/);
  assert.match(sseMetricsConfigSource, /draftFingerprint/);
  assert.match(sseMetricsConfigSource, /请求配置已变化，请使用新请求重新验证/);
  assert.match(sseMetricsConfigSource, /推荐原因/);
  assert.match(sseMetricsConfigSource, /其他事件/);
  assert.match(sseMetricsConfigSource, /样本事件/);
  assert.match(sseMetricsConfigSource, /结束条件/);
  assert.match(sseMetricsConfigSource, /高级匹配规则/);
  assert.match(sseMetricsConfigSource, /指标名称/);
  assert.match(sseMetricsConfigSource, /SSE 事件类型/);
  assert.match(sseMetricsConfigSource, /JSON 字段路径/);
  assert.match(sseMetricsConfigSource, /期望值/);
  assert.match(sseMetricsConfigSource, /未命中时/);
  assert.match(sseMetricsConfigSource, /记录为缺失，不影响请求/);
  assert.match(sseMetricsConfigSource, /将请求标记为失败/);
  assert.match(sseMetricsConfigSource, /忽略本次指标/);
  assert.match(sseMetricsConfigSource, /查看命中事件/);
  assert.doesNotMatch(sseMetricsConfigSource, />记录为空</);
  assert.match(sseMetricsConfigSource, /命中.*次/);
  assert.match(sseMetricsConfigSource, /待验证/);
  assert.match(sseMetricsConfigSource, /重新验证/);
  assert.match(sseMetricsConfigSource, /if \(!result\) \{\s*void run\(\);\s*\}/);
  assert.match(sseMetricsConfigSource, /currentMetricIds/);
  assert.match(sseMetricsConfigSource, /currentMetricIds\.has\(candidate\.metric_id\)/);
  assert.match(sseMetricsConfigSource, /当前配置不会立即被覆盖/);
  assert.match(sseMetricsConfigSource, /end_rule: current\?\.end_rule \?\? null/);
  assert.doesNotMatch(sseMetricsConfigSource, /end_rule: generated\.end_rule_candidate\?\.match \?\? null/);
  assert.match(sseMetricsConfigSource, /启用推荐结束规则/);
  assert.match(sseMetricsConfigSource, /不启用结束规则/);
  assert.match(sseMetricsConfigSource, /移除结束规则/);
  assert.match(sseMetricsConfigSource, /setDraft\(\{ \.\.\.draft, end_rule: null \}\)/);
  assert.doesNotMatch(sseMetricsConfigSource, /generated\.warnings\.forEach/);
  assert.doesNotMatch(sseMetricsConfigSource, /识别 LLM 调用开始、首次回答/);
  assert.match(apiClientSource, /sse_metric_goals\?: PerformanceSseMetricGoal\[]/);
  assert.match(formSource, /SSE 事件指标目标/);
  assert.match(formSource, /P95 上限（ms）|percentile\.toUpperCase\(\)/);
  assert.match(formSource, /buildSseMetricGoals\(sse, sseGoalTargets\)/);
  assert.doesNotMatch(sseMetricsConfigSource, /Tabs|事件时间轴|JSONPath 自动补全/);
});

test("performance SSE metrics keep the generated candidate catalog after applying a selection", () => {
  const applyBlock = sseMetricsConfigSource.match(/function apply\(\) \{[\s\S]*?\n {2}\}\n\n {2}const hasPendingDraft/);

  assert.ok(applyBlock, "apply handler should exist");
  assert.doesNotMatch(applyBlock[0], /setResult\(null\)/);
  assert.doesNotMatch(applyBlock[0], /setSelectedKeys\(\[\]\)/);
  assert.match(
    sseMetricsConfigSource,
    /const hasPendingDraft = Boolean\(result && JSON\.stringify\(draft\) !== JSON\.stringify\(value\)\)/,
  );
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

test("performance load fields expose accessible hover descriptions", () => {
  assert.match(formSource, /function LoadConfigFieldLabel/);
  assert.match(formSource, /TooltipTrigger asChild/);
  assert.match(formSource, /CircleHelp/);
  assert.match(formSource, /aria-label=\{`\$\{label\}说明`\}/);
  assert.match(formSource, /压测需要启动的虚拟用户总数。每个用户会循环执行测试任务。/);
  assert.match(formSource, /每秒启动的虚拟用户数量，必须大于 0。/);
  assert.match(formSource, /从压测启动开始计算的总运行时间，包含用户逐步启动的爬升时间。/);
  assert.match(formSource, /用户完成一次任务后，再次执行前的最短等待时间，不能小于 0.1 秒。/);
  assert.match(formSource, /用户完成一次任务后，再次执行前的最长等待时间，不能小于最小等待时间。/);
  assert.match(formSource, /单个请求超过该时间仍未完成时，将被记录为超时失败。/);
});

test("performance create form does not preselect its identifying fields", () => {
  assert.match(formSource, /const \[selectedProjectId, setSelectedProjectId\] = useState\(""\)/);
  assert.match(formSource, /const \[endpointId, setEndpointId\] = useState\(""\)/);
  assert.match(formSource, /const \[environmentId, setEnvironmentId\] = useState\(""\)/);
  assert.match(formSource, /const \[name, setName\] = useState\(""\)/);
  assert.doesNotMatch(formSource, /initialProjectId/);
  assert.doesNotMatch(formSource, /setEndpointId\(endpointRows\[0\]/);
  assert.doesNotMatch(formSource, /setEnvironmentId\(environmentRows\[0\]/);
  assert.doesNotMatch(formSource, /setName\(\(current\).*result\.endpoint\.name/);
});

test("performance create form keeps its grid and actions shrinkable on narrow screens", () => {
  assert.match(formSource, /grid-cols-\[minmax\(0,1fr\)\]/);
  assert.match(formSource, /\[&>\*\]:min-w-0/);
  assert.match(formSource, /flex flex-wrap items-center justify-between gap-2 border-b/);
});

test("performance request configuration keeps endpoint fields scoped while both targets support transport", () => {
  assert.doesNotMatch(formSource, /请求数据来源/);
  assert.doesNotMatch(formSource, /listApiAutomationTestCases/);
  assert.doesNotMatch(formSource, /sourceCaseId|source_api_test_case_id|endpointCases|changeSourceCase/);
  assert.doesNotMatch(apiClientSource, /source_api_test_case_id/);
  assert.match(formSource, /hasEntries\(preview\?\.request_config\.path_parameters\)/);
  assert.match(formSource, /hasEntries\(preview\?\.request_config\.query_parameters\)/);
  assert.match(formSource, /hasEntries\(preview\?\.request_config\.headers\)/);
  assert.match(formSource, /hasBody\(preview\?\.request_config\.body\)/);
  assert.match(formSource, /scenario-sse-step/);
  assert.match(formSource, /scenarioRequestSteps/);
  assert.match(formSource, /scenario_step_id: targetType === "scenario" && transport === "sse"/);
  assert.match(sseMetricsConfigSource, /scenario_id: scenarioId, scenario_step_id: scenarioStepId/);
});

test("performance create form leaves success rules to the OpenAPI-backed server default", () => {
  assert.doesNotMatch(formSource, /成功状态码|successCodes|setSuccessRules|withStatusCodes|parseStatusCodes/);
  assert.doesNotMatch(formSource, /success_rules:/);
  assert.match(apiClientSource, /success_rules\?: PerformanceSuccessRule\[\]/);
  assert.match(formSource, /targetType === "endpoint" && \(!preview \|\| preview\.endpoint\.id !== endpointId\)/);
});

test("performance create form supports current API scenarios without version selection", () => {
  assert.match(apiClientSource, /target_type: "endpoint" \| "scenario"/);
  assert.match(apiClientSource, /scenario_id: string \| null/);
  assert.match(formSource, /listApiAutomationScenarios/);
  assert.match(formSource, /接口场景/);
  assert.match(
    formSource,
    /<SelectOption key=\{scenario\.id\} value=\{scenario\.id\}>\s*\{scenario\.name\}\s*<\/SelectOption>/,
  );
  assert.match(formSource, /target_type: targetType/);
  assert.match(formSource, /endpoint_id: targetType === "endpoint" \? endpointId : null/);
  assert.match(formSource, /scenario_id: targetType === "scenario" \? scenarioId : null/);
  assert.doesNotMatch(
    formSource,
    /直接使用场景当前保存版本|当前版本 v|个步骤。场景修改后请手动重新生成脚本|发布场景|版本选择|scenarioVersionId/,
  );
});

test("global performance create route owns project selection and structured editors", () => {
  assert.match(globalCreatePageSource, /<PerformanceTestForm/);
  assert.doesNotMatch(globalCreatePageSource, /useSearchParams|initialProjectId/);
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

test("performance edit route unwraps Next.js async params", () => {
  assert.match(editPageSource, /params: Promise<\{ projectId: string; testId: string \}>/);
  assert.match(editPageSource, /const \{ projectId, testId \} = await params/);
  assert.doesNotMatch(editPageSource, /"use client"/);
});

test("performance lists expose edit actions and regenerate scripts after saving", () => {
  assert.match(projectListSource, />操作<\/TableHead>/);
  assert.match(allListSource, />操作<\/TableHead>/);
  assert.match(projectListSource, /label: "编辑"/);
  assert.match(allListSource, /label: "编辑"/);
  assert.match(formSource, /updatePerformanceTest/);
  assert.match(formSource, /generatePerformanceScript\(selectedProjectId, saved\.id\)/);
});

test("performance lists expose created parameters in a reusable read-only dialog", () => {
  assert.match(projectListSource, /label: "查看参数"/);
  assert.match(allListSource, /label: "查看参数"/);
  assert.match(projectListSource, /<PerformanceTestParamsDialog/);
  assert.match(allListSource, /<PerformanceTestParamsDialog/);
  assert.match(paramsDialogSource, /创建参数/);
  assert.match(paramsDialogSource, /request_config: item\.request_config/);
  assert.match(paramsDialogSource, /load_config: item\.load_config/);
  assert.match(paramsDialogSource, /performance_goal: item\.performance_goal/);
  assert.match(paramsDialogSource, /<OneClipboard/);
});

test("stress mode configures automatic capacity discovery instead of manual stages", () => {
  assert.match(formSource, /stress_start_users/);
  assert.match(formSource, /stress_max_users/);
  assert.match(formSource, /stress_step_users/);
  assert.match(formSource, /stress_hold_seconds/);
  assert.match(formSource, /初始用户数/);
  assert.match(formSource, /最大用户数/);
  assert.match(formSource, /每级增加用户数/);
  assert.match(formSource, /每级观察时间/);
  assert.match(formSource, /mode === "stress"/);
});

test("deleting a performance test uses the system dialog and confirms all history will be removed", () => {
  assert.match(projectListSource, /将同时删除该条目下的全部压测历史/);
  assert.match(allListSource, /将同时删除该条目下的全部压测历史/);
  assert.match(projectListSource, /<AlertDialog/);
  assert.match(allListSource, /<AlertDialog/);
  assert.doesNotMatch(projectListSource, /window\.confirm/);
  assert.doesNotMatch(allListSource, /window\.confirm/);
});

test("performance script API and review route support generation, edits, and validation", () => {
  assert.match(apiClientSource, /export function generatePerformanceScript/);
  assert.match(apiClientSource, /export function updatePerformanceScriptConfiguration/);
  assert.doesNotMatch(apiClientSource, /confirmPerformanceScript/);
  assert.match(scriptPageSource, /<ScriptReview/);
  assert.match(scriptReviewSource, /结构化请求配置/);
  assert.match(scriptReviewSource, /只读 Locust 脚本/);
  assert.match(scriptReviewSource, /校验通过/);
  assert.doesNotMatch(scriptReviewSource, /生成来源：/);
  assert.doesNotMatch(scriptReviewSource, /接口场景配置/);
  assert.doesNotMatch(scriptReviewSource, /脚本使用生成时的场景当前保存版本/);
  assert.doesNotMatch(scriptReviewSource, /<details/);
  assert.match(scriptReviewSource, /<Sheet/);
  assert.match(scriptReviewSource, /执行顺序/);
  assert.doesNotMatch(scriptReviewSource, /确认脚本|已确认|重新确认/);
  assert.match(scriptReviewSource, /requestPreview\?\.request\.headers \?\? planRequest\.headers/);
  assert.match(scriptReviewSource, /step\.request(?:\?\.|\.)method/);
  assert.match(scriptReviewSource, /step\.request(?:\?\.|\.)path/);
  assert.match(scriptReviewSource, /查询参数/);
  assert.match(scriptReviewSource, /请求体/);
  assert.match(scriptReviewSource, /step\.request\?\.multipart_form/);
});

test("performance script review reuses the clipboard control and keeps JSON editors white", () => {
  assert.match(scriptReviewSource, /import \{ OneClipboard \} from "@\/components\/ui\/one-clipboard"/);
  assert.match(scriptReviewSource, /<OneClipboard copiedLabel="已复制" label="复制" text=\{script\.code\} \/>/);
  assert.match(scriptReviewSource, /className="bg-white font-mono text-xs dark:bg-\[#24292e\]"/);
});

test("validated performance script explicitly enters the Locust console", () => {
  assert.match(apiClientSource, /export function createPerformanceRun/);
  assert.match(apiClientSource, /export function getPerformanceRun/);
  assert.match(scriptReviewSource, /进入 Locust 控制台/);
  assert.match(scriptReviewSource, /performance-tests\/\$\{testId\}\/runs\/\$\{run\.id\}/);
  assert.doesNotMatch(scriptReviewSource, /createLocustUiSession|window\.open/);
});

test("performance test detail page is removed", () => {
  assert.equal(existsSync(detailPageUrl), false);
  assert.equal(existsSync(detailComponentUrl), false);
  assert.doesNotMatch(projectListSource, /performance-tests\/\$\{item\.id\}(?!\/)/);
  assert.doesNotMatch(allListSource, /performance-tests\/\$\{item\.id\}(?!\/)/);
});

test("project-native performance run workspace is present", () => {
  assert.equal(
    existsSync(
      new URL(
        "../src/app/(main)/projects/[projectId]/performance-tests/[testId]/runs/[runId]/page.tsx",
        import.meta.url,
      ),
    ),
    true,
  );
  assert.match(apiClientSource, /export function getPerformanceRun/);
  assert.match(apiClientSource, /export function getPerformanceRunStats/);
  assert.match(apiClientSource, /export function startPerformanceRun/);
  assert.match(apiClientSource, /export function stopPerformanceRun/);
  assert.match(runDetailSource, /LocustConsole/);
  assert.doesNotMatch(locustConsoleSource, /LocustStartPanel|Start new load test/);
  assert.match(locustConsoleSource, /统计/);
  assert.match(locustConsoleSource, /趋势图/);
  assert.match(locustConsoleSource, /失败请求/);
  assert.match(locustConsoleSource, /下载文件/);
});

test("Locust console presents run metrics without exposing the internal run ID", () => {
  assert.doesNotMatch(locustConsoleSource, />LOCUST</);
  assert.match(locustConsoleSource, /\/brand\/locust-mark\.svg/);
  assert.match(locustConsoleSource, /开始时间/);
  assert.match(locustConsoleSource, /持续时间/);
  assert.doesNotMatch(locustConsoleSource, /运行\s*\/\s*\{runId\}/);
  assert.match(locustConsoleSource, /grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6/);
  assert.match(locustConsoleSource, /function formatRunDuration/);
  assert.doesNotMatch(locustConsoleSource, /<LocustOverviewCharts/);
  assert.match(locustConsoleSource, /统计汇总/);
  assert.match(locustConsoleSource, /请求统计/);
  assert.match(locustConsoleSource, /异常分析/);
});

test("Locust request statistics use the compact success-rate table layout", () => {
  const statisticsTableSource = readFileSync(
    new URL("../src/components/ai-testing/performance-testing/locust-statistics-table.tsx", import.meta.url),
    "utf8",
  );
  assert.match(statisticsTableSource, /\["success_rate", "成功率"\]/);
  assert.doesNotMatch(statisticsTableSource, /\["average_response_time_ms", "平均响应时间"\]/);
  assert.match(statisticsTableSource, /\["p50_response_time_ms", "P50"\]/);
  assert.match(statisticsTableSource, /function SuccessRate/);
  assert.match(statisticsTableSource, /function RequestName/);
  assert.match(statisticsTableSource, /function methodBadgeClass/);
  assert.match(
    statisticsTableSource,
    /\["success_rate", "成功率"\],\s*\["requests_per_second", "RPS"\],\s*\["p50_response_time_ms", "P50"\]/,
  );
  assert.doesNotMatch(statisticsTableSource, /sticky right-0/);
  assert.match(statisticsTableSource, /min-w-\[1040px\]/);
  assert.match(statisticsTableSource, /max_response_time_ms: 118/);
  assert.match(statisticsTableSource, /requests_per_second: 64/);
  assert.match(statisticsTableSource, /table-fixed/);
  assert.doesNotMatch(statisticsTableSource, /size-2 rounded-full/);
});

test("performance AI analysis API supports approved repair and rerun", () => {
  assert.match(apiClientSource, /export type PerformanceAnalysis/);
  assert.match(apiClientSource, /export function createPerformanceAnalysis/);
  assert.match(apiClientSource, /export function getPerformanceAnalysis/);
  assert.match(apiClientSource, /export function listPerformanceRunAnalyses/);
  assert.match(apiClientSource, /performance-test-runs\/\$\{runId\}\/ai-analysis/);
  assert.match(apiClientSource, /performance-analysis\/\$\{analysisId\}/);
  assert.match(apiClientSource, /export function applyPerformanceAnalysis/);
  assert.match(apiClientSource, /apply-and-rerun/);
});
