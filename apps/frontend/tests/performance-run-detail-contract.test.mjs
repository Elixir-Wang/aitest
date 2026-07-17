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
const testDetailSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/performance-test-detail.tsx", import.meta.url),
  "utf8",
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");


test("performance run page is project-native and Chinese", () => {
  assert.equal(existsSync(pageUrl), true);
  assert.equal(existsSync(detailUrl), true);
  const detailSource = readFileSync(detailUrl, "utf8");
  assert.match(detailSource, /运行概览/);
  assert.match(detailSource, /请求统计/);
  assert.match(detailSource, /实时图表/);
  assert.match(detailSource, /失败请求/);
  assert.match(detailSource, /异常信息/);
  assert.match(detailSource, /运行日志/);
  assert.match(detailSource, /停止压测/);
});


test("performance test launch navigates to the project-native run page", () => {
  assert.match(apiClientSource, /export function getPerformanceRun/);
  assert.match(apiClientSource, /export function getPerformanceRunStats/);
  assert.match(apiClientSource, /export function stopPerformanceRun/);
  assert.match(testDetailSource, /performance-tests\/\$\{testId\}\/runs\/\$\{run\.id\}/);
  assert.doesNotMatch(testDetailSource, /window\.open/);
  assert.doesNotMatch(testDetailSource, /createLocustUiSession/);
});


test("performance run uses SSE first and polling fallback", () => {
  const detailSource = readFileSync(detailUrl, "utf8");
  assert.match(apiClientSource, /export async function streamPerformanceRun/);
  assert.match(detailSource, /streamPerformanceRun\(projectId, runId/);
  assert.match(detailSource, /startPollingFallback/);
  assert.match(detailSource, /AbortController/);
});
