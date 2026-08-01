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

export function normalizeRequestLifecycleConfig(step) {
  const config = step?.control_config || {};
  return {
    ...config,
    timeout_ms: Number(config.timeout_ms ?? 30000),
    retries: Number(config.retries ?? 0),
    retry_interval_ms: Number(config.retry_interval_ms ?? 1000),
    pre_request: normalizeLifecyclePhase(config.pre_request),
    post_response: normalizeLifecyclePhase(config.post_response),
  };
}

const utilityDefaults = {
  condition: { name: "条件判断", control_config: { source: { type: "literal", value: true }, operator: "truthy" } },
  wait: { name: "固定等待", control_config: { duration_ms: 1000 } },
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
  const requestOverrides = structuredClone(step.request_overrides || {});
  const bindings = [];
  for (const binding of step.bindings || []) {
    if (binding?.source?.type === "literal") {
      setPointer(requestOverrides, binding.target, binding.source.value);
    } else {
      bindings.push(binding);
    }
  }
  return {
    id: step.id,
    step_type: step.step_type,
    api_test_case_id: step.api_test_case_id ?? null,
    endpoint_id: step.endpoint_id ?? null,
    step_order: stepOrder,
    name: step.name || "",
    request_overrides: requestOverrides,
    bindings,
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
    if (step.step_type === "api_request" && !step.endpoint_id) {
      errors.push(`${label}必须选择接口资产。`);
    }
    if (step.step_type === "wait" && !(Number(config.duration_ms) >= 0 && Number(config.duration_ms) <= 300000)) {
      errors.push(`${label}的等待时长必须在 0 到 300000 毫秒之间。`);
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
      if (extractor.source === "sse_event_json") {
        if (!String(extractor.event || "").trim()) errors.push(`${label}的 SSE 事件名称不能为空。`);
        if (!String(extractor.path || extractor.expression || "").trim())
          errors.push(`${label}的 SSE 提取路径不能为空。`);
      }
    }
    if (step.step_type === "assign" && String(config.name || "").trim()) extractorNames.add(String(config.name).trim());
    stepOutputs.set(step.id, extractorNames);
    for (const binding of step.bindings || []) {
      validateSource(binding?.source, label, index, stepIndexes, stepOutputs, errors);
    }
    validateRequestLifecycle(step, label, index, stepIndexes, stepOutputs, errors);
    if (step.step_type === "api_request" && (step.assertions || []).length === 0) {
      warnings.push(`${label}没有断言。`);
    }
  });

  return { valid: errors.length === 0, errors: [...new Set(errors)], warnings: [...new Set(warnings)] };
}

