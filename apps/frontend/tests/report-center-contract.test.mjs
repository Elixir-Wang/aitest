import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/reports/page.tsx", import.meta.url), "utf8");
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("report center loads generated performance reports from the backend index", () => {
  assert.match(apiClientSource, /export type ReportCenterItem/);
  assert.match(apiClientSource, /export function listReportCenterItems/);
  assert.match(apiClientSource, /\/reports\?\$\{params\.toString\(\)\}/);
  assert.match(pageSource, /listReportCenterItems\(\)/);
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
  assert.match(pageSource, /选择全部性能报告/);
  assert.match(pageSource, /onBatchDelete/);
  assert.match(pageSource, /删除选中的报告/);
  assert.match(pageSource, /deleteReportCenterItem/);
});
