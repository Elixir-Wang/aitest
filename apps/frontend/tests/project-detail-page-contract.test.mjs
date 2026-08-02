import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/projects/[projectId]/page.tsx", import.meta.url), "utf8");
const versionPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/versions/page.tsx", import.meta.url),
  "utf8",
);
const settingsPageUrl = new URL("../src/app/(main)/projects/[projectId]/settings/page.tsx", import.meta.url);

test("project detail removes edit entry and edit dialog", () => {
  assert.doesNotMatch(pageSource, /primaryAction="编辑项目"/);
  assert.doesNotMatch(pageSource, /DialogTitle>编辑项目/);
  assert.doesNotMatch(pageSource, /method: "PATCH"/);
});

test("project detail metrics use real project data", () => {
  assert.match(pageSource, /`\/dashboard\/overview\?project_id=\$\{projectId\}&days=\$\{trendDays\}`/);
  assert.match(pageSource, /apiRequest<ApiRequirementDocument\[\]>\(`\/projects\/\$\{projectId\}\/requirements`\)/);
  assert.match(pageSource, /metricByLabel\.get\("用例资产数"\)/);
  assert.match(pageSource, /metricByLabel\.get\("测试用例采纳率"\)/);
  assert.match(pageSource, /metricByLabel\.get\("自动化用例数量"\)/);
  assert.match(pageSource, /label="用例采纳率"/);
  assert.doesNotMatch(pageSource, /label="UI 自动化数量"/);
});

test("project overview hides project id and shows useful project facts", () => {
  assert.doesNotMatch(pageSource, /项目 ID/);
  assert.match(pageSource, /label: "项目名称"/);
  assert.match(pageSource, /label: "项目状态"/);
  assert.match(pageSource, /label: "当前版本"/);
  assert.match(pageSource, /label: "创建时间"/);
  assert.match(pageSource, /label: "最近更新"/);
});

test("project navigation only exposes overview and version management tabs", () => {
  assert.match(pageSource, /activeTab="项目概览"/);
  for (const source of [pageSource, versionPageSource]) {
    assert.match(source, /\{ label: "项目概览", href: `\/projects\/\$\{projectId\}` \}/);
    assert.match(source, /\{ label: "版本管理", href: `\/projects\/\$\{projectId\}\/versions` \}/);
    assert.doesNotMatch(source, /\{ label: "项目设置", href: `\/projects\/\$\{projectId\}\/settings` \}/);
    assert.doesNotMatch(source, /^\s*"成员",$/m);
    assert.doesNotMatch(source, /^\s*"环境配置",$/m);
  }
});

test("project settings page and overview entry are removed", () => {
  assert.equal(existsSync(settingsPageUrl), false);
  assert.doesNotMatch(pageSource, /\/projects\/\$\{projectId\}\/settings/);
  assert.doesNotMatch(pageSource, /项目设置/);
  assert.match(pageSource, /<Link href=\{`\/projects\/\$\{projectId\}\/logs`\}>/);
  assert.match(pageSource, /项目日志/);
});

test("project workspace action stays on the tab row", () => {
  assert.match(pageSource, /tabActions=\{/);
  assert.doesNotMatch(pageSource, /\n\s+actions=\{/);
  assert.match(pageSource, /打开需求工作区/);
});

test("project overview restores workspace entries", () => {
  assert.match(pageSource, /title: "需求管理"/);
  assert.match(pageSource, /title: "探索分析"/);
  assert.match(pageSource, /title: "测试用例"/);
  assert.match(pageSource, /title: "操作日志"/);
});

test("project overview includes loading and retry states", () => {
  assert.match(pageSource, /function OverviewSkeleton\(\)/);
  assert.match(pageSource, /function OverviewError\(/);
  assert.match(pageSource, /重新加载/);
});
