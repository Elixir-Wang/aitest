import {
  buildVariableOptions,
  createEndpointStep,
  createUtilityStep,
  moveScenarioStep,
  validateScenarioDraft,
} from "../src/components/ai-testing/api-automation/api-scenario-model.mjs";
import assert from "node:assert/strict";
import test from "node:test";

const endpoint = {
  id: "apiend-orders",
  method: "POST",
  path: "/orders",
  summary: "创建订单",
};

test("generates scenario step ids when crypto.randomUUID is unavailable", () => {
  const cryptoDescriptor = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  Object.defineProperty(globalThis, "crypto", {
    configurable: true,
    value: {
      getRandomValues(bytes) {
        bytes.fill(1);
        return bytes;
      },
    },
  });

  try {
    assert.match(createEndpointStep(endpoint, "project-1").id, /^apistep-/);
    assert.match(createUtilityStep("wait", "project-1").id, /^apistep-/);
  } finally {
    if (cryptoDescriptor) {
      Object.defineProperty(globalThis, "crypto", cryptoDescriptor);
    } else {
      delete globalThis.crypto;
    }
  }
});

test("creates scenario steps directly from endpoint assets", () => {
  const step = createEndpointStep(endpoint, "project-1", "scenario-1", "step-1");

  assert.equal(step.endpoint_id, "apiend-orders");
  assert.equal(step.api_test_case_id, null);
  assert.equal(step.step_type, "api_request");
  assert.equal(step.name, "创建订单");
});

test("creates utility steps with executable default control config", () => {
  const wait = createUtilityStep("wait", "project-1", "scenario-1", "wait-1");
  const assign = createUtilityStep("assign", "project-1", "scenario-1", "assign-1");

  assert.equal(wait.endpoint_id, null);
  assert.deepEqual(wait.control_config, { duration_ms: 1000 });
  assert.equal(assign.name, "数据赋值");
  assert.deepEqual(assign.control_config, {
    name: "variable",
    source: { type: "literal", value: "" },
  });
});

test("exposes assign outputs to downstream variable selectors", () => {
  const assign = createUtilityStep("assign", "project-1", "scenario-1", "assign-1");
  const request = createEndpointStep(endpoint, "project-1", "scenario-1", "step-2");

  const options = buildVariableOptions([assign, request], request.id);

  assert.deepEqual(options.stepOutputs, [{ stepId: "assign-1", stepName: "数据赋值", name: "variable" }]);
});

test("validates utility step control config before saving", () => {
  const wait = {
    ...createUtilityStep("wait", "project-1", "scenario-1", "wait-1"),
    control_config: { duration_ms: 400000 },
  };
  const assign = {
    ...createUtilityStep("assign", "project-1", "scenario-1", "assign-1"),
    control_config: { name: "", source: {} },
  };
  const poll = createUtilityStep("poll", "project-1", "scenario-1", "poll-1");

  const result = validateScenarioDraft({ name: "异步流程", steps: [wait, assign, poll] });

  assert.equal(result.valid, false);
  assert.ok(result.errors.some((error) => error.includes("等待时长")));
  assert.ok(result.errors.some((error) => error.includes("变量名")));
  assert.ok(result.errors.some((error) => error.includes("结束断言")));
});

test("moves steps and rewrites stable step order", () => {
  const first = createEndpointStep(endpoint, "project-1", "scenario-1", "step-1");
  const second = createEndpointStep(
    { ...endpoint, id: "apiend-query", summary: "查询订单" },
    "project-1",
    "scenario-1",
    "step-2",
  );

  const moved = moveScenarioStep([first, second], "step-2", "step-1");

  assert.deepEqual(
    moved.map((step) => [step.id, step.step_order]),
    [
      ["step-2", 0],
      ["step-1", 1],
    ],
  );
});

test("only exposes outputs from preceding steps", () => {
  const steps = [
    { ...createEndpointStep(endpoint, "project-1", "scenario-1", "step-1"), extractors: [{ name: "token" }] },
    { ...createEndpointStep(endpoint, "project-1", "scenario-1", "step-2"), extractors: [{ name: "orderId" }] },
  ];

  const options = buildVariableOptions(steps, "step-2", { tenant: "demo" }, { region: "cn" });

  assert.deepEqual(options.stepOutputs, [{ stepId: "step-1", stepName: "创建订单", name: "token" }]);
});

test("rejects forward output references", () => {
  const steps = [
    {
      ...createEndpointStep(endpoint, "project-1", "scenario-1", "step-1"),
      bindings: [
        {
          target: "/request/body/orderId",
          source: { type: "step_output", step_id: "step-2", variable: "orderId" },
        },
      ],
    },
    { ...createEndpointStep(endpoint, "project-1", "scenario-1", "step-2"), extractors: [{ name: "orderId" }] },
  ];

  const issues = validateScenarioDraft({ name: "订单链路", steps });

  assert.ok(issues.errors.some((issue) => issue.includes("只能引用前序步骤")));
});
