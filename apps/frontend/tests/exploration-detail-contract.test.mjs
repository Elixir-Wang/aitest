import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx", import.meta.url),
  "utf8",
);
const explorationRunRepoSource = readFileSync(
  new URL("../../backend/app/repositories/exploration_run_repo.py", import.meta.url),
  "utf8",
);
const explorationServiceSource = readFileSync(
  new URL("../../backend/app/services/exploration/page_exploration_service.py", import.meta.url),
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

test("terminal exploration overview falls back to realtime monitor when planned modules are filtered out", () => {
  assert.match(pageSource, /const hideEmptyPlanModules = isTerminalStatus\(detail\.run\.status\);/);
  assert.match(
    pageSource,
    /const tasks = detail\.modules[\s\S]*\.filter\(\(module\) => !\(hideEmptyPlanModules && isEmptyPlannedModule\(module\)\)\)[\s\S]*\.map\(\(module\) => \(\{/,
  );
  assert.match(pageSource, /return tasks\.length \? tasks : buildMonitorModuleTasks\(monitor\);/);
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
  assert.match(
    pageSource,
    /setters\.setMonitor\(finalizeRunningMonitorSteps\(monitorFromRunDetail\(snapshot\), snapshot\.run\.status\)\);/,
  );
  assert.match(pageSource, /setters\.setStreamDetail\(\(current\) => mergeModuleEvent\(current, event\)\);/);
  assert.doesNotMatch(pageSource, /applyStreamEvent\(event, \{ setDetail, setRun \}\);/);
  assert.match(pageSource, /const runStatus = run\?\.status;/);
  assert.match(pageSource, /\}, \[loadRun, params\.runId, runStatus\]\);/);
});

test("exploration detail refresh preserves existing map when snapshot has no modules", () => {
  assert.match(
    pageSource,
    /function mergeDetailSnapshot\([\s\S]*current: ExplorationRunDetail \| null,[\s\S]*incoming: ExplorationRunDetail,[\s\S]*\): ExplorationRunDetail/,
  );
  assert.match(pageSource, /setStreamDetail\(\(current\) => mergeDetailSnapshot\(current, normalizedData\)\);/);
  assert.match(pageSource, /setters\.setStreamDetail\(\(current\) => mergeDetailSnapshot\(current, snapshot\)\);/);
  assert.match(pageSource, /if \(!current \|\| incoming\.modules\.length > 0\) \{[\s\S]*return incoming;/);
  assert.match(pageSource, /if \(current\.run\.id !== incoming\.run\.id \|\| current\.modules\.length === 0\) \{/);
  assert.match(pageSource, /modules: current\.modules,/);
});

test("restarting exploration clears previous overview and failed runs keep current partial outputs", () => {
  assert.match(explorationServiceSource, /event_bus\.clear\(run_id\)/);
  assert.match(explorationServiceSource, /_clear_previous_exploration_outputs\(run_dict\)/);
  assert.match(explorationServiceSource, /def _register_failed_exploration_outputs\(run_id: str\) -> str:/);
  assert.match(explorationServiceSource, /artifact_summary = _register_failed_exploration_outputs\(run_id\)/);
  assert.match(explorationRunRepoSource, /def reset_completion_state\(db: Connection, run_id: str\) -> None:/);
  assert.match(
    explorationRunRepoSource,
    /SET[\s\S]*result_summary\s*=\s*''[\s\S]*WHERE id = \?/,
  );
});

test("exploration overview owns realtime stream beside module progress", () => {
  assert.match(pageSource, /payload\?: Record<string, unknown>;/);
  assert.match(pageSource, /type ReadableExecutionCardKind =/);
  assert.match(pageSource, /function buildReadableExecutionCards\(/);
  assert.match(pageSource, /function ReadableExecutionCardView\(/);
  assert.match(pageSource, /function RawExecutionEvents\(/);
  assert.match(pageSource, /function ExplorationModuleProgressPanel\(/);
  assert.match(pageSource, /function ExplorationRealtimeStreamPanel\(/);
  assert.match(pageSource, /function ExplorationModuleEmptyState\(/);
  assert.match(pageSource, /<ExplorationModuleProgressPanel[\s\S]*monitor=\{monitor\}/);
  assert.match(
    pageSource,
    /<ExplorationRealtimeStreamPanel[\s\S]*monitor=\{monitor\}[\s\S]*run=\{run\}[\s\S]*streamDetail=\{detail\}/,
  );
  assert.match(pageSource, /min-h-\[480px\]/);
  assert.match(pageSource, /lg:min-h-0/);
  assert.match(pageSource, /lg:grid-cols-\[360px_minmax\(0,1fr\)\]/);
  assert.match(pageSource, /className="min-h-0 min-w-0 overflow-y-auto/);
  assert.match(pageSource, /className="h-full"/);
  assert.match(pageSource, /className="min-h-0 flex-1 space-y-2 overflow-y-auto/);
  assert.match(pageSource, /关键动作摘要，原始事件保留在卡片调试区/);
  assert.match(pageSource, /原始事件 \/ 输入输出 \/ 调试信息/);
});

test("exploration realtime stream follows new events while pinned to bottom", () => {
  assert.match(pageSource, /useLayoutEffect/);
  assert.match(pageSource, /function ExplorationRealtimeStreamPanel\(/);
  assert.match(pageSource, /const latestEventKey = useMemo\(\(\) => \{/);
  assert.match(pageSource, /latestCard\.raw_events\.length,/);
  assert.match(pageSource, /previousLatestEventKeyRef\.current === latestEventKey/);
  assert.match(
    pageSource,
    /const shouldFollowLatest = shouldFollowBottomRef\.current \|\| isEventListAtBottom\(list\);/,
  );
  assert.match(
    pageSource,
    /window\.requestAnimationFrame\(\(\) => \{[\s\S]*list\.scrollTo\(\{ top: list\.scrollHeight \}\);/,
  );
  assert.match(pageSource, /shouldFollowBottomRef\.current = true;[\s\S]*setUnreadEventCount\(0\);/);
  assert.match(pageSource, /const isAtBottom = isEventListAtBottom\(list\);/);
});

test("exploration overview does not render the empty module progress card", () => {
  assert.doesNotMatch(pageSource, /暂无探索模块进度信息/);
  assert.doesNotMatch(pageSource, /任务尚未开始，点击「开始探索」后将显示进度信息。/);
});

test("exploration overview does not render the execution timeline card", () => {
  assert.doesNotMatch(pageSource, /执行时间线/);
  assert.doesNotMatch(pageSource, /按北京时间展示关键阶段/);
  assert.doesNotMatch(pageSource, /function TimelineItem/);
});

test("exploration plan tab no longer renders realtime execution monitor", () => {
  assert.match(pageSource, /tabs=\{\["探索概览", "探索报告"\]\}/);
  assert.match(pageSource, /activeTab === "探索概览" \? \(/);
  assert.doesNotMatch(pageSource, /<ExplorationTaskInfoPanel monitor=\{monitor\} run=\{run\} \/>/);
  assert.doesNotMatch(pageSource, /function ExplorationTaskInfoPanel\(\{ monitor, run \}/);
  assert.doesNotMatch(pageSource, /<ExplorationRealtimeMonitor monitor=\{monitor\} run=\{run\} \/>/);
  assert.doesNotMatch(pageSource, /function ExplorationRealtimeMonitor\(/);
});

test("exploration stream snapshot rebuilds realtime monitor without fuzzy module matching", () => {
  assert.match(pageSource, /function monitorFromRunDetail\(detail: ExplorationRunDetail\): ExplorationMonitorState/);
  assert.match(
    pageSource,
    /function monitorStepsFromDetail\(detail: ExplorationRunDetail\): ExplorationMonitorStep\[\]/,
  );
  assert.match(
    pageSource,
    /function findStreamModuleIndex\(modules: ExplorationRunDetail\["modules"\], moduleId: string\): number/,
  );
  assert.doesNotMatch(pageSource, /module\.module_name\.includes\(moduleId\)/);
  assert.doesNotMatch(pageSource, /moduleId\.includes\(module\.module_name\)/);
});

test("exploration detail exposes no execution or interaction mode controls", () => {
  assert.match(pageSource, /const restarting = hasExplorationStarted\(run\);/);
  assert.match(pageSource, /\/page-exploration\/runs\/\$\{run\.id\}\/start/);
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
  assert.match(pageSource, /tabs=\{\["探索概览", "探索报告"\]\}/);
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
  assert.match(pageSource, /\.split\(\s*\/\[，。\]\/\s*\)/);
  assert.doesNotMatch(pageSource, /\.split\(\s*\/\\n\+\/\s*\)/);
});

test("exploration detail query includes environment summary fields", () => {
  assert.match(explorationRunRepoSource, /def find_detail_by_id\(db: Connection, run_id: str\) -> Row \| None:/);
  assert.match(explorationRunRepoSource, /p\.name AS project_name/);
  assert.match(explorationRunRepoSource, /pe\.name AS environment_name/);
  assert.match(explorationRunRepoSource, /pe\.site_url AS environment_site_url/);
  assert.match(explorationRunRepoSource, /pe\.login_strategy AS environment_login_strategy/);
  assert.match(explorationRunRepoSource, /COALESCE\(sd\.name, ''\) AS requirement_doc_title/);
  assert.match(explorationServiceSource, /def _normalize_exploration_run_detail\(run: dict\) -> dict:/);
  assert.match(explorationServiceSource, /run\["login_strategy"\] = environment_login_strategy/);
});
