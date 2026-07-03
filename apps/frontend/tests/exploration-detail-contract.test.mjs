import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx", import.meta.url),
  "utf8",
);
const taskInfoPanelSource = readFileSync(
  new URL("../src/components/ai-testing/exploration-task-info-panel.tsx", import.meta.url),
  "utf8",
);
const explorationServiceSource = readFileSync(
  new URL("../../backend/app/services/exploration/page_exploration_service.py", import.meta.url),
  "utf8",
);

test("exploration overview uses a plain dialogue transcript instead of the old event card timeline", () => {
  assert.match(taskInfoPanelSource, /function ExplorationExecutionTranscript\(/);
  assert.match(taskInfoPanelSource, /function DialogueTranscriptItem\(/);
  assert.match(taskInfoPanelSource, /function ToolTranscriptItem\(/);
  assert.match(taskInfoPanelSource, /useState<Set<string>>/);
  assert.match(taskInfoPanelSource, /<button[\s\S]*aria-expanded=/);
  assert.doesNotMatch(taskInfoPanelSource, /border-l/);
  assert.doesNotMatch(taskInfoPanelSource, /SquareTerminal/);
  assert.doesNotMatch(taskInfoPanelSource, /grid-cols-\[28px_minmax\(0,1fr\)\]/);
  assert.doesNotMatch(pageSource, /实时动作/);
  assert.doesNotMatch(pageSource, /动作列表/);
  assert.doesNotMatch(pageSource, /张卡片/);
});

test("exploration transcript merges tool lifecycle events by step id", () => {
  assert.match(taskInfoPanelSource, /const blockKey = stringValue\(event\.payload\?\.step_id\) \|\| event\.id/);
  assert.match(taskInfoPanelSource, /existing\.status = event\.status/);
  assert.match(taskInfoPanelSource, /existing\.completedAt = event\.occurred_at/);
  assert.match(taskInfoPanelSource, /type: "tool"/);
  assert.match(taskInfoPanelSource, /type: "message"/);
});

test("exploration progress keeps agent plan updates and survives empty snapshots", () => {
  assert.match(explorationServiceSource, /"plan_steps": _todo_plan_steps/);
  assert.match(explorationServiceSource, /def _todo_plan_steps/);
  assert.match(pageSource, /event\.type === "planning_completed" \|\| event\.type === "agent_plan_updated"/);
  assert.match(pageSource, /normalizeMonitorPlanSteps\(payload\.plan_steps\)/);
  assert.match(pageSource, /function mergeMonitorSnapshot/);
  assert.match(pageSource, /if \(!hasMonitorProgress\(snapshot\)\)/);
  assert.match(pageSource, /current\.steps/);
});

test("exploration progress restores left-side steps from persisted plan events", () => {
  assert.match(pageSource, /function monitorStepsFromPersistedPlanEvents/);
  assert.match(pageSource, /event\.type !== "agent_plan_updated"/);
  assert.match(pageSource, /normalizeMonitorPlanSteps\(rawPlanSteps\)/);
  assert.match(
    pageSource,
    /const steps = detailSteps\.length \? mergeMonitorSteps\(persistedPlanSteps, detailSteps\) : persistedPlanSteps/,
  );
  assert.match(
    pageSource,
    /status === "running" \|\| status === "queued" \|\| status === "in-progress" \|\| status === "in_progress"/,
  );
});

test("exploration output is a right-side card with running status in the header", () => {
  assert.match(taskInfoPanelSource, /探索输出/);
  assert.match(taskInfoPanelSource, /h-\[calc\(100vh-210px\)\]/);
  assert.match(taskInfoPanelSource, /rounded-xl border border-border\/70 bg-card text-card-foreground/);
  assert.doesNotMatch(taskInfoPanelSource, /bg-slate-50\/80/);
  assert.match(taskInfoPanelSource, /function RunStatusBadge/);
  assert.match(taskInfoPanelSource, /className="ml-auto"/);
  assert.match(taskInfoPanelSource, /status: AgentPlanStatus/);
  assert.match(taskInfoPanelSource, /执行中/);
  assert.match(taskInfoPanelSource, /已停止/);
});

test("exploration transcript auto-scrolls only while the user is near the bottom", () => {
  assert.match(taskInfoPanelSource, /const scrollRef = useRef<HTMLDivElement>\(null\)/);
  assert.match(taskInfoPanelSource, /const \[stickToBottom, setStickToBottom\] = useState\(true\)/);
  assert.match(taskInfoPanelSource, /distanceFromBottom < 48/);
  assert.match(taskInfoPanelSource, /node\.scrollTo\(\{ top: node\.scrollHeight, behavior: "smooth" \}\)/);
  assert.match(taskInfoPanelSource, /onScroll=\{handleScroll\}/);
});

test("exploration transcript keeps slim public payloads", () => {
  assert.match(taskInfoPanelSource, /display\.summary \|\| event\.summary/);
  assert.doesNotMatch(pageSource, /displayFields/);
  assert.doesNotMatch(pageSource, /rawEventIds/);
  assert.doesNotMatch(taskInfoPanelSource, /payload\.input/);
  assert.doesNotMatch(taskInfoPanelSource, /payload\.output/);
  assert.doesNotMatch(pageSource, /debug_ref/);
  assert.doesNotMatch(pageSource, /duration_ms/);
  assert.doesNotMatch(pageSource, /suggestion/);
});

test("agent stream events still produce readable thought and tool updates", () => {
  assert.match(explorationServiceSource, /agent_thought/);
  assert.match(explorationServiceSource, /_projection_message_to_thought_event/);
  assert.match(explorationServiceSource, /_public_agent_thought/);
  assert.match(explorationServiceSource, /agent_tool_started/);
  assert.match(explorationServiceSource, /agent_tool_completed/);
  assert.match(explorationServiceSource, /agent_tool_failed/);
  assert.match(explorationServiceSource, /agent_plan_updated/);
  assert.match(explorationServiceSource, /if tool_name == "write_todos":/);
  assert.doesNotMatch(explorationServiceSource, /displayFields/);
  assert.doesNotMatch(explorationServiceSource, /rawEventIds/);
  assert.doesNotMatch(explorationServiceSource, /debug_ref/);
  assert.doesNotMatch(explorationServiceSource, /duration_ms/);
});
