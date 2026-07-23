import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const sidebarSource = fs.readFileSync(new URL("../src/navigation/sidebar/sidebar-items.ts", import.meta.url), "utf8");
const pageSource = fs.readFileSync(new URL("../src/app/(main)/automation/ui/page.tsx", import.meta.url), "utf8");
const apiClientSource = fs.readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("UI automation navigation is available", () => {
  const uiAutomationItem = sidebarSource.match(/title: "UI 自动化",[\s\S]*?url: "\/automation\/ui",[\s\S]*?\n\s*},/);

  assert.ok(uiAutomationItem, "UI 自动化导航项应存在");
  assert.doesNotMatch(uiAutomationItem[0], /comingSoon:\s*true/);
  assert.doesNotMatch(uiAutomationItem[0], /disabled:\s*true/);
});

test("UI automation asset list reuses the API automation list structure without dropping content", () => {
  assert.match(pageSource, /<ListToolbar/);
  assert.match(pageSource, /createLabel="新建 UI 自动化"/);
  assert.match(pageSource, /const selection = useLocalTableSelection<UiAutomationRow>/);
  assert.match(pageSource, /selectedCount=\{selection\.selectedCount\}/);
  assert.match(pageSource, /aria-label="选择全部 UI 自动化用例"/);
  assert.match(pageSource, /selection\.toggleAll\(Boolean\(checked\)\)/);
  assert.match(pageSource, /selection\.toggleOne\(row\.id, Boolean\(checked\)\)/);
  assert.match(pageSource, /<div className="overflow-hidden rounded-lg border">/);
  assert.match(pageSource, /<TableHead>用例名称<\/TableHead>/);
  assert.doesNotMatch(pageSource, /<TableHead>项目<\/TableHead>/);
  assert.match(pageSource, /<TableHead>入口路径<\/TableHead>/);
  assert.match(pageSource, /<TableHead>步骤<\/TableHead>/);
  assert.match(pageSource, /<TableHead className="w-20">执行<\/TableHead>/);
  assert.doesNotMatch(pageSource, /<FieldLabel>项目<\/FieldLabel>/);
  assert.doesNotMatch(pageSource, /<FieldLabel>运行环境<\/FieldLabel>/);
});

test("UI automation create dialog selects the real generation inputs", () => {
  assert.match(pageSource, /<DialogTitle>新建 UI 自动化<\/DialogTitle>/);
  assert.match(pageSource, /<FieldLabel htmlFor="ui-automation-project">项目<\/FieldLabel>/);
  assert.match(pageSource, /<FieldLabel htmlFor="ui-automation-source">测试用例 \/ 已采纳用例集<\/FieldLabel>/);
  assert.doesNotMatch(pageSource, /ui-automation-case-set/);
  assert.match(pageSource, /apiRequest<ApiManualTestCase\[]>\(`\/projects\/\$\{nextProjectId\}\/test-cases`\)/);
  assert.match(pageSource, /value=\{`manual:\$\{testCase\.id\}`\}/);
  assert.match(pageSource, /value=\{`set:\$\{caseSet\.id\}`\}/);
  assert.match(pageSource, /item\.status === "approved"/);
  assert.match(pageSource, /<FieldLabel htmlFor="ui-automation-environment">运行环境<\/FieldLabel>/);
  assert.match(pageSource, /createUiAutomationGenerationRun/);
});

test("UI automation execution chooses an environment outside the aggregate list", () => {
  assert.match(pageSource, /<DialogTitle>执行 UI 自动化<\/DialogTitle>/);
  assert.match(pageSource, /<FieldLabel htmlFor="ui-automation-run-environment">运行环境<\/FieldLabel>/);
  assert.match(pageSource, /createUiAutomationExecutionRun/);
});

test("API client exposes UI automation asset, generation, and execution contracts", () => {
  assert.match(apiClientSource, /export function listUiAutomationAssets/);
  assert.match(apiClientSource, /export function createUiAutomationGenerationRun/);
  assert.match(apiClientSource, /export function getUiAutomationGenerationRun/);
  assert.match(apiClientSource, /export function createUiAutomationExecutionRun/);
  assert.match(apiClientSource, /export function getUiAutomationExecutionRun/);
});
