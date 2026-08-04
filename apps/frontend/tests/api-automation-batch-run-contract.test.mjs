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
const suiteDialogUrl = new URL(
  "../src/components/ai-testing/api-automation/api-scenario-suite-dialog.tsx",
  import.meta.url,
);
const suiteDetailUrl = new URL(
  "../src/components/ai-testing/api-automation/api-scenario-suite-detail.tsx",
  import.meta.url,
);
const suitePageUrl = new URL(
  "../src/app/(main)/projects/[projectId]/automation/api/suites/[suiteId]/page.tsx",
  import.meta.url,
);

test("API automation exposes an independent batch run tab", () => {
  assert.match(apiPageSource, /批量运行/);
  assert.match(apiPageSource, /ApiBatchRunList/);
  assert.doesNotMatch(apiPageSource, /批量运行.*场景编排.*批量删除/);
});

test("batch run UI manages reusable scenario suites", () => {
  const source = readFileSync(batchComponentUrl, "utf8");
  const dialogSource = readFileSync(suiteDialogUrl, "utf8");
  const combinedSource = `${source}\n${dialogSource}`;
  assert.match(combinedSource, /listApiAutomationEnvironments/);
  assert.match(combinedSource, /listApiAutomationScenarios/);
  assert.match(combinedSource, /listApiAutomationScenarioSuites/);
  assert.match(combinedSource, /新建测试集/);
  assert.match(combinedSource, /编辑测试集/);
  assert.match(combinedSource, /runApiAutomationScenarioSuite/);
  assert.match(combinedSource, /deleteApiAutomationScenarioSuite/);
  assert.match(combinedSource, /selectedScenarioIds/);
  assert.match(combinedSource, /同一场景只能加入一次/);
  assert.match(dialogSource, /scenario\.revision > 0/);
  assert.match(dialogSource, /scenario\.published_hash/);
  assert.doesNotMatch(dialogSource, /scenario\.status|>状态</);
  assert.match(source, /automation\/api\/suites\/\$\{suite\.id\}/);
  assert.match(source, /查看测试集/);
  assert.doesNotMatch(source, /最近批次/);
  assert.doesNotMatch(source, /历史版本|原版本|选择版本/);
});

test("suite names open a dedicated detail page with ordered scenarios and run actions", () => {
  const detailSource = readFileSync(suiteDetailUrl, "utf8");
  const pageSource = readFileSync(suitePageUrl, "utf8");
  assert.match(pageSource, /ApiScenarioSuiteDetail/);
  assert.match(detailSource, /getApiAutomationScenarioSuite/);
  assert.match(detailSource, /执行计划/);
  assert.match(detailSource, /运行测试集/);
  assert.match(detailSource, /编辑测试集/);
  assert.match(detailSource, /查看完整报告/);
  assert.equal(detailSource.match(/查看(?:完整)?报告/g)?.length, 1);
  assert.match(detailSource, /updateApiAutomationScenarioSuite/);
  assert.match(detailSource, /切换运行环境/);
  assert.doesNotMatch(detailSource, /按既定顺序串行验证核心接口链路/);
  assert.doesNotMatch(detailSource, /aria-label="返回批量运行"/);
  assert.match(detailSource, /aria-label=\{`打开场景/);
  assert.doesNotMatch(detailSource, /scenario\.name\}[\s\S]{0,160}<ArrowUpRight/);
  assert.match(detailSource, /scenario\.position|index \+ 1/);
});

test("API client exposes scenario suite CRUD and repeat-run functions", () => {
  assert.match(apiClientSource, /export type ApiAutomationScenarioSuite/);
  assert.match(apiClientSource, /export type ApiAutomationBatchRun/);
  assert.match(apiClientSource, /export function createApiAutomationScenarioSuite/);
  assert.match(apiClientSource, /export function listApiAutomationScenarioSuites/);
  assert.match(apiClientSource, /export function getApiAutomationScenarioSuite/);
  assert.match(apiClientSource, /export function updateApiAutomationScenarioSuite/);
  assert.match(apiClientSource, /export function deleteApiAutomationScenarioSuite/);
  assert.match(apiClientSource, /export function runApiAutomationScenarioSuite/);
  assert.match(apiClientSource, /export function listApiAutomationBatchRuns/);
  assert.match(apiClientSource, /export function getApiAutomationBatchRun/);
  assert.match(apiClientSource, /\/api-scenario-suites/);
  assert.match(apiClientSource, /\/runs/);
  assert.doesNotMatch(
    apiClientSource,
    /export type ApiAutomationScenario = \{[\s\S]*?status: "draft" \| "ready" \| "archived";/,
  );
});
