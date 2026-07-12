import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workspaceSource = readFileSync(
  new URL("../src/components/ai-testing/exploration-workspace.tsx", import.meta.url),
  "utf8",
);
const createPageSource = readFileSync(
  new URL("../src/components/ai-testing/exploration-run-create-page.tsx", import.meta.url),
  "utf8",
);
const tableSource = readFileSync(
  new URL("../src/components/ai-testing/exploration-environments-table.tsx", import.meta.url),
  "utf8",
);

test("environment creation requires a project and places the name before project", () => {
  assert.match(workspaceSource, /project_id: form\.projectId/);
  assert.match(workspaceSource, /form\.projectId\.length > 0/);
  assert.match(workspaceSource, /所属项目 \*/);
  assert.ok(workspaceSource.indexOf("环境名称 *") < workspaceSource.indexOf("所属项目 *"));
  assert.doesNotMatch(tableSource, /<TableHead>所属项目<\/TableHead>/);
  assert.doesNotMatch(tableSource, /item\.project_name/);
});

test("exploration environment options reload within the selected project", () => {
  assert.match(createPageSource, /`\/environments\?project_id=\$\{selectedProjectId\}`/);
  assert.match(createPageSource, /data\.some\(\(environment\) => environment\.id === current\.environmentId\)/);
  assert.match(createPageSource, /disabled=\{environmentLoading \|\| !selectedProjectId\}/);
});
