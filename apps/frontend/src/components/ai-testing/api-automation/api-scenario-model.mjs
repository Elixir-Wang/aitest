import { createId } from "../../../lib/create-id.mjs";

export function createEndpointStep(endpoint, projectId, scenarioId = "", stepId = `apistep-${createId()}`) {
  return {
    id: stepId,
    scenario_id: scenarioId,
    project_id: projectId,
    step_type: "api_request",
    endpoint_id: endpoint.id,
    api_test_case_id: null,
    step_order: 0,
    name: endpoint.summary || `${endpoint.method} ${endpoint.path}`,
    request_overrides: { request: {}, test_data: {} },
    bindings: [],
    extractors: [],
    assertions: [],
    control_config: {},
    on_failure: "stop",
    enabled: true,
    created_at: "",
    updated_at: "",
  };
}

const utilityDefaults = {
  condition: { name: "条件判断", control_config: { source: { type: "literal", value: true }, operator: "truthy" } },
  wait: { name: "固定等待", control_config: { duration_ms: 1000 } },
  poll: { name: "轮询等待", control_config: { interval_ms: 1000, timeout_ms: 30000 } },
  assign: { name: "数据赋值", control_config: { name: "variable", source: { type: "literal", value: "" } } },
};

export function createUtilityStep(stepType, projectId, scenarioId = "", stepId = `apistep-${createId()}`) {
  const defaults = utilityDefaults[stepType];
  if (!defaults) throw new Error(`Unsupported utility step: ${stepType}`);
  return {
    id: stepId,
    scenario_id: scenarioId,
    project_id: projectId,
    step_type: stepType,
    endpoint_id: null,
    api_test_case_id: null,
    step_order: 0,
    name: defaults.name,
    request_overrides: { request: {}, test_data: {} },
    bindings: [],
    extractors: [],
    assertions: [],
    control_config: structuredClone(defaults.control_config),
    on_failure: "stop",
    enabled: true,
    created_at: "",
    updated_at: "",
  };
}

export function moveScenarioStep(steps, activeId, overId) {
  const activeIndex = steps.findIndex((step) => step.id === activeId);
  const overIndex = steps.findIndex((step) => step.id === overId);
  if (activeIndex < 0 || overIndex < 0 || activeIndex === overIndex) return steps;
  const next = [...steps];
  const [active] = next.splice(activeIndex, 1);
  next.splice(overIndex, 0, active);
  return next.map((step, stepOrder) => ({ ...step, step_order: stepOrder }));
}

// Keep persistence payloads separate from server response metadata.
export function toScenarioStepInput(step, stepOrder) {
  return {
    id: step.id,
    step_type: step.step_type,
    api_test_case_id: step.api_test_case_id ?? null,
    endpoint_id: step.endpoint_id ?? null,
    step_order: stepOrder,
    name: step.name || "",
    request_overrides: step.request_overrides || {},
    bindings: step.bindings || [],
    extractors: step.extractors || [],
    assertions: step.assertions || [],
    control_config: step.control_config || {},
    on_failure: step.on_failure || "stop",
    enabled: step.enabled !== false,
  };
}

export function buildVariableOptions(steps, activeStepId, scenarioVariables = {}, environmentVariables = {}) {
  const activeIndex = steps.findIndex((step) => step.id === activeStepId);
  const precedingSteps = activeIndex < 0 ? steps : steps.slice(0, activeIndex);
  return {
    stepOutputs: precedingSteps.flatMap((step) =>
      [
        ...(step.extractors || []),
        ...(step.step_type === "assign" && step.control_config?.name
          ? [{ name: String(step.control_config.name) }]
          : []),
      ]
        .filter((extractor) => extractor.name)
        .map((extractor) => ({ stepId: step.id, stepName: step.name, name: extractor.name })),
    ),
    scenarioVariables: Object.keys(scenarioVariables),
    environmentVariables: Object.keys(environmentVariables),
  };
}

