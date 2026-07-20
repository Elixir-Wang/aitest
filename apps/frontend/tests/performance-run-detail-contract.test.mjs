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
const locustStartPanelUrl = new URL(
  "../src/components/ai-testing/performance-testing/locust-start-panel.tsx",
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
  const startPanelSource = readFileSync(locustStartPanelUrl, "utf8");
  assert.match(detailSource, /LocustConsole/);
  assert.match(startPanelSource, /Start new load test/);
  assert.match(consoleSource, /Statistics/);
  assert.match(consoleSource, /Charts/);
  assert.match(consoleSource, /Failures/);
  assert.match(consoleSource, /Exceptions/);
  assert.match(consoleSource, /Download Data/);
  assert.match(consoleSource, /Stop/);
  assert.match(consoleSource, /Reset Stats/);
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
  assert.match(consoleSource, /startPollingFallback/);
  assert.match(consoleSource, /AbortController/);
});
