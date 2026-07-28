import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const editorSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-scenario-editor.tsx", import.meta.url),
  "utf8",
);
const hookSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/use-api-scenario-editor.ts", import.meta.url),
  "utf8",
);
const clientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const taskIndicatorSource = readFileSync(
  new URL("../src/components/ai-testing/task-running-indicator.tsx", import.meta.url),
  "utf8",
);

test("AI scenario generation uses an accepted background task contract", () => {
  assert.match(clientSource, /ApiScenarioAiPlanAccepted/);
  assert.match(clientSource, /lifecycle_status:\s*"generating"/);
  assert.match(clientSource, /apiRequest<ApiScenarioAiPlanAccepted>/);
  assert.match(hookSource, /const accepted = await createApiScenarioAiPlan/);
  assert.match(hookSource, /notifyAiTaskStarted\(\)/);
  assert.match(hookSource, /sessionStorage\.setItem\([\s\S]*accepted\.plan_id/);
  assert.doesNotMatch(hookSource, /const plan = await createApiScenarioAiPlan/);
});

test("AI orchestration is a right drawer that closes after task acceptance", () => {
  assert.match(editorSource, /AiOrchestrationDrawer/);
  assert.match(editorSource, /<Drawer direction="right"/);
  assert.match(editorSource, /data-\[vaul-drawer-direction=right\]:sm:max-w-\[480px\]/);
  assert.doesNotMatch(editorSource, /function AiOrchestrationDialog/);
  assert.match(editorSource, /const accepted = await onGenerate\(goal\.trim\(\)\)/);
  assert.match(editorSource, /if \(accepted\) onOpenChange\(false\)/);
});

test("top running task cards link back to task details", () => {
  assert.match(taskIndicatorSource, /detailUrl: item\.detail_url/);
  assert.match(taskIndicatorSource, /<Link[^>]*href=\{task\.detailUrl\}/);
  assert.match(taskIndicatorSource, /查看任务/);
});
