import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const pageSource = fs.readFileSync(new URL("../src/app/(main)/test-cases/page.tsx", import.meta.url), "utf8");
const apiClientSource = fs.readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("manual test case mode exposes AI generation beside the case choice", () => {
  assert.match(pageSource, /新建测试用例/);
  assert.match(pageSource, /AI 生成/);
  assert.match(pageSource, /createMode === "case"/);
  assert.match(pageSource, /setAiDialogOpen\(true\)/);
  assert.match(pageSource, /border-primary\/20 bg-primary\/\[0\.06\]/);
  assert.match(pageSource, /bg-primary\/10 text-primary/);
});

test("manual test case form places project after the case name", () => {
  const titleIndex = pageSource.indexOf('htmlFor="manual-test-case-title"');
  const projectIndex = pageSource.indexOf('htmlFor="manual-test-case-project"');
  const explorationIndex = pageSource.indexOf("是否关联探索产物");

  assert.ok(titleIndex >= 0);
  assert.ok(projectIndex > titleIndex);
  assert.ok(explorationIndex > projectIndex);
});

test("manual test case textareas start at one line and grow with content", () => {
  assert.match(pageSource, /className="min-h-9 resize-none overflow-hidden"\s+id="manual-test-case-preconditions"/);
  assert.match(pageSource, /aria-label=\{`第 \$\{index \+ 1\} 步操作步骤`\}[\s\S]*?rows=\{1\}/);
  assert.match(pageSource, /aria-label=\{`第 \$\{index \+ 1\} 步预期结果`\}[\s\S]*?rows=\{1\}/);
  assert.match(pageSource, /className="min-h-9 resize-none overflow-hidden"\s+id="manual-test-case-notes"/);
});

test("manual case AI generation can include all project exploration artifacts", () => {
  assert.match(pageSource, /是否关联探索产物/);
  assert.match(pageSource, /includeExplorationArtifacts/);
  assert.match(pageSource, /useState\(true\)/);
  assert.match(pageSource, /当前项目全部探索产物/);
  assert.match(pageSource, /include_exploration_artifacts: includeExplorationArtifacts/);
});

test("manual case AI result protects existing form content", () => {
  assert.match(pageSource, /function manualFormHasContent/);
  assert.match(pageSource, /manualFormRef\.current/);
  assert.match(pageSource, /pendingAiResult/);
  assert.match(pageSource, /当前表单已有内容/);
  assert.match(pageSource, /覆盖并应用/);
  assert.match(pageSource, /notes: current\.notes/);
});

test("api client defines manual test case AI request and response contracts", () => {
  assert.match(apiClientSource, /export type ApiManualTestCaseAiGenerateRequest =/);
  assert.match(apiClientSource, /include_exploration_artifacts: boolean/);
  assert.match(apiClientSource, /export type ApiManualTestCaseAiGenerateResult =/);
  assert.match(apiClientSource, /generation_notes: string\[\]/);
  assert.match(apiClientSource, /source_summary:/);
});