function validateSource(source, label, currentIndex, stepIndexes, stepOutputs, errors) {
  const sourceType = source?.type;
  if (["literal", "scenario", "environment", "user_input", "secret", "generated"].includes(sourceType)) return;
  if (sourceType === "object") {
    for (const child of Object.values(source.properties || {})) {
      validateSource(child, label, currentIndex, stepIndexes, stepOutputs, errors);
    }
    return;
  }
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

function normalizeLifecyclePhase(phase) {
  return {
    actions: Array.isArray(phase?.actions) ? phase.actions : [],
    script: typeof phase?.script === "string" ? phase.script : "",
  };
}

export function formatValueSource(source, stepName = "步骤") {
  if (!source || typeof source !== "object") return "未配置";
  if (source.type === "literal") return formatLiteralValue(source.value);
  if (source.type === "step_output") return `{{ ${stepName}.${String(source.variable || "")} }}`;
  if (source.type === "environment" || source.type === "secret") {
    return `{{ ${source.type}.${String(source.key || "")} }}`;
  }
  if (source.type === "scenario" || source.type === "user_input") {
    return `{{ ${source.type}.${String(source.name || "")} }}`;
  }
  if (source.type === "generated") return `{{ generated.${String(source.generator || "")} }}`;
  if (source.type === "object") return `对象（${Object.keys(source.properties || {}).length} 个字段）`;
  return `不支持的来源（${String(source.type || "unknown")}）`;
}

export function buildEndpointRequestFields(endpoint) {
  const parameterFields = (endpoint?.parameters || [])
    .map((parameter) => createRequestField(parameter, String(parameter?.in || "query")))
    .filter(Boolean);
  const requestBody = endpoint?.request_body || {};
  const content = requestBody.content && typeof requestBody.content === "object" ? requestBody.content : {};
  const mediaType = selectRequestMediaType(content);
  const bodyDefinition = mediaType ? content[mediaType] : null;
  const fallbackSchema = requestBody.schema && typeof requestBody.schema === "object" ? requestBody.schema : null;
  const schema =
    bodyDefinition?.schema && typeof bodyDefinition.schema === "object" ? bodyDefinition.schema : fallbackSchema;
  const bodyMode = mediaTypeToBodyMode(mediaType, schema);
  const bodyLocation = bodyModeToLocation(bodyMode);
  const required = new Set(Array.isArray(schema?.required) ? schema.required.map(String) : []);
  const bodyFields = Object.entries(schema?.properties || {})
    .map(([key, property]) =>
      createRequestField({ ...property, name: key, required: required.has(key), schema: property }, bodyLocation),
    )
    .filter(Boolean);
  return { bodyMode, mediaType, fields: [...parameterFields, ...bodyFields] };
}

function validateRequestLifecycle(step, label, currentIndex, stepIndexes, stepOutputs, errors) {
  if (step.step_type !== "api_request") return;
  const request = step.request_overrides?.request || {};
  const rawBody = request.body_raw ?? request.raw_body;
  if (request.body_mode === "json" && typeof rawBody === "string" && rawBody.trim()) {
    try {
      JSON.parse(rawBody);
    } catch {
      errors.push(`${label}的 JSON Body 格式无效。`);
    }
  }
  const lifecycle = normalizeRequestLifecycleConfig(step);
  validateLifecycleActions(
    lifecycle.pre_request.actions,
    `${label}的前置变量动作`,
    currentIndex,
    stepIndexes,
    stepOutputs,
    errors,
  );
  validateLifecycleActions(
    lifecycle.post_response.actions,
    `${label}的后置变量动作`,
    currentIndex,
    stepIndexes,
    stepOutputs,
    errors,
  );
}

function validateLifecycleActions(actions, actionLabel, currentIndex, stepIndexes, stepOutputs, errors) {
  for (const action of actions) {
    if (action?.type !== "set_variable" || !String(action?.name || "").trim()) {
      errors.push(`${actionLabel}配置不完整。`);
      continue;
    }
    validateSource(action.source, actionLabel, currentIndex, stepIndexes, stepOutputs, errors);
  }
}

function createRequestField(definition, location) {
  const key = String(definition?.name || "");
  if (!key) return null;
  const schema = definition?.schema && typeof definition.schema === "object" ? definition.schema : definition;
  return {
    key,
    location,
    target: requestFieldTarget(location, key),
    required: Boolean(definition?.required),
    description: String(definition?.description || schema?.description || ""),
    schema,
    defaultValue:
      schema?.default ?? (Array.isArray(schema?.enum) && schema.enum.length === 1 ? schema.enum[0] : schema?.example),
  };
}

function requestFieldTarget(location, key) {
  const sections = {
    path: "path_params",
    query: "query",
    header: "headers",
    cookie: "cookies",
    json_body: "json",
    body: "json",
    form: "form",
    multipart: "multipart_form",
  };
  return `/request/${sections[location] || "query"}/${escapePointer(key)}`;
}

function selectRequestMediaType(content) {
  const mediaTypes = Object.keys(content || {});
  return (
    ["application/json", "multipart/form-data", "application/x-www-form-urlencoded"].find(
      (mediaType) => mediaType in content,
    ) ||
    mediaTypes[0] ||
    ""
  );
}

function mediaTypeToBodyMode(mediaType, schema) {
  if (mediaType === "multipart/form-data") return "multipart";
  if (mediaType === "application/x-www-form-urlencoded") return "form";
  if (mediaType === "application/json" || schema) return "json";
  return mediaType ? "raw" : "none";
}

function bodyModeToLocation(bodyMode) {
  if (bodyMode === "multipart") return "multipart";
  if (bodyMode === "form") return "form";
  return "json_body";
}

function setPointer(document, pointer, value) {
  const parts = String(pointer || "")
    .split("/")
    .filter(Boolean)
    .map(unescapePointer);
  if (parts.length === 0) return document;
  let current = document;
  for (const part of parts.slice(0, -1)) {
    if (!current[part] || typeof current[part] !== "object" || Array.isArray(current[part])) current[part] = {};
    current = current[part];
  }
  current[parts.at(-1)] = value;
  return document;
}

function formatLiteralValue(value) {
  if (typeof value === "string") return value;
  if (value === undefined) return "未配置";
  return JSON.stringify(value);
}

function escapePointer(value) {
  return String(value).replaceAll("~", "~0").replaceAll("/", "~1");
}

function unescapePointer(value) {
  return String(value).replaceAll("~1", "/").replaceAll("~0", "~");
}
