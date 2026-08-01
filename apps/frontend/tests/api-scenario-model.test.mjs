import {
  buildEndpointRequestFields,
  buildVariableOptions,
  createEndpointStep,
  createUtilityStep,
  formatValueSource,
  moveScenarioStep,
  normalizeRequestLifecycleConfig,
  toScenarioStepInput,
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

test("formats every persisted value source with its canonical field", () => {
  assert.equal(formatValueSource({ type: "literal", value: "multi-agent-server" }), "multi-agent-server");
  assert.equal(formatValueSource({ type: "secret", key: "robot_key" }), "{{ secret.robot_key }}");
  assert.equal(formatValueSource({ type: "environment", key: "region" }), "{{ environment.region }}");
  assert.equal(formatValueSource({ type: "scenario", name: "username" }), "{{ scenario.username }}");
  assert.equal(formatValueSource({ type: "user_input", name: "question" }), "{{ user_input.question }}");
  assert.equal(formatValueSource({ type: "generated", generator: "uuid4" }), "{{ generated.uuid4 }}");
  assert.equal(
    formatValueSource({ type: "step_output", step_id: "step-1", variable: "token" }, "登录"),
    "{{ 登录.token }}",
  );
  assert.equal(
    formatValueSource({ type: "object", properties: { question: { type: "user_input", name: "question" } } }),
    "对象（1 个字段）",
  );
});

test("expands endpoint parameters and multipart body into canonical request fields", () => {
  const fields = buildEndpointRequestFields({
    parameters: [
      { name: "tenant", in: "query", required: true },
      { name: "X-Token", in: "header", required: true },
    ],
    request_body: {
      content: {
        "multipart/form-data": {
          schema: {
            type: "object",
            required: ["data"],
            properties: {
              data: { type: "string", description: "JSON string" },
              file: { type: "string", format: "binary" },
            },
          },
        },
      },
    },
  });

  assert.equal(fields.bodyMode, "multipart");
  assert.deepEqual(
    fields.fields.map(({ key, location, target }) => ({ key, location, target })),
    [
      { key: "tenant", location: "query", target: "/request/query/tenant" },
      { key: "X-Token", location: "header", target: "/request/headers/X-Token" },
      { key: "data", location: "multipart", target: "/request/multipart_form/data" },
      { key: "file", location: "multipart", target: "/request/multipart_form/file" },
    ],
  );
});

test("normalizes request lifecycle defaults without replacing existing step fields", () => {
  const step = {
    ...createEndpointStep(endpoint, "project-1", "scenario-1", "step-1"),
    request_overrides: { request: { headers: { "X-Tenant": "demo" } }, test_data: {} },
    control_config: { timeout_ms: 15000 },
  };

  const lifecycle = normalizeRequestLifecycleConfig(step);

  assert.deepEqual(lifecycle.pre_request, { actions: [], script: "" });
  assert.deepEqual(lifecycle.post_response, { actions: [], script: "" });
  assert.equal(lifecycle.timeout_ms, 15000);
  assert.equal(lifecycle.retries, 0);
  assert.equal(lifecycle.retry_interval_ms, 1000);
  assert.deepEqual(step.request_overrides.request.headers, { "X-Tenant": "demo" });
});

test("rejects malformed raw JSON and incomplete lifecycle actions", () => {
  const step = {
    ...createEndpointStep(endpoint, "project-1", "scenario-1", "step-1"),
    request_overrides: {
      request: { body_mode: "json", raw_body: "{invalid" },
      test_data: {},
    },
    control_config: {
      pre_request: { actions: [{ type: "set_variable", name: "", source: { type: "literal", value: 1 } }] },
    },
  };

  const result = validateScenarioDraft({ name: "订单流程", steps: [step] });

  assert.equal(result.valid, false);
  assert.ok(result.errors.some((error) => error.includes("JSON Body")));
  assert.ok(result.errors.some((error) => error.includes("前置变量动作")));
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

test("serializes only writable step fields and preserves test case references", () => {
  const step = {
    id: "step-1",
    scenario_id: "scenario-1",
    project_id: "project-1",
    step_type: "api_request",
    api_test_case_id: "case-1",
    endpoint_id: "apiend-orders",
    step_order: 7,
    name: "创建订单",
    request_overrides: { request: {} },
    bindings: [],
    extractors: [],
    assertions: [],
    control_config: {},
    on_failure: "stop",
    enabled: true,
    created_at: "created",
    updated_at: "updated",
  };

  assert.deepEqual(toScenarioStepInput(step, 0), {
    id: "step-1",
    step_type: "api_request",
    api_test_case_id: "case-1",
    endpoint_id: "apiend-orders",
    step_order: 0,
    name: "创建订单",
    request_overrides: { request: {} },
    bindings: [],
    extractors: [],
    assertions: [],
    control_config: {},
    on_failure: "stop",
    enabled: true,
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
  const result = validateScenarioDraft({ name: "异步流程", steps: [wait, assign] });

  assert.equal(result.valid, false);
  assert.ok(result.errors.some((error) => error.includes("等待时长")));
  assert.ok(result.errors.some((error) => error.includes("变量名")));
});

test("rejects removed polling utility steps", () => {
  assert.throws(() => createUtilityStep("poll", "project-1", "scenario-1", "poll-1"), /Unsupported utility step: poll/);
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

test("requires event and path for SSE event JSON extractors", () => {
  const step = {
    ...createEndpointStep(endpoint, "project-1", "scenario-1", "step-1"),
    extractors: [{ name: "dialog_id", source: "sse_event_json", event: "", path: "" }],
  };

  const issues = validateScenarioDraft({ name: "SSE 对话", steps: [step] });

  assert.equal(issues.valid, false);
  assert.ok(issues.errors.some((issue) => issue.includes("SSE 事件名称")));
  assert.ok(issues.errors.some((issue) => issue.includes("SSE 提取路径")));
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

test("serializes literal bindings as request overrides without losing their values", () => {
  const step = {
    ...createEndpointStep(endpoint, "project-1", "scenario-1", "step-1"),
    request_overrides: {},
    bindings: [
      {
        target: "/request/headers/cybertron-app-id",
        source: { type: "literal", value: "multi-agent-server" },
      },
      {
        target: "/request/headers/cybertron-robot-key",
        source: { type: "secret", key: "robot_key" },
      },
    ],
  };

  const serialized = toScenarioStepInput(step, 0);

  assert.equal(serialized.request_overrides.request.headers["cybertron-app-id"], "multi-agent-server");
  assert.deepEqual(serialized.bindings, [
    {
      target: "/request/headers/cybertron-robot-key",
      source: { type: "secret", key: "robot_key" },
    },
  ]);
});

test("rejects forward output references nested in object sources", () => {
  const steps = [
    {
      ...createEndpointStep(endpoint, "project-1", "scenario-1", "step-1"),
      bindings: [
        {
          target: "/request/body/payload",
          source: {
            type: "object",
            properties: {
              orderId: { type: "step_output", step_id: "step-2", variable: "orderId" },
            },
          },
        },
      ],
    },
    { ...createEndpointStep(endpoint, "project-1", "scenario-1", "step-2"), extractors: [{ name: "orderId" }] },
  ];

  const issues = validateScenarioDraft({ name: "订单链路", steps });

  assert.ok(issues.errors.some((issue) => issue.includes("只能引用前序步骤")));
});
