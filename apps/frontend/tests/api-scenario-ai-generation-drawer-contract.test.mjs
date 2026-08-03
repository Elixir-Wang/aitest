import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const editorSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-scenario-editor.tsx", import.meta.url),
  "utf8",
);
const drawerSource = readFileSync(new URL("../src/components/ui/drawer.tsx", import.meta.url), "utf8");
const hookSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/use-api-scenario-editor.ts", import.meta.url),
  "utf8",
);
const clientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const taskIndicatorSource = readFileSync(
  new URL("../src/components/ai-testing/task-running-indicator.tsx", import.meta.url),
  "utf8",
);
const reviewDrawerSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-scenario-ai-review-drawer.tsx", import.meta.url),
  "utf8",
);
const reviewStepSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-scenario-ai-review-step-card.tsx", import.meta.url),
  "utf8",
);
const reviewFieldSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-scenario-ai-review-field.tsx", import.meta.url),
  "utf8",
);

test("AI scenario review uses versioned editable review contracts", () => {
  assert.match(clientSource, /export type ApiScenarioAiReviewPlan/);
  assert.match(clientSource, /schema_version:\s*3/);
  assert.match(clientSource, /review_revision:\s*number/);
  assert.match(clientSource, /saveApiScenarioAiPlanReview/);
  assert.match(clientSource, /expected_review_revision/);
  assert.match(hookSource, /persistAiPlanReviewForApply/);
  assert.match(hookSource, /expected_review_revision:\s*aiPlan\.review_revision/);
  assert.match(
    hookSource,
    /expected_review_revision:\s*aiPlan\.review_revision[\s\S]*confirmation:\s*"create_version"/,
  );
});

test("AI scenario review renders one editable card per step", () => {
  assert.match(editorSource, /ApiScenarioAiReviewDrawer/);
  assert.match(reviewDrawerSource, /plan\.steps\.map/);
  assert.match(reviewDrawerSource, /ApiScenarioAiReviewStepCard/);
  assert.match(reviewStepSource, /步骤 \{step\.order\}/);
  assert.match(reviewStepSource, /step\.field_groups/);
  assert.match(reviewStepSource, /已自动确定/);
  assert.match(reviewStepSource, /最终值/);
  assert.doesNotMatch(reviewStepSource, /AI 建议/);
  assert.match(reviewFieldSource, /环境变量/);
  assert.match(reviewFieldSource, /上游输出/);
  assert.match(reviewFieldSource, /ReferenceSelect/);
  assert.match(hookSource, /synchronizeReviewField/);
  assert.match(hookSource, /synchronizeConfirmedObjectFields/);
  assert.doesNotMatch(reviewDrawerSource + reviewStepSource + reviewFieldSource, /置信度|当前环境未提供|原因/);
});

test("AI scenario review keeps primary actions in the drawer header", () => {
  const headerSource = reviewDrawerSource.match(/<DrawerHeader[\s\S]*?<\/DrawerHeader>/)?.[0] ?? "";

  assert.match(headerSource, /放弃方案/);
  assert.match(headerSource, /<Trash2 \/>[\s\S]*放弃方案/);
  assert.doesNotMatch(headerSource, /保存审核/);
  assert.match(headerSource, /应用为新版本/);
  assert.doesNotMatch(reviewDrawerSource, /onSave/);
  assert.doesNotMatch(hookSource, /handleSaveAiPlanReview|saveAiPlanReview:/);
  assert.doesNotMatch(reviewDrawerSource, /<DrawerFooter/);
});

test("AI scenario review value controls stay inside their grid columns", () => {
  assert.match(reviewFieldSource, /<SelectTrigger className="h-8 min-w-0 text-xs">/);
  assert.match(reviewFieldSource, /<Input[\s\S]*?className="h-8 min-w-0 font-mono text-xs"/);
});

