import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/test-cases/page.tsx", import.meta.url), "utf8");
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("test case page exposes the create test case set flow in the test case module", () => {
  assert.match(pageSource, /createLabel="新建测试用例集"/);
  assert.match(pageSource, /<DialogTitle>新建测试用例集<\/DialogTitle>/);
  assert.match(pageSource, /生成测试用例/);
  assert.doesNotMatch(pageSource, /自动化用例集/);
  assert.doesNotMatch(pageSource, /UI 自动化/);
});

test("test case set creation requires exactly one requirement and auto-selects related exploration", () => {
  assert.match(pageSource, /requirementDocId: ""/);
  assert.match(pageSource, /function handleRequirementChange\(value: string\)/);
  assert.match(pageSource, /relatedExplorationForRequirement\(value\)/);
  assert.match(pageSource, /explorationRunId: related\?\.id \?\? ""/);
  assert.match(pageSource, /请选择需求/);
  assert.doesNotMatch(pageSource, /requirements:\s*\[/);
});

test("company knowledge is default enabled and sent as generation guidance", () => {
  assert.match(pageSource, /includeCompanyKnowledge: true/);
  assert.match(pageSource, /使用公司知识库/);
  assert.match(pageSource, /默认开启/);
  assert.match(pageSource, /include_company_knowledge: form\.includeCompanyKnowledge/);
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
  assert.match(apiClientSource, /export type ApiTestCaseSetCreate =/);
  assert.match(apiClientSource, /export type ApiRequirementDocument =/);
  assert.match(apiClientSource, /export type ApiExplorationRun =/);
});
