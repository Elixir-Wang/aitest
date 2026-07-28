import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const pageUrl = new URL(
  "../src/app/(main)/projects/[projectId]/performance-tests/[testId]/runs/[runId]/page.tsx",
  import.meta.url,
);
const detailUrl = new URL(
  "../src/components/ai-testing/performance-testing/performance-run-detail.tsx",
  import.meta.url,
);
const locustConsoleUrl = new URL(
  "../src/components/ai-testing/performance-testing/locust-console.tsx",
  import.meta.url,
);
const locustChartsUrl = new URL(
  "../src/components/ai-testing/performance-testing/locust-charts-panel.tsx",
  import.meta.url,
);
const aiAnalysisDrawerUrl = new URL(
  "../src/components/ai-testing/performance-testing/performance-ai-analysis-drawer.tsx",
  import.meta.url,
);
const aiEvidenceListUrl = new URL(
  "../src/components/ai-testing/performance-testing/performance-ai-evidence-list.tsx",
  import.meta.url,
);
const aiAnalysisProgressUrl = new URL(
  "../src/components/ai-testing/performance-testing/performance-ai-analysis-progress.tsx",
  import.meta.url,
);
const aiReportPageUrl = new URL(
  "../src/app/(main)/projects/[projectId]/performance-tests/[testId]/runs/[runId]/analysis/[analysisId]/page.tsx",
  import.meta.url,
);
const aiReportUrl = new URL(
  "../src/components/ai-testing/performance-testing/performance-analysis-report.tsx",
  import.meta.url,
);
const testDetailUrl = new URL(
  "../src/components/ai-testing/performance-testing/performance-test-detail.tsx",
  import.meta.url,
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("performance run page hosts the Locust-native console", () => {
  assert.equal(existsSync(pageUrl), true);
  assert.equal(existsSync(detailUrl), true);
  assert.equal(existsSync(locustConsoleUrl), true);
  const detailSource = readFileSync(detailUrl, "utf8");
  const consoleSource = readFileSync(locustConsoleUrl, "utf8");
  assert.match(detailSource, /LocustConsole/);
  assert.doesNotMatch(consoleSource, /LocustStartPanel|Start new load test/);
  assert.match(consoleSource, /统计/);
  assert.match(consoleSource, /趋势图/);
  assert.match(consoleSource, /失败请求/);
  assert.match(consoleSource, /下载文件/);
  assert.match(consoleSource, /开始压测/);
  assert.match(consoleSource, /停止/);
  assert.match(consoleSource, /重置统计/);
  assert.match(consoleSource, /重新压测/);
  assert.match(consoleSource, /createPerformanceRun\(projectId, testId, run\.script_id\)/);
  assert.match(consoleSource, /startPerformanceRun\(projectId, testId, nextRun\.id, startDefaults\)/);
  assert.match(
    consoleSource,
    /router\.push\(`\/projects\/\$\{projectId\}\/performance-tests\/\$\{testId\}\/runs\/\$\{nextRun\.id\}`\)/,
  );
  assert.match(consoleSource, /const canReset = Boolean\(run && !\["created", "stopping"\]\.includes\(run\.status\)\)/);
  assert.match(consoleSource, /border-b px-4 py-4 sm:px-5/);
});

test("performance test detail is removed and run controls use project APIs", () => {
  assert.match(apiClientSource, /export function getPerformanceRun/);
  assert.match(apiClientSource, /export function getPerformanceRunStats/);
  assert.match(apiClientSource, /export function startPerformanceRun/);
  assert.match(apiClientSource, /export function stopPerformanceRun/);
  assert.match(apiClientSource, /export function resetPerformanceRunStats/);
  assert.equal(existsSync(testDetailUrl), false);
  assert.doesNotMatch(apiClientSource, /createLocustUiSession/);
});

test("performance run uses SSE first and polling fallback", () => {
  const consoleSource = readFileSync(locustConsoleUrl, "utf8");
  assert.match(apiClientSource, /export async function streamPerformanceRun/);
  assert.match(consoleSource, /streamPerformanceRun\(projectId, runId/);
  assert.match(consoleSource, /event !== "stats" \|\| !isRecord\(payload\.latest\)/);
  assert.match(consoleSource, /stats: \[\.\.\.current\.stats, latest\]\.slice\(-180\)/);
  assert.match(consoleSource, /request_stats: Array\.isArray\(payload\.request_stats\)/);
  assert.match(consoleSource, /startPollingFallback/);
  assert.match(consoleSource, /AbortController/);
});

test("performance run report downloads preserve API authentication", () => {
  const consoleSource = readFileSync(locustConsoleUrl, "utf8");
  assert.match(apiClientSource, /export function downloadPerformanceRunReport/);
  assert.match(
    apiClientSource,
    /export function downloadPerformanceRunReport[\s\S]*?return apiBlobRequest\([\s\S]*?performance-test-runs/,
  );
  assert.match(consoleSource, /downloadPerformanceRunReport\(projectId, runId, filename\)/);
  assert.match(consoleSource, /onClick=\{\(\) => void downloadReport\(report\.name\)\}/);
  assert.doesNotMatch(consoleSource, /href=\{performanceRunReportUrl\(projectId, runId, report\.name\)\}/);
});

test("performance run restores Locust-native chart history", () => {
  const consoleSource = readFileSync(locustConsoleUrl, "utf8");
  const chartsSource = readFileSync(locustChartsUrl, "utf8");
  assert.match(apiClientSource, /export function getPerformanceRunCharts/);
  assert.match(consoleSource, /getPerformanceRunCharts\(projectId, runId\)/);
  assert.match(consoleSource, /setSamples\(chartSamples\(nextCharts\.samples\)\)/);
  assert.match(chartsSource, /每秒请求数/);
  assert.match(chartsSource, /响应时间/);
  assert.match(chartsSource, /用户数/);
  assert.match(chartsSource, /failuresPerSecond/);
  assert.match(chartsSource, /p50ResponseTime/);
  assert.match(chartsSource, /p95ResponseTime/);
});

test("performance failure and exception tables use backend response fields", () => {
  const consoleSource = readFileSync(locustConsoleUrl, "utf8");
  assert.match(consoleSource, /\["request_name", "名称"\]/);
  assert.match(consoleSource, /\["reason", "错误信息"\]/);
  assert.match(consoleSource, /\["count", "次数"\]/);
  assert.match(consoleSource, /\["exception_type", "异常类型"\]/);
  assert.match(consoleSource, /\["message", "异常信息"\]/);
  assert.doesNotMatch(consoleSource, /\["occurrences", "次数"\]/);
  assert.doesNotMatch(consoleSource, /\["msg", "异常信息"\]/);
});

test("background performance refresh failures do not show request error toasts", () => {
  const consoleSource = readFileSync(locustConsoleUrl, "utf8");
  assert.match(consoleSource, /const refreshSilently = \(\) => refresh\(\)\.catch\(\(\) => undefined\)/);
  assert.match(consoleSource, /(?:void )?refreshSilently\(\);/);
  assert.doesNotMatch(consoleSource, /refresh\(\)\.catch\(\(error\) => !disposed && toast\.error/);
  assert.doesNotMatch(consoleSource, /refresh\(\)\.catch\(\(error\) => toast\.error/);
});

test("stopped performance runs expose an AI repair and rerun drawer", () => {
  const consoleSource = readFileSync(locustConsoleUrl, "utf8");
  assert.equal(existsSync(aiAnalysisDrawerUrl), true);
  const drawerSource = readFileSync(aiAnalysisDrawerUrl, "utf8");
  const evidenceSource = readFileSync(aiEvidenceListUrl, "utf8");
  const progressSource = readFileSync(aiAnalysisProgressUrl, "utf8");
  assert.match(consoleSource, /AI 分析/);
  assert.match(consoleSource, /PerformanceAiAnalysisDrawer/);
  assert.match(consoleSource, /TERMINAL_STATUSES\.has\(run\.status\)/);
  assert.match(drawerSource, /direction="right"/);
  assert.match(drawerSource, /data-\[vaul-drawer-direction=right\]:sm:max-w-3xl/);
  assert.match(drawerSource, /window\.setInterval/);
  assert.match(drawerSource, /function analysisFailureMessage/);
  assert.match(drawerSource, /触发模型接口 429 频率限制/);
  assert.match(drawerSource, /2000/);
  assert.match(evidenceSource, /已证实证据/);
  assert.match(evidenceSource, /推断与建议/);
  assert.match(progressSource, /status === "waiting_approval" \|\| status === "rejected"/);
  assert.match(drawerSource, /缺失证据/);
  assert.match(drawerSource, /审批后自动预检、修复配置并重新压测/);
  assert.match(drawerSource, /applyPerformanceAnalysis/);
  assert.match(drawerSource, /修复并重新压测/);
  assert.match(drawerSource, /预检失败，原配置未修改/);
  assert.doesNotMatch(drawerSource, /驳回/);
  assert.doesNotMatch(drawerSource, /应用并重新压测|确认修改源码/);
});

test("completed AI analysis opens a deterministic full report", () => {
  const drawerSource = readFileSync(aiAnalysisDrawerUrl, "utf8");
  assert.equal(existsSync(aiReportPageUrl), true);
  assert.equal(existsSync(aiReportUrl), true);
  const reportSource = readFileSync(aiReportUrl, "utf8");
  assert.match(drawerSource, /查看完整报告/);
  assert.match(drawerSource, /analysis\?\.analysis_status === "completed"/);
  assert.match(reportSource, /metric_snapshot/);
  assert.match(reportSource, /report_snapshot/);
  assert.match(reportSource, /性能目标/);
  assert.match(reportSource, /诊断发现/);
  assert.match(reportSource, /优化与复测建议/);
  assert.match(reportSource, /LineChart/);
  assert.doesNotMatch(reportSource, /createPerformanceAnalysis/);
});

test("Locust console exposes the latest ten run history records", () => {
  const consoleSource = readFileSync(locustConsoleUrl, "utf8");
  assert.match(apiClientSource, /export type PerformanceRunHistory/);
  assert.match(apiClientSource, /export function listPerformanceRunHistory/);
  assert.match(apiClientSource, /runs\/history/);
  assert.match(consoleSource, /历史记录/);
  assert.match(consoleSource, /保留最近 10 次/);
  assert.match(consoleSource, /listPerformanceRunHistory\(projectId, testId\)/);
  assert.match(
    consoleSource,
    /router\.push\(`\/projects\/\$\{projectId\}\/performance-tests\/\$\{testId\}\/runs\/\$\{historyRun\.id\}`\)/,
  );
});

test("deletable history records including ready runs expose an x delete action", () => {
  const consoleSource = readFileSync(locustConsoleUrl, "utf8");
  assert.match(apiClientSource, /export function deletePerformanceRun/);
  assert.match(consoleSource, /aria-label=\{`删除历史记录 \$\{historyRun\.id\}`\}/);
  assert.match(consoleSource, /deletePerformanceRun\(projectId, historyRun\.id\)/);
  assert.match(consoleSource, /DELETABLE_STATUSES = new Set<PerformanceRun\["status"\]>\(\[\s*"created",/);
  assert.match(consoleSource, /DELETABLE_STATUSES\.has\(historyRun\.status\)/);
  assert.doesNotMatch(consoleSource, /window\.confirm\("删除本次压测历史/);
});
