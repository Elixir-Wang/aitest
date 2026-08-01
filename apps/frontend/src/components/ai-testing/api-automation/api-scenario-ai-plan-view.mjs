const LOCATION_LABELS = {
  path: "路径参数",
  query: "查询参数",
  header: "请求头",
  cookie: "Cookie",
  json_body: "JSON 请求体",
  form: "表单",
  multipart: "Multipart 表单",
  raw_body: "原始请求体",
};

function displayValue(value) {
  if (typeof value === "string") return value;
  if (value === undefined) return "";
  return JSON.stringify(value);
}

function sourceKey(source) {
  return JSON.stringify(source ?? {});
}

function targetName(target) {
  return String(target?.path ?? "").replace(/^\//, "") || "请求参数";
}

function describeSource(source, inputs, nodeNames) {
  if (!source || typeof source !== "object") {
    return { label: "来源尚未确定", value: "待确认" };
  }
  if (source.type === "literal") {
    return { label: "固定值", value: displayValue(source.value) };
  }
  if (source.type === "user_input") {
    const input = inputs.get(source.name);
    const hasDefault = input && input.default_value !== null && input.default_value !== undefined;
    return {
      label: `用户输入 · ${source.name ?? "未命名参数"}`,
      value: hasDefault ? displayValue(input.default_value) : "运行前填写",
    };
  }
  if (source.type === "step_output") {
    const stepName = nodeNames.get(source.step_id) ?? source.step_id ?? "前序步骤";
    return {
      label: `来自步骤「${stepName}」`,
      value: source.variable ? `运行时输出 · ${source.variable}` : "运行时输出",
    };
  }
  if (source.type === "environment") {
    return { label: "运行环境", value: `运行时读取 · ${source.key ?? "环境变量"}` };
  }
  if (source.type === "secret") {
    return { label: "环境密钥", value: `运行时读取 · ${source.key ?? "密钥"}` };
  }
  if (source.type === "scenario") {
    return { label: "场景变量", value: `运行时读取 · ${source.name ?? source.variable ?? "变量"}` };
  }
  if (source.type === "generated") {
    return { label: "系统生成", value: source.generator ?? "运行时生成" };
  }
  return { label: source.type ?? "来源尚未确定", value: "待确认" };
}

function toParameter(binding, inputs, nodeNames) {
  const source = describeSource(binding.source, inputs, nodeNames);
  return {
    key: `${binding.target?.location ?? "request"}:${binding.target?.path ?? ""}:${sourceKey(binding.source)}`,
    name: targetName(binding.target),
    location: LOCATION_LABELS[binding.target?.location] ?? binding.target?.location ?? "请求参数",
    source: source.label,
    value: source.value,
    rawTarget: binding.target,
    rawSource: binding.source,
  };
}

export function buildAiPlanPresentation(plan, endpoints, submittedGoal = "") {
  const endpointById = new Map((endpoints ?? []).map((endpoint) => [endpoint.id, endpoint]));
  const nodeNames = new Map((plan.nodes ?? []).map((node) => [node.id, node.name || node.id]));
  const inputs = new Map((plan.inputs ?? []).map((input) => [input.name, input]));
  const bindingOccurrences = new Map();

  for (const node of plan.nodes ?? []) {
    for (const binding of node.bindings ?? []) {
      const key = `${binding.target?.location ?? "request"}:${binding.target?.path ?? ""}:${sourceKey(binding.source)}`;
      const occurrences = bindingOccurrences.get(key) ?? [];
      occurrences.push(node.id);
      bindingOccurrences.set(key, occurrences);
    }
  }

  const commonKeys = new Set(
    [...bindingOccurrences.entries()].filter(([, nodeIds]) => new Set(nodeIds).size > 1).map(([key]) => key),
  );
  const commonParameters = [];
  const seenCommon = new Set();
  const steps = (plan.nodes ?? []).map((node, index) => {
    const endpoint = endpointById.get(node.endpoint_id);
    const parameters = [];
    const dependencies = [];
    for (const binding of node.bindings ?? []) {
      const parameter = toParameter(binding, inputs, nodeNames);
      if (binding.source?.type === "step_output") {
        dependencies.push({
          stepId: binding.source.step_id,
          stepName: nodeNames.get(binding.source.step_id) ?? binding.source.step_id,
          variable: binding.source.variable,
          target: parameter.name,
        });
      }
      if (commonKeys.has(parameter.key)) {
        if (!seenCommon.has(parameter.key)) {
          seenCommon.add(parameter.key);
          commonParameters.push({
            ...parameter,
            usedBy: bindingOccurrences.get(parameter.key)?.map((nodeId) => nodeNames.get(nodeId) ?? nodeId) ?? [],
          });
        }
      } else {
        parameters.push(parameter);
      }
    }
    return {
      id: node.id,
      index: index + 1,
      name: node.name || endpoint?.summary || node.id,
      purpose: endpoint?.summary || node.name || "执行场景步骤",
      method: endpoint?.method ?? node.type,
      path: endpoint?.path ?? "辅助步骤",
      phase: node.phase ?? "main",
      parameters,
      dependencies,
      rawNode: node,
    };
  });

  const actionItems = (plan.inputs ?? [])
    .filter((input) => input.required)
    .map((input) => {
      const targets = [];
      for (const node of plan.nodes ?? []) {
        for (const binding of node.bindings ?? []) {
          if (binding.source?.type === "user_input" && binding.source.name === input.name) {
            targets.push(`${nodeNames.get(node.id) ?? node.id} · ${targetName(binding.target)}`);
          }
        }
      }
      return {
        name: input.name,
        label: input.label || input.name,
        description: input.description || "运行场景前填写此值",
        value:
          input.default_value !== null && input.default_value !== undefined
            ? displayValue(input.default_value)
            : "尚未填写",
        targets: [...new Set(targets)],
      };
    });

  return {
    goal: submittedGoal.trim() || plan.description || plan.scenario_name,
    steps,
    commonParameters,
    actionItems,
    diagnostics: [...new Set([...(plan.validation?.errors ?? []), ...(plan.validation?.warnings ?? [])])],
  };
}
