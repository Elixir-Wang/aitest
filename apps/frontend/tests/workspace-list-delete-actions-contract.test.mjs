import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const projectListSource = readFileSync(new URL("../src/app/(main)/projects/page.tsx", import.meta.url), "utf8");
const requirementListSource = readFileSync(
  new URL("../src/components/ai-testing/requirements-page.tsx", import.meta.url),
  "utf8",
);
const explorationWorkspaceSource = readFileSync(
  new URL("../src/components/ai-testing/exploration-workspace.tsx", import.meta.url),
  "utf8",
);

test("project, requirement, and exploration list row actions expose delete with Trash2 icons", () => {
  for (const source of [projectListSource, requirementListSource, explorationWorkspaceSource]) {
    assert.match(source, /Trash2/);
    assert.match(source, /label: "删除",[\s\S]*icon: Trash2/);
  }
});