export function validateScenarioDraft(draft) {
  const errors = [];
  const warnings = [];
  if (!String(draft.name || "").trim()) errors.push("请填写场景名称。");
  const enabledSteps = (draft.steps || []).filter((step) => step.enabled);
  if (enabledSteps.length === 0) errors.push("场景至少需要一个启用步骤。");
  const stepIndexes = new Map(enabledSteps.map((step, index) => [step.id, index]));
  const stepOutputs = new Map();

  enabledSteps.forEach((step, index) => {
    const label = `步骤 ${index + 1}（${step.name || step.id}）`;
    const config = step.control_config || {};
    if (["api_request", "poll"].includes(step.step_type) && !step.endpoint_id) {
      errors.push(`${label}必须选择接口资产。`);
    }
    if (step.step_type === "wait" && !(Number(config.duration_ms) >= 0 && Number(config.duration_ms) <= 300000)) {
      errors.push(`${label}的等待时长必须在 0 到 300000 毫秒之间。`);
    }
    if (step.step_type === "poll") {
      if (!(Number(config.interval_ms) > 0)) errors.push(`${label}的轮询间隔必须大于 0。`);
      if (!(Number(config.timeout_ms) > 0)) errors.push(`${label}的轮询超时必须大于 0。`);
      if ((step.assertions || []).length === 0) errors.push(`${label}至少需要一个结束断言。`);
    }
    if (step.step_type === "assign") {
      if (!String(config.name || "").trim()) errors.push(`${label}必须填写变量名。`);
      validateSource(config.source, label, index, stepIndexes, stepOutputs, errors);
    }
    if (step.step_type === "condition") {
      validateSource(config.source, label, index, stepIndexes, stepOutputs, errors);
      if (
        !["equals", "not_equals", "contains", "not_contains", "truthy", "falsy", "gt", "gte", "lt", "lte"].includes(
          config.operator,
        )
      ) {
        errors.push(`${label}存在不支持的条件操作符。`);
      }
    }
    const extractorNames = new Set();
    for (const extractor of step.extractors || []) {
      const name = String(extractor.name || "").trim();
      if (!name) errors.push(`${label}存在未命名的响应提取。`);
      else if (extractorNames.has(name)) errors.push(`${label}重复提取变量 ${name}。`);
      else extractorNames.add(name);
    }
    if (step.step_type === "assign" && String(config.name || "").trim()) extractorNames.add(String(config.name).trim());
    stepOutputs.set(step.id, extractorNames);
    for (const binding of step.bindings || []) {
      if (binding?.source?.type !== "step_output") continue;
      const sourceStepId = String(binding.source.step_id || "");
      const sourceIndex = stepIndexes.get(sourceStepId);
      if (sourceIndex === undefined) errors.push(`${label}引用的步骤不存在。`);
      else if (sourceIndex >= index) errors.push(`${label}只能引用前序步骤输出。`);
      else if (!stepOutputs.get(sourceStepId)?.has(String(binding.source.variable || ""))) {
        errors.push(`${label}引用了前序步骤未提取的变量 ${binding.source.variable || ""}。`);
      }
    }
    if (step.step_type === "api_request" && (step.assertions || []).length === 0) {
      warnings.push(`${label}没有断言。`);
    }
  });

  return { valid: errors.length === 0, errors, warnings };
}

function validateSource(source, label, currentIndex, stepIndexes, stepOutputs, errors) {
  const sourceType = source?.type;
  if (["literal", "scenario", "environment"].includes(sourceType)) return;
  if (sourceType !== "step_output") {
    errors.push(`${label}存在不支持的变量来源。`);
    return;
  }
  const sourceStepId = String(source.step_id || "");
  const sourceIndex = stepIndexes.get(sourceStepId);
  if (sourceIndex === undefined) errors.push(`${label}引用的步骤不存在。`);
  else if (sourceIndex >= currentIndex) errors.push(`${label}只能引用前序步骤输出。`);
  else if (!stepOutputs.get(sourceStepId)?.has(String(source.variable || ""))) {
    errors.push(`${label}引用了前序步骤未输出的变量 ${source.variable || ""}。`);
  }
}
