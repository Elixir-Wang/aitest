import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const workspaceSource = readFileSync(
  new URL("../src/components/ai-testing/exploration-workspace.tsx", import.meta.url),
  "utf8",
);
const detailSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx", import.meta.url),
  "utf8",
);
const createPageSource = readFileSync(
  new URL("../src/components/ai-testing/exploration-run-create-page.tsx", import.meta.url),
  "utf8",
);

test("exploration form pages can link only finalized requirements", () => {
  for (const source of [createPageSource]) {
    assert.match(source, /current_version_id: string \| null/);
    assert.match(
      source,
      /function isExplorationLinkableRequirement\(requirement: RequirementDocument\)[\s\S]*return Boolean\(requirement\.current_version_id\)/,
    );
    assert.doesNotMatch(source, /latest_requirement_analysis_run\?\.status === "completed"/);
  }
});

test("exploration form pages do not duplicate selected requirement below the field", () => {
  for (const source of [createPageSource]) {
    assert.doesNotMatch(source, /已关联：/);
    assert.doesNotMatch(source, /selectedRequirementLabel/);
    assert.match(source, />不关联需求</);
  }
});

test("exploration overview and list no longer expose inline edit dialogs", () => {
  assert.doesNotMatch(detailSource, /编辑探索任务/);
  assert.doesNotMatch(detailSource, /editDialogOpen/);
  assert.doesNotMatch(workspaceSource, /编辑探索任务/);
  assert.doesNotMatch(workspaceSource, /explorationDialogOpen/);
  assert.match(
    workspaceSource,
    /router\.push\(`\/projects\/\$\{run\.project_id\}\/exploration\/\$\{run\.id\}\/edit`\)/,
  );
  assert.match(workspaceSource, /label: "编辑"/);
});

test("exploration workspace exposes restart action from available actions", () => {
  assert.match(workspaceSource, /\(item\.available_actions \?\? \[\]\)\.includes\("start"\)/);
  assert.match(workspaceSource, /label: item\.status === "pending" \? "开始探索" : "重新探索"/);
  assert.match(workspaceSource, /\/page-exploration\/runs\/\$\{run\.id\}\/start/);
  assert.match(workspaceSource, /onSelect: \(\) => void startExplorationRun\(item\)/);
});
