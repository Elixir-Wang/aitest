import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/projects/[projectId]/page.tsx", import.meta.url), "utf8");

test("project detail removes edit entry and edit dialog", () => {
  assert.doesNotMatch(pageSource, /primaryAction="编辑项目"/);
  assert.doesNotMatch(pageSource, /DialogTitle>编辑项目/);
  assert.doesNotMatch(pageSource, /method: "PATCH"/);
});

test("project detail metrics use real project data", () => {
  assert.match(
    pageSource,
    /apiRequest<ApiDashboardOverview>\(`\/dashboard\/overview\?project_id=\$\{projectId\}&days=7`\)/,
  );
  assert.match(pageSource, /apiRequest<ApiRequirementDocument\[\]>\(`\/projects\/\$\{projectId\}\/requirements`\)/);
  assert.match(pageSource, /metricByLabel\.get\("用例资产数"\)/);
  assert.match(pageSource, /metricByLabel\.get\("测试用例采纳率"\)/);
  assert.match(pageSource, /label="用例采纳率"/);
  assert.doesNotMatch(pageSource, /label="UI 自动化数量"/);
});

test("project overview hides project id and shows five useful facts", () => {
  assert.doesNotMatch(pageSource, /项目 ID/);
  assert.match(pageSource, /项目名称：/);
  assert.match(pageSource, /项目描述：/);
  assert.match(pageSource, /状态：/);
  assert.match(pageSource, /创建时间：/);
  assert.match(pageSource, /最近更新：/);
  assert.doesNotMatch(pageSource, /需求文档：/);
  assert.doesNotMatch(pageSource, /用例资产：/);
});

test("project log action has no leading icon", () => {
  assert.doesNotMatch(pageSource, /ListChecks/);
  assert.match(
    pageSource,
    /<Button variant="outline" onClick=\{\(\) => goToModule\(`\/projects\/\$\{projectId\}\/logs`\)\}>\s*项目日志\s*<\/Button>/,
  );
});
