import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx", import.meta.url),
  "utf8",
);

test("exploration detail keeps only the page-level stop exploration action", () => {
  assert.doesNotMatch(pageSource, /<h2 className="font-medium text-sm">探索模块进度<\/h2>[\s\S]*>\s*停止\s*<\/Button>/);
  assert.match(pageSource, />\s*停止探索\s*<\/Button>/);
});

test("running exploration runs show pending module plans as active", () => {
  assert.match(
    pageSource,
    /function resolveModulePlanStatus\(runStatus: string, moduleStatus: string\): AgentPlanStatus/,
  );
  assert.match(
    pageSource,
    /const canFollowRunStatus = normalizedModuleStatus === "pending" \|\| normalizedModuleStatus === "running";/,
  );
  assert.match(
    pageSource,
    /if \(isActiveStatus\(runStatus\) && canFollowRunStatus\) \{[\s\S]*return normalizeAgentPlanStatus\(runStatus\);/,
  );
  assert.match(pageSource, /status: resolveModulePlanStatus\(detail\.run\.status, module\.completion_status\)/);
});

test("running page events do not keep completed exploration pages active", () => {
  assert.match(pageSource, /function resolvePagePlanStatus\(page: ExplorationPage\): AgentPlanStatus/);
  assert.match(pageSource, /status: resolvePagePlanStatus\(page\)/);
  assert.doesNotMatch(pageSource, /status: normalizeAgentPlanStatus\(page\.status \|\| "pending"\)/);
});

test("exploration module cards do not show synthetic percentage progress", () => {
  assert.doesNotMatch(pageSource, /`\$\{module\.progress_percent \?\? 0\}%`/);
});

test("exploration stream updates the displayed detail snapshot", () => {
  assert.match(
    pageSource,
    /function applyStreamEvent\([\s\S]*setStreamDetail: React\.Dispatch<React\.SetStateAction<ExplorationRunDetail \| null>>;/,
  );
  assert.match(pageSource, /applyStreamEvent\(event, \{ setStreamDetail, setRun \}\);/);
  assert.match(pageSource, /setters\.setStreamDetail\(\(current\) => mergeModuleEvent\(current, event\)\);/);
  assert.doesNotMatch(pageSource, /applyStreamEvent\(event, \{ setDetail, setRun \}\);/);
  assert.match(pageSource, /const runStatus = run\?\.status;/);
  assert.match(pageSource, /\}, \[loadRun, params\.projectId, params\.runId, runStatus\]\);/);
});

test("exploration detail exposes no execution or interaction mode controls", () => {
  assert.match(pageSource, /const restarting = hasExplorationStarted\(run\);/);
  assert.match(pageSource, /\/projects\/\$\{run\.project_id\}\/exploration-runs\/\$\{run\.id\}\/start/);
  assert.doesNotMatch(pageSource, /explorationExecutionModeOptions/);
  assert.doesNotMatch(pageSource, /explorationInteractionModeOptions/);
  assert.doesNotMatch(pageSource, /executionMode/);
  assert.doesNotMatch(pageSource, /interactionMode/);
  assert.doesNotMatch(pageSource, /execution_mode/);
  assert.doesNotMatch(pageSource, /interaction_mode/);
  assert.doesNotMatch(pageSource, /agent_turn_count/);
  assert.doesNotMatch(pageSource, /restartPolicyPatch/);
  assert.doesNotMatch(pageSource, />执行模式</);
  assert.doesNotMatch(pageSource, />探索引擎</);
  assert.doesNotMatch(pageSource, />交互策略</);
  assert.doesNotMatch(pageSource, /Agent 决策轮数/);
  assert.doesNotMatch(pageSource, /body: JSON\.stringify\(\{[\s\S]*(execution_mode|interaction_mode)[\s\S]*\}\)/);
});

test("exploration detail supports first discovery before confirmed plan runs", () => {
  assert.match(pageSource, /type ExplorationPlan = \{/);
  assert.match(pageSource, /plan_status: "not_generated" \| "draft" \| "confirmed" \| "running" \| "completed" \| "blocked";/);
  assert.match(pageSource, /async function generateExplorationPlan\(\)/);
  assert.match(pageSource, /async function confirmExplorationPlan\(\)/);
  assert.match(
    pageSource,
    /const hasFirstDiscoveryArtifacts = activeDetail[\s\S]*\? activeDetail\.modules\.some\(\(module\) => !hasNoModuleArtifacts\(module\)\)[\s\S]*: false;/,
  );
  assert.match(pageSource, /const canStartFirstDiscovery = Boolean\(run\) && canStart && !hasFirstDiscoveryArtifacts;/);
  assert.match(pageSource, /const canStartFromPlan = explorationPlan\?\.plan_status === "confirmed" && Boolean\(run\) && canStart;/);
  assert.match(pageSource, />\s*首次探索采集\s*<\/Button>/);
  assert.match(pageSource, />\s*生成探索计划\s*<\/Button>/);
  assert.match(pageSource, />\s*确认计划\s*<\/Button>/);
  assert.match(pageSource, />\s*按计划开始探索\s*<\/Button>/);
  assert.doesNotMatch(pageSource, />\s*\{startLabel\}\s*<\/Button>/);
});
