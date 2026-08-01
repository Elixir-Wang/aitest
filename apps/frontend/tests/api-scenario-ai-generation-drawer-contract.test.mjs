import { buildAiPlanPresentation } from "../src/components/ai-testing/api-automation/api-scenario-ai-plan-view.mjs";
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
  new URL(
    "../src/components/ai-testing/api-automation/api-scenario-ai-review-drawer.tsx",
    import.meta.url,
  ),
  "utf8",
);
const reviewStepSource = readFileSync(
  new URL(
    "../src/components/ai-testing/api-automation/api-scenario-ai-review-step-card.tsx",
    import.meta.url,
  ),
  "utf8",
);
const reviewFieldSource = readFileSync(
  new URL(
    "../src/components/ai-testing/api-automation/api-scenario-ai-review-field.tsx",
    import.meta.url,
  ),
  "utf8",
);

test("AI scenario review uses versioned editable review contracts", () => {
  assert.match(clientSource, /export type ApiScenarioAiReviewPlan/);
  assert.match(clientSource, /schema_version:\s*3/);
  assert.match(clientSource, /review_revision:\s*number/);
  assert.match(clientSource, /saveApiScenarioAiPlanReview/);
  assert.match(clientSource, /expected_review_revision/);
  assert.match(hookSource, /saveAiPlanReview/);
  assert.match(hookSource, /expected_review_revision:\s*aiPlan\.review_revision/);
  assert.match(hookSource, /expected_review_revision:\s*aiPlan\.review_revision[\s\S]*confirmation:\s*"overwrite_draft"/);
});

