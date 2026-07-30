import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const reportSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/performance-analysis-report.tsx", import.meta.url),
  "utf8",
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("performance analysis API exposes generation metadata", () => {
  assert.match(apiClientSource, /generation_mode: "" \| "ai_primary" \| "ai_repaired" \| "deterministic_fallback"/);
  assert.match(apiClientSource, /analysis_attempts: Array<Record<string, unknown>>/);
  assert.match(apiClientSource, /generation_warnings\?: Array<\{/);
});

test("fallback report displays warning and supports reanalysis", () => {
  assert.match(reportSource, /analysis\.generation_mode === "deterministic_fallback"/);
  assert.match(reportSource, /当前为基础性能报告/);
  assert.match(reportSource, /AI 根因分析及修复建议未生成/);
  assert.match(reportSource, /createPerformanceAnalysis/);
  assert.match(reportSource, /重新分析/);
});

test("fallback report hides AI findings and recommendations", () => {
  assert.match(reportSource, /!isFallback \? \(/);
  assert.match(reportSource, /优化与复测建议/);
  assert.match(reportSource, /诊断发现/);
});

test("performance report removes duplicated and low-value metadata", () => {
  assert.doesNotMatch(reportSource, /分析 v\{analysis\.analysis_version\}/);
  assert.doesNotMatch(reportSource, /指标 v\{metric\.schema_version/);
  assert.doesNotMatch(reportSource, /证据覆盖/);
  assert.doesNotMatch(reportSource, /title="测试有效性"/);
  assert.doesNotMatch(reportSource, /report\.capacity_summary/);
  assert.match(reportSource, /<summary[^>]*>生成信息<\/summary>/);
});

test("performance report hides empty analytical sections", () => {
  assert.match(reportSource, /objectives\.length \? \(/);
  assert.match(reportSource, /stageAnalysis\.length > 1 \? \(/);
  assert.match(reportSource, /showCapacityAnalysis \? \(/);
  assert.match(reportSource, /failureAnalysis\.length \? \(/);
  assert.match(reportSource, /findings\.length \? \(/);
  assert.match(reportSource, /recommendations\.length \? \(/);
});

test("performance report compresses AI findings and recommendations", () => {
  assert.doesNotMatch(reportSource, /置信度 \{Math\.round/);
  assert.doesNotMatch(reportSource, /recommendation\.expected_effect/);
  assert.match(reportSource, /\.slice\(0, 3\)/);
  assert.match(reportSource, /title="数据限制"/);
});