test("AI scenario review displays object sources as plain JSON values", () => {
  assert.match(reviewFieldSource, /function unwrapObjectSource/);
  assert.match(reviewFieldSource, /JSON\.stringify\(unwrapObjectSource\(source\.properties/);
  assert.match(reviewFieldSource, /wrapObjectSource/);
});

test("AI scenario generation uses an accepted background task contract", () => {
  assert.match(clientSource, /ApiScenarioAiPlanAccepted/);
  assert.match(clientSource, /lifecycle_status:\s*"generating"/);
  assert.match(clientSource, /apiRequest<ApiScenarioAiPlanAccepted>/);
  assert.match(hookSource, /const accepted = await createApiScenarioAiPlan/);
  assert.match(hookSource, /notifyAiTaskStarted\(\)/);
  assert.match(hookSource, /sessionStorage\.setItem\([\s\S]*accepted\.plan_id/);
  assert.doesNotMatch(hookSource, /const plan = await createApiScenarioAiPlan/);
});

test("AI scenario generation surfaces persisted failure details", () => {
  assert.match(clientSource, /error\?:\s*\{[\s\S]*?code:\s*string;[\s\S]*?message:\s*string;/);
  assert.match(hookSource, /response\.lifecycle_status === "failed"/);
  assert.match(hookSource, /toast\.error\(\("error" in response && response\.error\?\.message\) \|\| "AI 编排失败"\)/);
  assert.match(hookSource, /response\.lifecycle_status === "expired"/);
});

test("AI orchestration submits without blocking the editor while the plan generates", () => {
  assert.match(editorSource, /AiOrchestrationDrawer/);
  assert.match(editorSource, /type AiDrawerMode = "closed" \| "generation" \| "review"/);
  assert.match(editorSource, /useState<AiDrawerMode>\("closed"\)/);
  assert.match(editorSource, /<Drawer direction="right"/);
  assert.doesNotMatch(editorSource, /<Drawer direction="right"[^>]*modal=\{false\}/);
  assert.match(editorSource, /\{busy \? "关闭" : "取消"\}/);
  assert.match(editorSource, /data-\[vaul-drawer-direction=right\]:w-\[min\(92vw,760px\)\]/);
  assert.match(editorSource, /data-\[vaul-drawer-direction=right\]:sm:max-w-\[760px\]/);
  assert.doesNotMatch(editorSource, /function AiOrchestrationDialog/);
  assert.match(editorSource, /const accepted = await editor\.actions\.generateAiPlan/);
  assert.match(editorSource, /if \(accepted\) setAiDrawerMode\("closed"\)/);
  assert.match(editorSource, /selectedEndpointIds/);
  assert.match(hookSource, /source_scope: \{ endpoint_ids: endpointIds \}/);
  assert.doesNotMatch(hookSource, /for \(let attempt = 0; attempt < 90;/);
});

test("AI orchestration closes instead of falling back to an empty generation drawer", () => {
  assert.match(editorSource, /open=\{aiDrawerMode === "review"\}/);
  assert.match(editorSource, /open=\{aiDrawerMode === "generation"\}/);
  assert.match(
    editorSource,
    /const applied = await editor\.actions\.applyAiPlan\(\);[\s\S]*if \(applied\) setAiDrawerMode\("closed"\)/,
  );
  assert.match(editorSource, /editor\.actions\.discardAiPlan\(\);[\s\S]*setAiDrawerMode\("closed"\)/);
  assert.match(hookSource, /async function applyAiPlan\(\)[\s\S]*return true;/);
  assert.match(hookSource, /catch \(error\) \{[\s\S]*AI 编排应用失败[\s\S]*return false;/);
  assert.doesNotMatch(editorSource, /setAiDrawerOpen/);
});

test("AI orchestration drawer separates dragging from text selection", () => {
  const headerSource = editorSource.match(/<DrawerHeader[\s\S]*?<\/DrawerHeader>/)?.[0] ?? "";

  assert.match(drawerSource, /function DrawerHandle/);
  assert.match(drawerSource, /DrawerPrimitive\.Handle/);
  assert.match(editorSource, /<Drawer direction="right" handleOnly/);
  assert.match(headerSource, /className="absolute inset-y-0 left-0[^"]*"[\s\S]*?<DrawerHandle/);
  assert.doesNotMatch(headerSource, /<DrawerHandle[\s\S]*?className="[^"]*absolute/);
  assert.match(editorSource, /className="[^"]*select-text!/);
});

test("AI review drawer allows text selection without changing drawer dragging", () => {
  assert.match(reviewDrawerSource, /<div className="select-text! min-h-0 space-y-4 overflow-y-auto/);
  assert.match(reviewDrawerSource, /<Drawer direction="right" handleOnly/);
  assert.match(reviewDrawerSource, /<DrawerHandle[\s\S]*?cursor-ew-resize/);
});
test("AI orchestration generation actions stay in the drawer header", () => {
  const headerSource = editorSource.match(/<DrawerHeader[\s\S]*?<\/DrawerHeader>/)?.[0] ?? "";

  assert.match(headerSource, /\{busy \? "关闭" : "取消"\}/);
  assert.match(headerSource, /\{busy \? "正在生成" : "生成编排方案"\}/);
  assert.doesNotMatch(editorSource, /<DrawerFooter/);
});

test("AI plan apply creates a new current version", () => {
  assert.match(hookSource, /confirmation:\s*"create_version"/);
  assert.doesNotMatch(hookSource, /expected_revision:\s*aiPlan\.expected_revision/);
  assert.match(clientSource, /confirmation:\s*"create_version"/);
});

test("top running task cards link back to task details", () => {
  assert.match(taskIndicatorSource, /detailUrl: item\.detail_url/);
  assert.match(taskIndicatorSource, /<Link[^>]*href=\{task\.detailUrl\}/);
  assert.match(taskIndicatorSource, /查看任务/);
});
