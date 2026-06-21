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

test("running exploration modules without pages still render an expandable progress subtask", () => {
  assert.match(pageSource, /function buildModulePlanSubtasks\(/);
  assert.match(pageSource, /if \(module\.pages\.length > 0\)/);
  assert.match(pageSource, /id: `\$\{module\.id\}-progress`/);
  assert.match(pageSource, /title: buildModuleProgressSubtaskTitle\(detail\.run\.status\)/);
  assert.match(pageSource, /detail: detailText/);
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
  assert.match(pageSource, /setMonitor: React\.Dispatch<React\.SetStateAction<ExplorationMonitorState>>;/);
  assert.match(pageSource, /applyStreamEvent\(event, \{ setMonitor, setStreamDetail, setRun \}\);/);
  assert.match(pageSource, /if \(event\.type === "run_snapshot"\) \{/);
  assert.match(pageSource, /setters\.setMonitor\(monitorFromRunDetail\(snapshot\)\);/);
  assert.match(pageSource, /setters\.setStreamDetail\(\(current\) => mergeModuleEvent\(current, event\)\);/);
  assert.doesNotMatch(pageSource, /applyStreamEvent\(event, \{ setDetail, setRun \}\);/);
  assert.match(pageSource, /const runStatus = run\?\.status;/);
  assert.match(pageSource, /\}, \[loadRun, params\.projectId, params\.runId, runStatus\]\);/);
});

test("exploration stream snapshot rebuilds realtime monitor without fuzzy module matching", () => {
  assert.match(pageSource, /function monitorFromRunDetail\(detail: ExplorationRunDetail\): ExplorationMonitorState/);
  assert.match(pageSource, /function monitorStepsFromDetail\(detail: ExplorationRunDetail\): ExplorationMonitorStep\[\]/);
  assert.match(pageSource, /function findStreamModuleIndex\(modules: ExplorationRunDetail\["modules"\], moduleId: string\): number/);
  assert.doesNotMatch(pageSource, /module\.module_name\.includes\(moduleId\)/);
  assert.doesNotMatch(pageSource, /moduleId\.includes\(module\.module_name\)/);
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

test("exploration overview keeps the start action in page-level actions", () => {
  assert.match(
    pageSource,
    /const canStart = run[\s\S]*\? \["pending", "partial", "completed", "blocked", "cancelled", "interrupted", "failed"\]\.includes\(run\.status\)[\s\S]*: false;/,
  );
  assert.match(pageSource, /\{canStart \? \(/);
  assert.match(pageSource, /onClick=\{\(\) => void startExploration\(\)\}/);
  assert.match(pageSource, /\{run && hasExplorationStarted\(run\) \? "重新探索" : "开始探索"\}/);
});

test("interrupted exploration runs are terminal and restartable", () => {
  assert.match(
    pageSource,
    /return \["completed", "partial", "blocked", "cancelled", "interrupted", "failed"\]\.includes\(status\);/,
  );
  assert.match(pageSource, /"interrupted"/);
});

test("exploration detail removes the exploration plan module", () => {
  assert.match(pageSource, /tabs=\{\["探索计划", "探索概览", "探索日志", "探索报告"\]\}/);
  assert.doesNotMatch(pageSource, /type ExplorationPlan = \{/);
  assert.doesNotMatch(pageSource, /plan_status:/);
  assert.doesNotMatch(pageSource, /async function generateExplorationPlan\(\)/);
  assert.doesNotMatch(pageSource, /async function confirmExplorationPlan/);
  assert.doesNotMatch(pageSource, /ExplorationTaskPanel/);
  assert.doesNotMatch(pageSource, /<TaskSection title="探索计划">/);
  assert.doesNotMatch(pageSource, /首次探索采集/);
  assert.doesNotMatch(pageSource, /生成探索计划/);
  assert.doesNotMatch(pageSource, /从需求导入/);
  assert.doesNotMatch(pageSource, /手动修改探索计划/);
  assert.doesNotMatch(pageSource, /AI 修改当前计划/);
});

test("exploration task text keeps single newlines inside one rendered paragraph", () => {
  assert.match(pageSource, /\.split\(\s*\/\\n\{2,\}\/\s*\)/);
  assert.doesNotMatch(pageSource, /\.split\(\s*\/\\n\+\/\s*\)/);
});
