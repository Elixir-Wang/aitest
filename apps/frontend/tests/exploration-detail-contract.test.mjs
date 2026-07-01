import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx", import.meta.url),
  "utf8",
);
const explorationServiceSource = readFileSync(
  new URL("../../backend/app/services/exploration/page_exploration_service.py", import.meta.url),
  "utf8",
);

test("exploration overview uses left stages and right conversation stream", () => {
  assert.match(pageSource, /function ExplorationStageSidebar\(/);
  assert.match(pageSource, /function ExplorationConversationPanel\(/);
  assert.match(pageSource, /function ToolCallInlineBlock\(/);
  assert.match(pageSource, /function ConversationMessageBubble\(/);
  assert.match(pageSource, /buildExplorationConversationEntries/);
  assert.match(pageSource, /lg:grid-cols-\[360px_minmax\(0,1fr\)\]/);
  assert.match(pageSource, />\s*探索阶段\s*</);
  assert.match(pageSource, />\s*对话与执行\s*</);
  assert.doesNotMatch(pageSource, /实时动作/);
  assert.doesNotMatch(pageSource, /动作列表/);
  assert.doesNotMatch(pageSource, /张卡片/);
  assert.doesNotMatch(pageSource, /rounded-lg border bg-muted\/10 p-3/);
  assert.doesNotMatch(pageSource, /border bg-background px-3 py-2 text-sm/);
});

test("exploration overview keeps write_todos out of the main conversation timeline", () => {
  assert.match(pageSource, /event\.type === "agent_plan_updated" \|\| event\.display\?\.kind === "todo_update"/);
  assert.match(pageSource, /if \(display\?\.kind === "model_analysis"\)/);
  assert.match(pageSource, /if \(display\)/);
  assert.doesNotMatch(pageSource, /write_todos.*timeline/);
  assert.doesNotMatch(pageSource, /agent_plan_updated.*timeline/);
});

test("exploration overview keeps slim conversation payloads", () => {
  assert.match(pageSource, /type ExplorationConversationEntry = \{/);
  assert.doesNotMatch(pageSource, /displayFields/);
  assert.doesNotMatch(pageSource, /rawEventIds/);
  assert.doesNotMatch(pageSource, /debug_ref/);
  assert.doesNotMatch(pageSource, /duration_ms/);
  assert.doesNotMatch(pageSource, /suggestion/);
});

test("agent stream events still produce readable thought and tool updates", () => {
  assert.match(explorationServiceSource, /agent_thought/);
  assert.match(explorationServiceSource, /agent_tool_started/);
  assert.match(explorationServiceSource, /agent_tool_completed/);
  assert.match(explorationServiceSource, /agent_tool_failed/);
  assert.match(explorationServiceSource, /agent_plan_updated/);
  assert.match(explorationServiceSource, /if name == "write_todos":/);
  assert.doesNotMatch(explorationServiceSource, /displayFields/);
  assert.doesNotMatch(explorationServiceSource, /rawEventIds/);
  assert.doesNotMatch(explorationServiceSource, /debug_ref/);
  assert.doesNotMatch(explorationServiceSource, /duration_ms/);
});
