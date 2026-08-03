import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const apiPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
  "utf8",
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const batchComponentUrl = new URL(
  "../src/components/ai-testing/api-automation/api-batch-run-list.tsx",
  import.meta.url,
);

test("API automation exposes an independent batch run tab", () => {
  assert.match(apiPageSource, /批量运行/);
  assert.match(apiPageSource, /ApiBatchRunList/);
  assert.doesNotMatch(apiPageSource, /批量运行.*场景编排.*批量删除/);
});

test("batch run UI manages reusable scenario suites", () => {
  const source = readFileSync(batchComponentUrl, "utf8");
  assert.match(source, /listApiAutomationEnvironments/);
  assert.match(source, /listApiAutomationScenarios/);
  assert.match(source, /listApiAutomationScenarioSuites/);
  assert.match(source, /新建测试集/);
  assert.match(source, /编辑测试集/);
  assert.match(source, /runApiAutomationScenarioSuite/);
  assert.match(source, /deleteApiAutomationScenarioSuite/);
  assert.match(source, /selectedScenarioIds/);
  assert.match(source, /同一场景只能加入一次/);
  assert.doesNotMatch(source, /最近批次/);
  assert.doesNotMatch(source, /历史版本|原版本|选择版本/);
});

test("API client exposes scenario suite CRUD and repeat-run functions", () => {
  assert.match(apiClientSource, /export type ApiAutomationScenarioSuite/);
  assert.match(apiClientSource, /export type ApiAutomationBatchRun/);
  assert.match(apiClientSource, /export function createApiAutomationScenarioSuite/);
  assert.match(apiClientSource, /export function listApiAutomationScenarioSuites/);
  assert.match(apiClientSource, /export function updateApiAutomationScenarioSuite/);
  assert.match(apiClientSource, /export function deleteApiAutomationScenarioSuite/);
  assert.match(apiClientSource, /export function runApiAutomationScenarioSuite/);
  assert.match(apiClientSource, /export function listApiAutomationBatchRuns/);
  assert.match(apiClientSource, /export function getApiAutomationBatchRun/);
  assert.match(apiClientSource, /\/api-scenario-suites/);
  assert.match(apiClientSource, /\/runs/);
});
