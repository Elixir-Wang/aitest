import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

function readSource(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

const listPageSource = readSource("../src/app/(main)/exploration/page.tsx");
const globalCreatePageSource = readSource("../src/app/(main)/exploration/new/page.tsx");
const projectCreatePageSource = readSource("../src/app/(main)/projects/[projectId]/exploration/new/page.tsx");
const detailPageSource = readSource("../src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx");
const editPageSource = readSource("../src/app/(main)/projects/[projectId]/exploration/[runId]/edit/page.tsx");
const createPageSource = readSource("../src/components/ai-testing/exploration-run-create-page.tsx");

test("exploration routes use centralized breadcrumb builders", () => {
  assert.match(listPageSource, /moduleBreadcrumbs\("exploration"\)/);
  assert.doesNotMatch(globalCreatePageSource, /breadcrumbs=/);
  assert.doesNotMatch(projectCreatePageSource, /breadcrumbs=/);
  assert.doesNotMatch(editPageSource, /breadcrumbs=/);
});

test("exploration edit breadcrumbs use the loaded task title and detail link", () => {
  assert.match(createPageSource, /moduleBreadcrumbs\(\s*"exploration"/);
  assert.match(createPageSource, /label: loadedRunTitle/);
  assert.match(createPageSource, /setLoadedRunTitle\(run\.title\)/);
  assert.match(createPageSource, /: moduleBreadcrumbs\("exploration", \{ label: "新建探索任务" \}\)/);
  assert.doesNotMatch(createPageSource, /breadcrumbs\?:/);
  assert.match(createPageSource, /breadcrumbs=\{pageBreadcrumbs\}/);
});

test("project-scoped exploration pages do not encode the selected project as breadcrumb hierarchy", () => {
  assert.doesNotMatch(projectCreatePageSource, /label: "项目"/);
  assert.doesNotMatch(projectCreatePageSource, /label: projectName/);
  assert.doesNotMatch(editPageSource, /label: "项目"/);
  assert.doesNotMatch(editPageSource, /label: projectName/);
  assert.doesNotMatch(detailPageSource, /label: "项目"/);
  assert.doesNotMatch(detailPageSource, /label: projectName/);
});
