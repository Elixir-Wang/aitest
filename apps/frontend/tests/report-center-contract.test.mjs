import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/reports/page.tsx", import.meta.url), "utf8");
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const apiDetailSource = readFileSync(
  new URL("../src/app/(main)/reports/api/[reportId]/page.tsx", import.meta.url),
  "utf8",
);

test("report center loads generated performance reports from the backend index", () => {
  assert.match(apiClientSource, /export type ReportCenterItem/);
  assert.match(apiClientSource, /export function listReportCenterItems/);
  assert.match(apiClientSource, /\/reports\?\$\{params\.toString\(\)\}/);
  assert.match(pageSource, /listReportCenterItems\("all", reportTypeForTab\(activeTab\)\)/);
  assert.doesNotMatch(pageSource, /const reports:.*= \[\]/);
});

test("report center defaults to performance and opens the frozen report detail", () => {
  assert.match(pageSource, /useState\("性能"\)/);
  assert.match(pageSource, /href: report\.href/);
  assert.match(pageSource, /verdictLabel\(report\.verdict\)/);
  assert.match(pageSource, /qualityLabel\(report\.quality_status\)/);
  assert.doesNotMatch(pageSource, /新建报告/);
});

test("report center distinguishes deterministic fallback reports", () => {
  assert.match(apiClientSource, /generation_mode: string/);
  assert.match(apiClientSource, /generation_status: "generating" \| "generated" \| "degraded" \| "failed"/);
  assert.match(pageSource, /generationStatusLabel\(report\.generation_status\)/);
  assert.match(pageSource, /degraded: "基础报告"/);
  assert.match(pageSource, /status === "degraded"/);
});

test("report center hides project, analysis version, and archive description", () => {
  assert.doesNotMatch(pageSource, /<TableHead>项目<\/TableHead>/);
  assert.doesNotMatch(pageSource, /\{report\.project_name\}<\/TableCell>/);
  assert.doesNotMatch(pageSource, /分析版本 V\{report\.analysis_version\}/);
  assert.doesNotMatch(pageSource, /报告由测试运行自动生成并按更新时间归档。/);
});

test("report center supports confirmed multi-select deletion", () => {
  assert.match(apiClientSource, /export function deleteReportCenterItem/);
  assert.match(pageSource, /选择全部\$\{activeTab\}报告/);
  assert.match(pageSource, /onBatchDelete/);
  assert.match(pageSource, /删除选中的报告/);
  assert.match(pageSource, /deleteReportCenterItem/);
  assert.match(pageSource, /deleteReportCenterItem\(id, reportType\)/);
});

test("report center loads completed API batch reports in the API tab", () => {
  assert.match(apiClientSource, /report_type: "performance" \| "api"/);
  assert.match(pageSource, /reportTypeForTab/);
  assert.match(pageSource, /listReportCenterItems\("all", reportTypeForTab\(activeTab\)\)/);
  assert.match(pageSource, /report\.scenario_count/);
  assert.match(pageSource, /report\.pass_rate/);
});

test("API report detail shows deterministic batch and scenario results", () => {
  assert.match(apiClientSource, /export function getApiBatchReportDetail/);
  assert.match(apiDetailSource, /getApiBatchReportDetail/);
  assert.match(apiDetailSource, /report\.counts\.passed/);
  assert.match(apiDetailSource, /report\.runs\.map/);
  assert.doesNotMatch(apiDetailSource, /历史版本|原版本|选择版本/);
});

test("API report detail omits the report center return button", () => {
  assert.doesNotMatch(apiDetailSource, /返回报告中心/);
  assert.doesNotMatch(apiDetailSource, /<ArrowLeft/);
  assert.doesNotMatch(apiDetailSource, /actions=/);
});

test("API report detail follows the performance report decision-first layout", () => {
  assert.match(apiDetailSource, /max-w-\[90rem\]/);
  assert.match(apiDetailSource, /resultAccentClass\(report\.result\)/);
  assert.match(apiDetailSource, /xl:grid-cols-\[minmax\(34rem,1\.15fr\)_minmax\(22rem,0\.85fr\)\]/);
  assert.match(apiDetailSource, /id="batch-metrics-heading"/);
  assert.match(apiDetailSource, /id="run-context-heading"/);
  assert.match(apiDetailSource, /mt-4 grid grid-cols-2 gap-x-8/);
  assert.match(apiDetailSource, /overflow-x-auto rounded-lg border/);
});
