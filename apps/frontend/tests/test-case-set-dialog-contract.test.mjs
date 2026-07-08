import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/test-cases/page.tsx", import.meta.url), "utf8");
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const createContractSource = apiClientSource.match(/export type ApiTestCaseSetCreate = \{[\s\S]*?\};/)?.[0] ?? "";

test("test case page exposes the create test case set flow in the test case module", () => {
  assert.match(pageSource, /createLabel="新建测试用例集"/);
  assert.match(pageSource, /<DialogTitle>新建测试用例集<\/DialogTitle>/);
  assert.match(pageSource, /生成测试用例/);
  assert.doesNotMatch(pageSource, /自动化用例集/);
  assert.doesNotMatch(pageSource, /UI 自动化/);
});

test("test case set list supports selection, batch delete, and task indicator registration", () => {
  assert.match(pageSource, /useLocalTableSelection<ApiTestCaseSet>/);
  assert.match(pageSource, /onBatchDelete=\{\(\) => deleteTestCaseSets\(setSelection\.selectedIds\)\}/);
  assert.match(pageSource, /aria-label="选择全部测试用例集"/);
  assert.match(
    pageSource,
    /item\.status === "generating" \? \(\s+<ProcessingState label=\{testCaseSetStatusLabel\(item\)\} \/>\s+\) : \(\s+testCaseSetStatusLabel\(item\)\s+\)/,
  );
  assert.match(pageSource, /notifyAiTaskStarted\(\)/);
  assert.match(pageSource, /method: "DELETE"/);
});

test("test case set status label falls back to localized labels for raw status values", () => {
  assert.match(pageSource, /review_completed: "评审完成"/);
  assert.match(pageSource, /function testCaseSetStatusLabel\(item: ApiTestCaseSet\)/);
  assert.match(pageSource, /return testCaseSetStatusLabels\[item\.status\] \?\? item\.status_label;/);
});

test("test case set row actions expose regenerate with a refresh icon", () => {
  assert.match(pageSource, /RefreshCw/);
  assert.match(pageSource, /async function regenerateTestCaseSet\(item: ApiTestCaseSet\)/);
  assert.match(pageSource, /`\/projects\/\$\{item\.project_id\}\/test-case-sets\/\$\{item\.id\}\/regenerate`/);
  assert.match(pageSource, /label: "重新生成"/);
  assert.match(pageSource, /icon: RefreshCw/);
  assert.match(pageSource, /disabled: isTestCaseSetGenerating\(item\)/);
});

test("test case set name and view action navigate to review page", () => {
  assert.match(
    pageSource,
    /<Link\s+className="block truncate hover:underline"\s+href=\{`\/test-cases\/\$\{item\.id\}\/review\?project=\$\{item\.project_id\}`\}\s+title=\{item\.name\}/,
  );
  assert.match(
    pageSource,
    /label: "查看",\s+icon: ClipboardCheck,\s+href: `\/test-cases\/\$\{item\.id\}\/review\?project=\$\{item\.project_id\}`/,
  );
  assert.doesNotMatch(pageSource, /openTestCaseSetDetail/);
  assert.doesNotMatch(pageSource, /router\.push\(`\/test-cases\/\$\{item\.id\}\/review/);
  assert.doesNotMatch(pageSource, /selectedSetDetail/);
  assert.doesNotMatch(pageSource, /<DialogTitle>测试用例集详情<\/DialogTitle>/);
});

test("all-project scope loads test case sets from every real project", () => {
  assert.match(pageSource, /async \(nextProjectIds: string\[\], options\?: \{ silent\?: boolean \}\)/);
  assert.match(pageSource, /nextProjectIds\.map\(\(projectId\) => apiRequest<ApiTestCaseSet\[\]>/);
  assert.match(pageSource, /projects\.filter\(\(project\) => !project\.id\.startsWith\("__"\)\)/);
  assert.match(pageSource, /data\.flat\(\)\.sort/);
});

test("test case set creation requires exactly one finalized requirement", () => {
  assert.match(pageSource, /requirementDocId: ""/);
  assert.match(pageSource, /function handleRequirementChange\(value: string\)/);
  assert.match(pageSource, /const finalRequirements = requirements\.filter\(isFinalRequirement\);/);
  assert.match(pageSource, /finalRequirements\.map\(\(requirement\) =>/);
  assert.match(pageSource, /finalRequirementVersionActions\.has\(requirement\.current_version\.source_action\)/);
  assert.doesNotMatch(pageSource, /use_exploration_artifacts/);
  assert.doesNotMatch(createContractSource, /use_exploration_artifacts/);
  assert.doesNotMatch(createContractSource, /exploration_run_id: string/);
  assert.match(pageSource, /placeholder="搜索用例集或需求"/);
  assert.doesNotMatch(pageSource, /<TableHead>关联探索<\/TableHead>/);
  assert.match(pageSource, /请选择需求/);
  assert.doesNotMatch(pageSource, /requirements:\s*\[/);
});

test("reserved exploration and company knowledge controls default to no without request parameters", () => {
  assert.match(pageSource, /const NO_EXPLORATION_ARTIFACTS_VALUE = "no_exploration_artifacts";/);
  assert.match(pageSource, /const NO_COMPANY_KNOWLEDGE_VALUE = "no_company_knowledge";/);
  assert.match(pageSource, /使用探索产物/);
  assert.match(pageSource, /不使用探索产物/);
  assert.match(pageSource, /使用公司知识库/);
  assert.match(pageSource, /不使用公司知识库/);
  assert.doesNotMatch(pageSource, /include_company_knowledge/);
  assert.doesNotMatch(createContractSource, /include_company_knowledge/);
  assert.doesNotMatch(apiClientSource, /include_company_knowledge: boolean/);
});

test("generation scope supports all content or specified range input", () => {
  assert.match(pageSource, /generationScopeType: "all"/);
  assert.match(pageSource, /全部需求内容/);
  assert.match(pageSource, /指定范围/);
  assert.match(pageSource, /例如：这个需求中登录部分的测试用例/);
  assert.match(pageSource, /form\.generationScopeType === "specified"/);
});

test("api client contains test case set request and response contracts", () => {
  assert.match(apiClientSource, /export type ApiTestCaseSet =/);
  assert.match(apiClientSource, /export type ApiTestCase =/);
  assert.match(apiClientSource, /cases: ApiTestCase\[\]/);
  assert.match(apiClientSource, /export type ApiTestCaseSetCreate =/);
  assert.match(apiClientSource, /export type ApiRequirementDocument =/);
  assert.match(apiClientSource, /export type ApiExplorationRun =/);
});

test("legacy synchronous test case generation entry is removed", () => {
  assert.doesNotMatch(apiClientSource, /test-case-sets\/generate/);
  assert.doesNotMatch(pageSource, /test-case-sets\/generate/);
});