test("AI scenario review renders one editable card per step", () => {
  assert.match(editorSource, /ApiScenarioAiReviewDrawer/);
  assert.match(reviewDrawerSource, /plan\.steps\.map/);
  assert.match(reviewDrawerSource, /ApiScenarioAiReviewStepCard/);
  assert.match(reviewStepSource, /步骤 \{step\.order\}/);
  assert.match(reviewStepSource, /step\.field_groups/);
  assert.match(reviewStepSource, /已自动确定/);
  assert.match(reviewStepSource, /AI 建议/);
  assert.match(reviewStepSource, /最终值/);
  assert.match(reviewFieldSource, /环境变量/);
  assert.match(reviewFieldSource, /上游输出/);
  assert.doesNotMatch(reviewDrawerSource + reviewStepSource + reviewFieldSource, /置信度|当前环境未提供|原因/);
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

test("AI orchestration submits without blocking the editor while the plan generates", () => {
  assert.match(editorSource, /AiOrchestrationDrawer/);
  assert.match(editorSource, /<Drawer direction="right"/);
  assert.doesNotMatch(editorSource, /<Drawer direction="right"[^>]*modal=\{false\}/);
  assert.match(editorSource, /onOpenChange=\{setAiDrawerOpen\}/);
  assert.doesNotMatch(editorSource, /if \(open \|\| !editor\.aiBusy\) setAiDrawerOpen\(open\)/);
  assert.match(editorSource, /\{busy \? "关闭" : "取消"\}/);
  assert.match(editorSource, /data-\[vaul-drawer-direction=right\]:w-\[min\(92vw,760px\)\]/);
  assert.match(editorSource, /data-\[vaul-drawer-direction=right\]:sm:max-w-\[760px\]/);
  assert.doesNotMatch(editorSource, /function AiOrchestrationDialog/);
  assert.match(editorSource, /await onGenerate\(goal\.trim\(\), \{ requireCleanup \}\)/);
  assert.doesNotMatch(editorSource, /if \(accepted\) onOpenChange\(false\)/);
  assert.match(editorSource, /selectedEndpointIds/);
  assert.match(hookSource, /source_scope: \{ endpoint_ids: endpointIds \}/);
  assert.doesNotMatch(hookSource, /for \(let attempt = 0; attempt < 90;/);
});

test("AI orchestration drawer separates dragging from text selection and copying", () => {
  const headerSource = editorSource.match(/<DrawerHeader[\s\S]*?<\/DrawerHeader>/)?.[0] ?? "";
  const footerSource = editorSource.match(/<DrawerFooter[\s\S]*?<\/DrawerFooter>/)?.[0] ?? "";

  assert.match(drawerSource, /function DrawerHandle/);
  assert.match(drawerSource, /DrawerPrimitive\.Handle/);
  assert.match(editorSource, /<Drawer direction="right" handleOnly/);
  assert.match(headerSource, /className="absolute inset-y-0 left-0[^"]*"[\s\S]*?<DrawerHandle/);
  assert.doesNotMatch(headerSource, /<DrawerHandle[\s\S]*?className="[^"]*absolute/);
  assert.match(editorSource, /className="[^"]*select-text!/);
  assert.match(headerSource, /<OneClipboard[^>]*text=\{formatAiPlanForClipboard\(plan\)\}/);
  assert.match(headerSource, /放弃计划/);
  assert.match(headerSource, /覆盖当前草稿/);
  assert.doesNotMatch(footerSource, /<OneClipboard/);
  assert.doesNotMatch(footerSource, /放弃计划/);
  assert.doesNotMatch(footerSource, /覆盖当前草稿/);
});

test("AI orchestration generation actions stay in the drawer header", () => {
  const headerSource = editorSource.match(/<DrawerHeader[\s\S]*?<\/DrawerHeader>/)?.[0] ?? "";

  assert.match(headerSource, /\{busy \? "关闭" : "取消"\}/);
  assert.match(headerSource, /\{busy \? "正在生成" : "生成编排草稿"\}/);
  assert.doesNotMatch(editorSource, /<DrawerFooter/);
});

test("AI plan apply explicitly overwrites the current draft", () => {
  assert.match(hookSource, /confirmation:\s*"overwrite_draft"/);
  assert.doesNotMatch(hookSource, /expected_revision:\s*aiPlan\.expected_revision/);
  assert.match(clientSource, /confirmation:\s*"overwrite_draft"/);
  assert.match(editorSource, /当前草稿中的步骤修改不会保留/);
});

test("AI plan bindings use structured targets for stable rendering", () => {
  assert.match(clientSource, /export type ApiScenarioAiPlanBinding = \{/);
  assert.match(clientSource, /location: .*json_body.*multipart.*raw_body/);
  assert.match(editorSource, /key=\{`\$\{node\.id\}-\$\{binding\.target\.location\}-\$\{binding\.target\.path\}`\}/);
  assert.match(editorSource, /formatBindingTarget\(binding\.target\)/);
  assert.match(editorSource, /AI 完整步骤配置/);
  assert.match(editorSource, /JSON\.stringify\(step\.rawNode, null, 2\)/);
  assert.match(editorSource, /<details className="group border-b last:border-b-0"/);
});

test("AI plan preview explains the execution chain and removes repeated configuration", () => {
  const plan = {
    scenario_name: "生成编码并发起对话",
    description: "先生成编码，再发起 SSE 对话",
    inputs: [{ name: "username", label: "用户名", required: true, description: "本次对话的用户" }],
    nodes: [
      {
        id: "generate",
        type: "api_request",
        endpoint_id: "generate-endpoint",
        name: "生成 segment code",
        bindings: [
          { target: { location: "header", path: "/app-id" }, source: { type: "literal", value: "agent-server" } },
        ],
      },
      {
        id: "dialog",
        type: "api_request",
        endpoint_id: "dialog-endpoint",
        name: "发起 SSE 对话",
        bindings: [
          { target: { location: "header", path: "/app-id" }, source: { type: "literal", value: "agent-server" } },
          {
            target: { location: "multipart", path: "/segment_code" },
            source: { type: "step_output", step_id: "generate", variable: "segment_code" },
          },
          { target: { location: "multipart", path: "/username" }, source: { type: "user_input", name: "username" } },
        ],
      },
    ],
    validation: { errors: [], warnings: ["步骤 dialog 的 multipart /username 需要运行时输入。"] },
  };
  const endpoints = [
    { id: "generate-endpoint", method: "POST", path: "/segment-code/gen", summary: "生成对话编码" },
    { id: "dialog-endpoint", method: "POST", path: "/multi-agent/sse", summary: "发起流式对话" },
  ];

  const view = buildAiPlanPresentation(plan, endpoints, "完成一次流式对话");

  assert.equal(view.goal, "完成一次流式对话");
  assert.equal(view.steps[1].path, "/multi-agent/sse");
  assert.deepEqual(view.steps[1].dependencies[0], {
    stepId: "generate",
    stepName: "生成 segment code",
    variable: "segment_code",
    target: "segment_code",
  });
  assert.equal(view.commonParameters.length, 1);
  assert.equal(view.commonParameters[0].value, "agent-server");
  assert.equal(
    view.steps[1].parameters.some((parameter) => parameter.name === "app-id"),
    false,
  );
  assert.deepEqual(view.actionItems[0].targets, ["发起 SSE 对话 · username"]);
});

test("AI plan preview keeps complete literal and input default values", () => {
  const view = buildAiPlanPresentation(
    {
      scenario_name: "值展示",
      inputs: [
        {
          name: "data",
          label: "请求数据",
          required: true,
          default_value: { question: "上海今天的天气怎么样", stream: true },
        },
      ],
      nodes: [
        {
          id: "dialog",
          type: "api_request",
          endpoint_id: "dialog-endpoint",
          bindings: [
            {
              target: { location: "header", path: "/app-id" },
              source: { type: "literal", value: "multi-agent-server" },
            },
            { target: { location: "multipart", path: "/data" }, source: { type: "user_input", name: "data" } },
          ],
        },
      ],
      validation: { errors: [], warnings: [] },
    },
    [{ id: "dialog-endpoint", method: "POST", path: "/multi-agent/sse", summary: "发起流式对话" }],
  );

  assert.equal(view.steps[0].parameters[0].value, "multi-agent-server");
  assert.equal(view.steps[0].parameters[1].value, '{"question":"上海今天的天气怎么样","stream":true}');
  assert.equal(view.actionItems[0].value, '{"question":"上海今天的天气怎么样","stream":true}');
});

test("top running task cards link back to task details", () => {
  assert.match(taskIndicatorSource, /detailUrl: item\.detail_url/);
  assert.match(taskIndicatorSource, /<Link[^>]*href=\{task\.detailUrl\}/);
  assert.match(taskIndicatorSource, /查看任务/);
});
