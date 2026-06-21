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

test("exploration can link only finalized requirements", () => {
  for (const source of [workspaceSource, detailSource]) {
    assert.match(source, /current_version_id: string \| null/);
    assert.match(source, /function isExplorationLinkableRequirement\(requirement: RequirementDocument\)[\s\S]*return Boolean\(requirement\.current_version_id\)/);
    assert.doesNotMatch(source, /latest_requirement_analysis_run\?\.status === "completed"/);
  }
});

test("exploration requirement select does not duplicate selected requirement below the field", () => {
  for (const source of [workspaceSource, detailSource]) {
    assert.doesNotMatch(source, /已关联：/);
    assert.doesNotMatch(source, /selectedRequirementLabel/);
    assert.match(source, /当前项目没有可关联的需求，请先完成需求分析。/);
  }
});

test("exploration workspace exposes restart action from available actions", () => {
  assert.match(workspaceSource, /item\.available_actions\.includes\("start"\)/);
  assert.match(workspaceSource, /label: item\.status === "pending" \? "开始探索" : "重新探索"/);
  assert.match(workspaceSource, /\/projects\/\$\{run\.project_id\}\/exploration-runs\/\$\{run\.id\}\/start/);
  assert.match(workspaceSource, /onSelect: \(\) => void startExplorationRun\(item\)/);
});
