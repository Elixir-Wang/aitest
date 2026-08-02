"use client";

import { useEffect } from "react";

import Link from "next/link";

import { Plus, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import type {
  ApiAutomationEndpoint,
  ApiAutomationEnvironment,
  ApiAutomationScenarioAssertion,
  ApiAutomationScenarioBinding,
  ApiAutomationScenarioExtractor,
  ApiAutomationScenarioStep,
} from "@/lib/api-client";
import { createId } from "@/lib/create-id.mjs";
import { cn } from "@/lib/utils";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./api-orchestration-select";
import {
  buildEndpointRequestFields,
  buildVariableOptions,
  normalizeRequestLifecycleConfig,
  resolveRequestFieldValue,
} from "./api-scenario-model.mjs";

type ApiScenarioStepConfigProps = {
  activeStep: ApiAutomationScenarioStep | null;
  endpoints: ApiAutomationEndpoint[];
  environment: ApiAutomationEnvironment | null;
  precedingSteps: ApiAutomationScenarioStep[];
  scenarioVariables: Record<string, unknown>;
  onUpdateStep: (stepId: string, updates: Partial<ApiAutomationScenarioStep>) => void;
  projectId: string;
};

const methodTone: Record<string, string> = {
  GET: "border-blue-200 bg-blue-50 text-blue-700",
  POST: "border-emerald-200 bg-emerald-50 text-emerald-700",
  PUT: "border-amber-200 bg-amber-50 text-amber-700",
  PATCH: "border-violet-200 bg-violet-50 text-violet-700",
  DELETE: "border-red-200 bg-red-50 text-red-700",
};

export function ApiScenarioStepConfig({
  activeStep,
  endpoints,
  environment,
  precedingSteps,
  scenarioVariables,
  onUpdateStep,
  projectId,
}: ApiScenarioStepConfigProps) {
  if (!activeStep) {
    return (
      <div className="grid min-h-0 place-items-center bg-card">
        <div className="max-w-sm text-center">
          <div className="font-semibold text-base">先添加接口资产</div>
          <p className="mt-2 text-muted-foreground text-sm leading-6">
            从左侧执行链路添加接口后，可在这里配置请求参数、响应提取、断言和执行策略。
          </p>
        </div>
      </div>
    );
  }
  const endpoint = endpoints.find((item) => item.id === activeStep.endpoint_id) ?? null;
  const availableSteps = [...precedingSteps, activeStep];
  const variableOptions = buildVariableOptions(
    availableSteps,
    activeStep.id,
    scenarioVariables,
    environment?.variables ?? {},
  );
  const utilityStep = ["assign", "condition", "wait"].includes(activeStep.step_type);

  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-card">
      {utilityStep ? null : (
        <div className="flex h-[72px] shrink-0 items-center justify-between border-b px-5">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {endpoint ? (
                <Badge className={cn("font-mono text-[10px]", methodTone[endpoint.method])} variant="outline">
                  {endpoint.method}
                </Badge>
              ) : null}
              <Input
                className="h-8 max-w-md border-transparent bg-transparent px-1 font-semibold text-sm shadow-none hover:border-border focus-visible:border-border"
                onChange={(event) => onUpdateStep(activeStep.id, { name: event.target.value })}
                value={activeStep.name}
              />
            </div>
            <div className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
              {endpoint?.path ?? "请选择接口资产"}
            </div>
          </div>
          <Button asChild disabled={!endpoint} size="sm" variant="outline">
            <Link
              href={
                endpoint ? `/projects/${projectId}/automation/api?endpoint=${encodeURIComponent(endpoint.id)}` : "#"
              }
            >
              查看接口资产
            </Link>
          </Button>
        </div>
      )}
      {utilityStep ? (
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <UtilityStepEditor
            step={activeStep}
            variableOptions={variableOptions}
            onChange={(updates) => onUpdateStep(activeStep.id, updates)}
          />
        </div>
      ) : (
        <Tabs className="min-h-0 flex-1 gap-0 overflow-hidden" defaultValue="request">
          <TabsList
            className="h-11 w-full shrink-0 justify-start rounded-none border-b bg-muted/15 px-5"
            variant="line"
          >
            <TabsTrigger className="flex-none px-2" value="request">
              请求
            </TabsTrigger>
            <TabsTrigger className="flex-none px-2" value="pre-request">
              前置处理
            </TabsTrigger>
            <TabsTrigger className="flex-none px-2" value="response">
              响应处理 <Count value={activeStep.extractors.length} />
            </TabsTrigger>
            <TabsTrigger className="flex-none px-2" value="assertions">
              断言 <Count value={activeStep.assertions.length} />
            </TabsTrigger>
            <TabsTrigger className="flex-none px-2" value="control">
              执行控制
            </TabsTrigger>
          </TabsList>
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            <TabsContent className="m-0 p-5" value="request">
              <RequestEditor
                bindings={activeStep.bindings}
                endpoint={endpoint}
                requestOverrides={activeStep.request_overrides}
                variableOptions={variableOptions}
                onChange={(updates) => onUpdateStep(activeStep.id, updates)}
              />
            </TabsContent>
            <TabsContent className="m-0 p-5" value="pre-request">
              <LifecyclePhaseEditor
                phase="pre_request"
                step={activeStep}
                title="前置处理"
                variableOptions={variableOptions}
                onChange={(controlConfig) => onUpdateStep(activeStep.id, { control_config: controlConfig })}
              />
            </TabsContent>
            <TabsContent className="m-0 space-y-6 p-5" value="response">
              <ExtractorEditor
                extractors={activeStep.extractors}
                onChange={(extractors) => onUpdateStep(activeStep.id, { extractors })}
              />
              <LifecyclePhaseEditor
                phase="post_response"
                step={activeStep}
                title="后置处理"
                variableOptions={variableOptions}
                onChange={(controlConfig) => onUpdateStep(activeStep.id, { control_config: controlConfig })}
              />
            </TabsContent>
            <TabsContent className="m-0 p-5" value="assertions">
              <AssertionEditor
                assertions={activeStep.assertions}
                onChange={(assertions) => onUpdateStep(activeStep.id, { assertions })}
              />
            </TabsContent>
            <TabsContent className="m-0 p-5" value="control">
              <ControlEditor step={activeStep} onChange={(updates) => onUpdateStep(activeStep.id, updates)} />
            </TabsContent>
          </div>
        </Tabs>
      )}
    </section>
  );
}

function UtilityStepEditor({
  step,
  variableOptions,
  onChange,
}: {
  step: ApiAutomationScenarioStep;
  variableOptions: ReturnType<typeof buildVariableOptions>;
  onChange: (updates: Partial<ApiAutomationScenarioStep>) => void;
}) {
  const config = step.control_config;
  const source = (config.source ?? { type: "literal", value: "" }) as Record<string, unknown>;
  const updateConfig = (updates: Record<string, unknown>) => onChange({ control_config: { ...config, ...updates } });

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="rounded-2xl border border-amber-200 bg-[linear-gradient(135deg,#fffbeb,#fff_68%)] p-5">
        <div className="font-semibold text-amber-950">{utilityTitle(step.step_type)}</div>
        <p className="mt-1 text-amber-900/70 text-sm">{utilityDescription(step.step_type)}</p>
      </div>

      {step.step_type === "assign" ? (
        <div>
          <span className="mb-2 block font-medium text-sm">输出变量名</span>
          <Input
            onChange={(event) => updateConfig({ name: event.target.value })}
            placeholder="例如 orderId"
            value={String(config.name ?? "")}
          />
        </div>
      ) : null}

      {step.step_type === "assign" || step.step_type === "condition" ? (
        <SourceEditor
          source={source}
          variableOptions={variableOptions}
          onChange={(nextSource) => updateConfig({ source: nextSource })}
        />
      ) : null}

      {step.step_type === "condition" ? (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="mb-2 block font-medium text-sm">比较方式</span>
            <Select
              onValueChange={(operator) => updateConfig({ operator })}
              value={String(config.operator ?? "equals")}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="equals">等于</SelectItem>
                <SelectItem value="not_equals">不等于</SelectItem>
                <SelectItem value="contains">包含</SelectItem>
                <SelectItem value="not_contains">不包含</SelectItem>
                <SelectItem value="truthy">为真</SelectItem>
                <SelectItem value="falsy">为假</SelectItem>
                <SelectItem value="gt">大于</SelectItem>
                <SelectItem value="gte">大于等于</SelectItem>
                <SelectItem value="lt">小于</SelectItem>
                <SelectItem value="lte">小于等于</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {!["truthy", "falsy"].includes(String(config.operator)) ? (
            <div>
              <span className="mb-2 block font-medium text-sm">期望值</span>
              <Input
                onChange={(event) => updateConfig({ expected: parseInput(event.target.value) })}
                value={String(config.expected ?? "")}
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {step.step_type === "wait" ? (
        <div>
          <span className="mb-2 block font-medium text-sm">等待时长（毫秒）</span>
          <Input
            max={300000}
            min={0}
            onChange={(event) => updateConfig({ duration_ms: Number(event.target.value) || 0 })}
            type="number"
            value={Number(config.duration_ms ?? 1000)}
          />
        </div>
      ) : null}

      <div className="border-t pt-5">
        <ControlEditor onChange={onChange} step={step} />
      </div>
    </div>
  );
}

function SourceEditor({
  source,
  variableOptions,
  onChange,
}: {
  source: Record<string, unknown>;
  variableOptions: ReturnType<typeof buildVariableOptions>;
  onChange: (source: Record<string, unknown>) => void;
}) {
  const sourceType = String(source.type ?? "literal");
  return (
    <div className="grid grid-cols-[180px_1fr] gap-4">
      <div>
        <span className="mb-2 block font-medium text-sm">数据来源</span>
        <Select onValueChange={(type) => onChange(defaultValueSource(type))} value={sourceType}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="literal">
              {sourceType === "literal" ? displayBindingValue(source.value) : "固定值"}
            </SelectItem>
            <SelectItem value="step_output">前序步骤输出</SelectItem>
            <SelectItem value="scenario">场景变量</SelectItem>
            <SelectItem value="environment">环境变量</SelectItem>
            <SelectItem value="user_input">运行时输入</SelectItem>
            <SelectItem value="secret">密钥引用</SelectItem>
            <SelectItem value="generated">动态生成</SelectItem>
            <SelectItem value="object">对象</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div>
        <span className="mb-2 block font-medium text-sm">来源值</span>
        {sourceType === "literal" ? (
          <Input
            onChange={(event) => onChange({ type: "literal", value: parseInput(event.target.value) })}
            value={String(source.value ?? "")}
          />
        ) : sourceType === "step_output" ? (
          <Select
            onValueChange={(value) => {
              onChange(JSON.parse(value));
            }}
            value={
              source.step_id
                ? JSON.stringify({ type: "step_output", step_id: source.step_id, variable: source.variable })
                : ""
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="选择前序步骤输出" />
            </SelectTrigger>
            <SelectContent>
              {variableOptions.stepOutputs.map((option) => (
                <SelectItem
                  key={`${option.stepId}:${option.name}`}
                  value={JSON.stringify({ type: "step_output", step_id: option.stepId, variable: option.name })}
                >
                  {option.stepName}.{option.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : sourceType === "scenario" || sourceType === "environment" ? (
          <Select
            onValueChange={(value) =>
              onChange(
                sourceType === "environment" ? { type: "environment", key: value } : { type: "scenario", name: value },
              )
            }
            value={String(sourceType === "environment" ? (source.key ?? source.name ?? "") : (source.name ?? ""))}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择变量" />
            </SelectTrigger>
            <SelectContent>
              {(sourceType === "scenario"
                ? variableOptions.scenarioVariables
                : variableOptions.environmentVariables
              ).map((name) => (
                <SelectItem key={name} value={name}>
                  {name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : sourceType === "secret" || sourceType === "user_input" ? (
          <Input
            onChange={(event) =>
              onChange(
                sourceType === "secret"
                  ? { type: "secret", key: event.target.value }
                  : { type: "user_input", name: event.target.value },
              )
            }
            placeholder={sourceType === "secret" ? "密钥标识" : "输入参数名"}
            value={String(sourceType === "secret" ? (source.key ?? "") : (source.name ?? ""))}
          />
        ) : sourceType === "generated" ? (
          <Select
            onValueChange={(generator) => onChange({ type: "generated", generator })}
            value={String(source.generator ?? "uuid4")}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="uuid4">UUID</SelectItem>
              <SelectItem value="timestamp_ms">毫秒时间戳</SelectItem>
              <SelectItem value="timestamp_iso">ISO 时间</SelectItem>
              <SelectItem value="random_string">随机字符串</SelectItem>
            </SelectContent>
          </Select>
        ) : sourceType === "object" ? (
          <Textarea
            className="min-h-28 font-mono text-xs"
            onChange={(event) => {
              try {
                onChange({ type: "object", properties: JSON.parse(event.target.value) });
              } catch {
                // Keep the last valid object source until the JSON becomes valid.
              }
            }}
            value={JSON.stringify(source.properties ?? {}, null, 2)}
          />
        ) : (
          <Input disabled value="不支持的来源" />
        )}
      </div>
    </div>
  );
}

function utilityTitle(stepType: ApiAutomationScenarioStep["step_type"]) {
  const titles: Partial<Record<ApiAutomationScenarioStep["step_type"], string>> = {
    assign: "数据赋值",
    condition: "条件判断",
    wait: "固定等待",
  };
  return titles[stepType] ?? "辅助节点";
}

function utilityDescription(stepType: ApiAutomationScenarioStep["step_type"]) {
  const descriptions: Partial<Record<ApiAutomationScenarioStep["step_type"], string>> = {
    assign: "将固定值、场景变量、环境变量或前序输出保存为新的步骤输出。",
    condition: "计算一个布尔条件，为后续线性链路提供清晰的执行守卫。",
    wait: "在相邻接口之间暂停指定时长，适合等待异步任务进入可查询状态。",
  };
  return descriptions[stepType] ?? "配置增强线性编排行为。";
}

function Count({ value }: { value: number }) {
  return <span className="ml-1 rounded-full bg-muted px-1.5 text-[10px] text-muted-foreground">{value}</span>;
}

function RequestEditor({
  endpoint,
  requestOverrides,
  bindings,
  variableOptions,
  onChange,
}: {
  endpoint: ApiAutomationEndpoint | null;
  requestOverrides: Record<string, unknown>;
  bindings: ApiAutomationScenarioBinding[];
  variableOptions: ReturnType<typeof buildVariableOptions>;
  onChange: (updates: Partial<ApiAutomationScenarioStep>) => void;
}) {
  if (!endpoint)
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-destructive text-sm">
        接口资产已不存在，请重新选择接口。
      </div>
    );
  const requestModel = buildEndpointRequestFields(endpoint);
  const parameterFields = requestModel.fields.filter((field) => ["path", "query"].includes(field.location));
  const headerFields = requestModel.fields.filter((field) => field.location === "header");
  const cookieFields = requestModel.fields.filter((field) => field.location === "cookie");
  const bodyFields = requestModel.fields.filter((field) => ["json_body", "form", "multipart"].includes(field.location));
  const request = (requestOverrides.request ?? {}) as Record<string, unknown>;
  const bodyMode = String(request.body_mode ?? requestModel.bodyMode);
  const bodyRaw = String(
    request.body_raw ??
      (request.json && typeof request.json === "object"
        ? JSON.stringify(request.json, null, 2)
        : (request.raw_body ?? "")),
  );

  function updateBinding(target: string, encoded: string, fallbackValue?: unknown) {
    if (encoded === "literal") {
      const current = bindings.find((binding) => binding.target === target);
      const nextOverrides =
        current?.source.type === "literal"
          ? setPointer(requestOverrides, target, current.source.value)
          : fallbackValue !== undefined
            ? setPointer(requestOverrides, target, fallbackValue)
            : requestOverrides;
      onChange({ request_overrides: nextOverrides, bindings: bindings.filter((binding) => binding.target !== target) });
      return;
    }
    const source = JSON.parse(encoded) as ApiAutomationScenarioBinding["source"];
    onChange({
      bindings: [
        ...bindings.filter((binding) => binding.target !== target),
        { target, source } as ApiAutomationScenarioBinding,
      ],
    });
  }

  function updateRequestField(key: string, value: unknown) {
    onChange({ request_overrides: setPointer(requestOverrides, `/request/${escapePointer(key)}`, value) });
  }

  function updateBody(value: string) {
    let nextOverrides = setPointer(requestOverrides, "/request/body_raw", value);
    if (bodyMode === "json") {
      try {
        nextOverrides = setPointer(nextOverrides, "/request/json", value.trim() ? JSON.parse(value) : {});
      } catch {
        // Keep the invalid editor value so draft validation can point to this field.
      }
    } else {
      nextOverrides = setPointer(nextOverrides, "/request/raw_body", value);
    }
    onChange({ request_overrides: nextOverrides });
  }

  return (
    <div className="space-y-6">
      <RequestBlock title="URL / Params">
        <div className="grid grid-cols-[90px_1fr] gap-3">
          <Input disabled value={endpoint.method} />
          <Input
            onChange={(event) => updateRequestField("path", event.target.value)}
            value={String(request.path ?? endpoint.path)}
          />
        </div>
        <RequestFieldsEditor
          bindings={bindings}
          emptyText="该接口没有声明 Path 或 Query 参数。"
          fields={parameterFields}
          requestOverrides={requestOverrides}
          variableOptions={variableOptions}
          onBindingChange={updateBinding}
        />
      </RequestBlock>

      <RequestBlock title="Headers">
        <RequestFieldsEditor
          bindings={bindings}
          emptyText="该接口没有声明 Header。"
          fields={headerFields}
          requestOverrides={requestOverrides}
          variableOptions={variableOptions}
          onBindingChange={updateBinding}
        />
      </RequestBlock>

      <RequestBlock title="Body">
        <div className="flex items-center gap-3">
          <Select onValueChange={(mode) => updateRequestField("body_mode", mode)} value={bodyMode}>
            <SelectTrigger className="w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">None</SelectItem>
              <SelectItem value="json">JSON</SelectItem>
              <SelectItem value="form">Form URL Encoded</SelectItem>
              <SelectItem value="multipart">Multipart Form</SelectItem>
              <SelectItem value="raw">Raw Text</SelectItem>
              <SelectItem value="binary">Binary</SelectItem>
            </SelectContent>
          </Select>
          {bodyFields.length > 0 ? (
            <span className="text-muted-foreground text-xs">
              Schema：{bodyFields.map((item) => item.key).join("、")}
            </span>
          ) : null}
        </div>
        {bodyFields.length > 0 ? (
          <RequestFieldsEditor
            bindings={bindings}
            className="mt-3"
            emptyText="该请求体没有声明字段。"
            fields={bodyFields}
            requestOverrides={requestOverrides}
            variableOptions={variableOptions}
            onBindingChange={updateBinding}
          />
        ) : bodyMode === "none" ? null : (
          <Textarea
            className="mt-3 min-h-52 font-mono text-xs"
            onChange={(event) => updateBody(event.target.value)}
            placeholder={bodyMode === "json" ? '{\n  "name": "{{scenario.name}}"\n}' : "输入请求体"}
            value={bodyRaw}
          />
        )}
      </RequestBlock>

      <RequestBlock title="Cookies">
        <RequestFieldsEditor
          bindings={bindings}
          emptyText="该接口没有声明 Cookie。"
          fields={cookieFields}
          requestOverrides={requestOverrides}
          variableOptions={variableOptions}
          onBindingChange={updateBinding}
        />
      </RequestBlock>
    </div>
  );
}

function defaultValueSource(type: string): Record<string, unknown> {
  if (type === "literal") return { type, value: "" };
  if (type === "environment" || type === "secret") return { type, key: "" };
  if (type === "generated") return { type, generator: "uuid4" };
  if (type === "object") return { type, properties: {} };
  if (type === "step_output") return { type, step_id: "", variable: "" };
  return { type, name: "" };
}

function RequestFieldsEditor({
  fields,
  bindings,
  requestOverrides,
  variableOptions,
  emptyText,
  className,
  onBindingChange,
}: {
  fields: ReturnType<typeof buildEndpointRequestFields>["fields"];
  bindings: ApiAutomationScenarioBinding[];
  requestOverrides: Record<string, unknown>;
  variableOptions: ReturnType<typeof buildVariableOptions>;
  emptyText: string;
  className?: string;
  onBindingChange: (target: string, value: string, fallbackValue?: unknown) => void;
}) {
  return (
    <div className={cn("mt-4 overflow-hidden rounded-xl border", className)}>
      {fields.length === 0 ? (
        <div className="p-5 text-muted-foreground text-sm">{emptyText}</div>
      ) : (
        fields.map((field) => {
          const persistedBinding = bindings.find((item) => item.target === field.target);
          const literalValue = resolveRequestFieldValue(requestOverrides, field.target, field.defaultValue);
          return (
            <div
              className="grid min-h-16 min-w-0 grid-cols-[minmax(140px,0.9fr)_minmax(0,1.1fr)] items-center gap-3 border-b px-3 py-2 last:border-b-0"
              key={`${field.location}:${field.key}`}
            >
              <div>
                <div className="font-medium text-sm">
                  {field.key} {field.required ? <span className="text-destructive">*</span> : null}
                </div>
              </div>
              <BindingSourceSelect
                binding={persistedBinding}
                literalValue={literalValue}
                variableOptions={variableOptions}
                onChange={(value) => onBindingChange(field.target, value, literalValue)}
              />
            </div>
          );
        })
      )}
    </div>
  );
}

function BindingSourceSelect({
  binding,
  literalValue,
  variableOptions,
  onChange,
}: {
  binding?: ApiAutomationScenarioBinding;
  literalValue?: unknown;
  variableOptions: ReturnType<typeof buildVariableOptions>;
  onChange: (value: string) => void;
}) {
  const currentValue = bindingValue(binding);
  const standardValues = new Set([
    "literal",
    ...variableOptions.stepOutputs.map((option) =>
      encodeBindingSource({
        type: "step_output",
        step_id: option.stepId,
        variable: option.name,
      }),
    ),
    ...variableOptions.scenarioVariables.map((name) => encodeBindingSource({ type: "scenario", name })),
    ...variableOptions.environmentVariables.map((key) => encodeBindingSource({ type: "environment", key })),
  ]);
  return (
    <Select onValueChange={onChange} value={currentValue}>
      <SelectTrigger>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="literal">
          {displayBindingValue(binding?.source.type === "literal" ? binding.source.value : literalValue)}
        </SelectItem>
        {variableOptions.stepOutputs.map((option) => (
          <SelectItem
            key={`${option.stepId}:${option.name}`}
            value={encodeBindingSource({ type: "step_output", step_id: option.stepId, variable: option.name })}
          >
            {option.stepName}.{option.name}
          </SelectItem>
        ))}
        {variableOptions.scenarioVariables.map((name: string) => (
          <SelectItem key={`scenario:${name}`} value={encodeBindingSource({ type: "scenario", name })}>
            场景变量 · {name}
          </SelectItem>
        ))}
        {variableOptions.environmentVariables.map((name: string) => (
          <SelectItem key={`environment:${name}`} value={encodeBindingSource({ type: "environment", key: name })}>
            环境变量 · {name}
          </SelectItem>
        ))}
        {binding && !standardValues.has(currentValue) ? (
          <SelectItem value={currentValue}>
            {sourceTypeLabel(binding.source.type)} · {bindingSourceName(binding.source)}
          </SelectItem>
        ) : null}
      </SelectContent>
    </Select>
  );
}

function RequestBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-3 font-semibold text-sm">{title}</h3>
      {children}
    </section>
  );
}

function LifecyclePhaseEditor({
  phase,
  step,
  title,
  variableOptions,
  onChange,
}: {
  phase: "pre_request" | "post_response";
  step: ApiAutomationScenarioStep;
  title: string;
  variableOptions: ReturnType<typeof buildVariableOptions>;
  onChange: (controlConfig: Record<string, unknown>) => void;
}) {
  const lifecycle = normalizeRequestLifecycleConfig(step);
  const phaseConfig = lifecycle[phase] as {
    actions: Array<{ id?: string; type: string; name: string; source: Record<string, unknown> }>;
    script: string;
  };
  const updatePhase = (updates: Partial<typeof phaseConfig>) =>
    onChange({ ...step.control_config, [phase]: { ...phaseConfig, ...updates } });

  return (
    <div className="space-y-6">
      <EditorSection
        title="变量动作"
        description={`${title}阶段设置当前节点可用的变量。`}
        onAdd={() =>
          updatePhase({
            actions: [
              ...phaseConfig.actions,
              { id: createId(), type: "set_variable", name: "", source: { type: "literal", value: "" } },
            ],
          })
        }
      >
        {phaseConfig.actions.map((action, index) => (
          <div className="space-y-3 border-b p-4 last:border-b-0" key={action.id ?? `${action.type}:${action.name}`}>
            <div className="grid grid-cols-[1fr_36px] gap-2">
              <Input
                onChange={(event) =>
                  updatePhase({
                    actions: replaceAt(phaseConfig.actions, index, { ...action, name: event.target.value }),
                  })
                }
                placeholder="变量名"
                value={action.name}
              />
              <Button
                onClick={() =>
                  updatePhase({ actions: phaseConfig.actions.filter((_, itemIndex) => itemIndex !== index) })
                }
                size="icon-sm"
                variant="ghost"
              >
                <Trash2 />
              </Button>
            </div>
            <SourceEditor
              source={action.source}
              variableOptions={variableOptions}
              onChange={(source) =>
                updatePhase({ actions: replaceAt(phaseConfig.actions, index, { ...action, source }) })
              }
            />
          </div>
        ))}
      </EditorSection>

      <div>
        <h3 className="font-semibold">{phase === "pre_request" ? "前置脚本" : "后置脚本"}</h3>
        <p className="mt-1 text-muted-foreground text-sm">保存受控脚本元数据；运行时不执行任意系统代码。</p>
        <Textarea
          className="mt-3 min-h-48 font-mono text-xs"
          onChange={(event) => updatePhase({ script: event.target.value })}
          placeholder={
            phase === "pre_request"
              ? 'setVariable("timestamp", Date.now());'
              : 'setVariable("result", response.json());'
          }
          value={phaseConfig.script}
        />
      </div>
    </div>
  );
}

function ExtractorEditor({
  extractors,
  onChange,
}: {
  extractors: ApiAutomationScenarioExtractor[];
  onChange: (items: ApiAutomationScenarioExtractor[]) => void;
}) {
  return (
    <EditorSection
      title="响应提取"
      description="把响应字段保存为具名输出，供后续步骤引用。"
      onAdd={() => onChange([...extractors, { name: "", source: "response.body", expression: "$.", required: true }])}
    >
      {extractors.map((extractor, index) => {
        const source = extractor.source ?? "response.body";
        const isStatusSource = source === "response.status";
        const isSseSource = source === "sse_event_json";
        const pathPlaceholder = source === "response.header" ? "Header 名称" : "$.data.id";

        return (
          <div
            className="relative space-y-3 border-b p-3 pr-12 last:border-b-0"
            key={`${extractor.name}:${extractor.source}:${extractor.expression ?? extractor.path ?? ""}`}
          >
            <div className="min-w-0 space-y-1">
              <span className="block text-muted-foreground text-xs">来源</span>
              <Select
                onValueChange={(nextSource) =>
                  onChange(
                    replaceAt(extractors, index, {
                      ...extractor,
                      source: nextSource as ApiAutomationScenarioExtractor["source"],
                      event: nextSource === "sse_event_json" ? extractor.event || "message" : undefined,
                      occurrence: nextSource === "sse_event_json" ? extractor.occurrence || "first" : undefined,
                    }),
                  )
                }
                value={source}
              >
                <SelectTrigger aria-label="来源">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="response.body">响应 Body</SelectItem>
                  <SelectItem value="response.header">响应 Header</SelectItem>
                  <SelectItem value="response.status">状态码</SelectItem>
                  <SelectItem value="sse_event_json">SSE 事件 JSON</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {isSseSource ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="min-w-0 space-y-1">
                  <span className="block text-muted-foreground text-xs">事件名称</span>
                  <Input
                    aria-label="事件名称"
                    onChange={(event) =>
                      onChange(replaceAt(extractors, index, { ...extractor, event: event.target.value }))
                    }
                    placeholder="例如 message"
                    value={extractor.event ?? ""}
                  />
                </div>
                <div className="min-w-0 space-y-1">
                  <span className="block text-muted-foreground text-xs">匹配策略</span>
                  <Select
                    onValueChange={(occurrence) =>
                      onChange(
                        replaceAt(extractors, index, {
                          ...extractor,
                          occurrence: occurrence as ApiAutomationScenarioExtractor["occurrence"],
                        }),
                      )
                    }
                    value={extractor.occurrence ?? "first"}
                  >
                    <SelectTrigger aria-label="匹配策略">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="first">首次匹配</SelectItem>
                      <SelectItem value="last">最后匹配</SelectItem>
                      <SelectItem value="all">全部匹配</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            ) : null}
            <div className="min-w-0 space-y-1">
              <span className="block text-muted-foreground text-xs">提取路径</span>
              {isStatusSource ? (
                <div className="flex h-9 items-center rounded-md border bg-muted/40 px-3 text-muted-foreground text-sm">
                  自动取 HTTP 状态码
                </div>
              ) : (
                <Input
                  aria-label="提取路径"
                  onChange={(event) =>
                    onChange(replaceAt(extractors, index, { ...extractor, expression: event.target.value }))
                  }
                  placeholder={pathPlaceholder}
                  value={extractor.expression ?? extractor.path ?? ""}
                />
              )}
            </div>
            <div className="min-w-0 space-y-1">
              <span className="block text-muted-foreground text-xs">保存为</span>
              <Input
                aria-label="保存为"
                onChange={(event) => onChange(replaceAt(extractors, index, { ...extractor, name: event.target.value }))}
                placeholder="输出变量名"
                value={extractor.name}
              />
            </div>
            <Button
              aria-label={`删除第 ${index + 1} 条响应提取`}
              className="absolute top-2 right-2 text-muted-foreground hover:text-destructive"
              onClick={() => onChange(extractors.filter((_, itemIndex) => itemIndex !== index))}
              size="icon-sm"
              variant="ghost"
            >
              <Trash2 />
            </Button>
            <div className="flex min-w-0 items-center gap-2 text-muted-foreground text-xs">
              <Checkbox
                aria-label="未提取到时终止步骤"
                checked={extractor.required ?? true}
                onCheckedChange={(value) =>
                  onChange(replaceAt(extractors, index, { ...extractor, required: value === true }))
                }
              />
              <span>未提取到时终止步骤</span>
            </div>
          </div>
        );
      })}
    </EditorSection>
  );
}

function AssertionEditor({
  assertions,
  onChange,
}: {
  assertions: ApiAutomationScenarioAssertion[];
  onChange: (items: ApiAutomationScenarioAssertion[]) => void;
}) {
  useEffect(() => {
    if (assertions.some((assertion) => !assertion.id)) {
      onChange(
        assertions.map((assertion) => (assertion.id ? assertion : { ...assertion, id: `assertion-${createId()}` })),
      );
    }
  }, [assertions, onChange]);

  return (
    <EditorSection title="断言" onAdd={() => onChange([...assertions, createAssertion("status_code")])}>
      {assertions.map((assertion, index) => (
        <div className="relative space-y-3 border-b p-4 pr-12 last:border-b-0" key={assertion.id ?? assertion.type}>
          <AssertionField label="响应来源 / 目标路径">
            <AssertionPathEditor
              assertion={assertion}
              onChange={(path) => onChange(replaceAt(assertions, index, { ...assertion, path }))}
            />
          </AssertionField>
          <AssertionField label="判断条件">
            <Select
              onValueChange={(type) => onChange(replaceAt(assertions, index, createAssertion(type)))}
              value={assertion.type}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="status_code">状态码等于</SelectItem>
                <SelectItem value="jsonpath_exists">字段存在</SelectItem>
                <SelectItem value="jsonpath_equals">字段等于</SelectItem>
                <SelectItem value="jsonpath_type">字段类型</SelectItem>
                <SelectItem value="header_exists">Header 存在</SelectItem>
                <SelectItem value="header_equals">Header 等于</SelectItem>
                <SelectItem value="content_type">Content-Type 包含</SelectItem>
                <SelectItem value="response_time_max">响应时间不超过</SelectItem>
                <SelectItem value="schema_basic">基础结构</SelectItem>
              </SelectContent>
            </Select>
          </AssertionField>
          <AssertionField label="期望值">
            <AssertionExpectedEditor
              assertion={assertion}
              onChange={(expected) => onChange(replaceAt(assertions, index, { ...assertion, expected }))}
            />
          </AssertionField>
          <Button
            aria-label={`删除第 ${index + 1} 条断言`}
            className="absolute top-3 right-3 text-muted-foreground hover:text-destructive"
            onClick={() => onChange(assertions.filter((_, itemIndex) => itemIndex !== index))}
            size="icon-sm"
            variant="ghost"
          >
            <Trash2 />
          </Button>
        </div>
      ))}
    </EditorSection>
  );
}

function AssertionField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 space-y-1.5">
      <span className="block font-medium text-muted-foreground text-xs">{label}</span>
      {children}
    </div>
  );
}

function AssertionPathEditor({
  assertion,
  onChange,
}: {
  assertion: ApiAutomationScenarioAssertion;
  onChange: (path: string) => void;
}) {
  if (["status_code", "response_time_max", "schema_basic"].includes(assertion.type)) {
    return (
      <div className="flex h-9 items-center rounded-md border border-dashed bg-muted/35 px-3 text-muted-foreground text-sm">
        {assertion.type === "status_code"
          ? "响应状态"
          : assertion.type === "response_time_max"
            ? "响应耗时"
            : "响应 Body"}
      </div>
    );
  }
  return (
    <Input
      aria-label="目标路径"
      className="font-mono text-sm"
      onChange={(event) => onChange(event.target.value)}
      placeholder={assertion.type.startsWith("header_") ? "Header 名，例如 X-Request-Id" : "JSONPath，例如 $.data.id"}
      value={assertion.path ?? ""}
    />
  );
}

function AssertionExpectedEditor({
  assertion,
  onChange,
}: {
  assertion: ApiAutomationScenarioAssertion;
  onChange: (expected: unknown) => void;
}) {
  if (["jsonpath_exists", "header_exists"].includes(assertion.type)) {
    return (
      <div className="flex h-9 items-center rounded-md border border-dashed bg-emerald-50/60 px-3 text-emerald-700 text-sm">
        无需设置期望值
      </div>
    );
  }
  if (assertion.type === "jsonpath_type") {
    return (
      <Select onValueChange={onChange} value={String(assertion.expected ?? "string")}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="string">字符串</SelectItem>
          <SelectItem value="number">数字</SelectItem>
          <SelectItem value="boolean">布尔值</SelectItem>
          <SelectItem value="object">对象</SelectItem>
          <SelectItem value="array">数组</SelectItem>
          <SelectItem value="null">空值</SelectItem>
        </SelectContent>
      </Select>
    );
  }
  if (assertion.type === "schema_basic") {
    const schema =
      assertion.expected && typeof assertion.expected === "object"
        ? (assertion.expected as { type?: string; required?: string[] })
        : { type: "object", required: [] };
    return (
      <div className="grid grid-cols-[120px_1fr] gap-2">
        <Select onValueChange={(type) => onChange({ ...schema, type })} value={schema.type ?? "object"}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="object">对象</SelectItem>
            <SelectItem value="array">数组</SelectItem>
            <SelectItem value="string">字符串</SelectItem>
            <SelectItem value="number">数字</SelectItem>
            <SelectItem value="boolean">布尔值</SelectItem>
          </SelectContent>
        </Select>
        <Input
          disabled={schema.type !== "object"}
          onChange={(event) =>
            onChange({
              ...schema,
              required: event.target.value
                .split(",")
                .map((item) => item.trim())
                .filter(Boolean),
            })
          }
          placeholder="必填字段，逗号分隔"
          value={(schema.required ?? []).join(", ")}
        />
      </div>
    );
  }
  return (
    <Input
      onChange={(event) => onChange(parseInput(event.target.value))}
      placeholder={assertion.type === "response_time_max" ? "最大毫秒数" : "期望值"}
      type={assertion.type === "response_time_max" || assertion.type === "status_code" ? "number" : "text"}
      value={assertion.expected == null ? "" : String(assertion.expected)}
    />
  );
}

function createAssertion(type: string): ApiAutomationScenarioAssertion {
  const id = `assertion-${createId()}`;
  if (type === "status_code") return { id, type, expected: 200 };
  if (type === "response_time_max") return { id, type, expected: 1000 };
  if (type === "jsonpath_type") return { id, type, path: "$.data", expected: "string" };
  if (type === "schema_basic") return { id, type, expected: { type: "object", required: [] } };
  return { id, type, expected: "" };
}

function ControlEditor({
  step,
  onChange,
}: {
  step: ApiAutomationScenarioStep;
  onChange: (updates: Partial<ApiAutomationScenarioStep>) => void;
}) {
  return (
    <div className="max-w-xl space-y-5">
      <div className="flex items-center justify-between rounded-xl border p-4">
        <div>
          <div className="font-medium">启用步骤</div>
          <div className="mt-1 text-muted-foreground text-xs">禁用后保存配置，但运行时跳过。</div>
        </div>
        <Checkbox checked={step.enabled} onCheckedChange={(value) => onChange({ enabled: value === true })} />
      </div>
      <div>
        <div className="mb-2 font-medium text-sm">失败策略</div>
        <Select
          onValueChange={(onFailure: ApiAutomationScenarioStep["on_failure"]) => onChange({ on_failure: onFailure })}
          value={step.on_failure}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="stop">停止后续步骤</SelectItem>
            <SelectItem value="continue">记录失败并继续</SelectItem>
            <SelectItem value="always_run">始终执行（清理步骤）</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <span className="mb-2 block font-medium text-sm">超时（毫秒）</span>
          <Input
            onChange={(event) =>
              onChange({ control_config: { ...step.control_config, timeout_ms: Number(event.target.value) || 0 } })
            }
            type="number"
            value={Number(step.control_config.timeout_ms ?? 30000)}
          />
        </div>
        <div>
          <span className="mb-2 block font-medium text-sm">重试次数</span>
          <Input
            onChange={(event) =>
              onChange({
                control_config: {
                  ...step.control_config,
                  retries: Number(event.target.value) || 0,
                },
              })
            }
            type="number"
            value={Number(step.control_config.retries ?? 0)}
          />
        </div>
      </div>
    </div>
  );
}

function EditorSection({
  title,
  description,
  onAdd,
  children,
}: {
  title: string;
  description?: string;
  onAdd: () => void;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold">{title}</h3>
          {description ? <p className="mt-1 text-muted-foreground text-sm">{description}</p> : null}
        </div>
        <Button onClick={onAdd} size="sm" variant="outline">
          <Plus />
          添加
        </Button>
      </div>
      <div className="mt-4 overflow-hidden rounded-xl border">
        {children || <div className="p-6 text-center text-muted-foreground text-sm">暂无配置</div>}
      </div>
    </div>
  );
}

function setPointer(document: Record<string, unknown>, pointer: string, value: unknown) {
  const next = structuredClone(document);
  const parts = pointer.split("/").filter(Boolean).map(unescapePointer);
  let current: Record<string, unknown> = next;
  for (const part of parts.slice(0, -1)) {
    if (!current[part] || typeof current[part] !== "object") current[part] = {};
    current = current[part] as Record<string, unknown>;
  }
  current[parts.at(-1) ?? ""] = value;
  return next;
}

function bindingValue(binding?: ApiAutomationScenarioBinding) {
  if (!binding) return "literal";
  if (binding.source.type === "literal") return "literal";
  return encodeBindingSource(binding.source);
}

function encodeBindingSource(source: ApiAutomationScenarioBinding["source"]) {
  return JSON.stringify(source);
}

function displayBindingValue(value: unknown) {
  if (typeof value === "string") return value;
  if (value === undefined) return "未配置";
  return JSON.stringify(value);
}

function bindingSourceName(source: ApiAutomationScenarioBinding["source"]) {
  if (source.type === "step_output") return source.variable;
  if (source.type === "environment" || source.type === "secret") return source.key;
  if (source.type === "scenario" || source.type === "user_input") return source.name;
  if (source.type === "generated") return source.generator;
  return "当前引用";
}

function sourceTypeLabel(sourceType: ApiAutomationScenarioBinding["source"]["type"]) {
  const labels: Record<ApiAutomationScenarioBinding["source"]["type"], string> = {
    literal: "固定值",
    user_input: "运行时输入",
    environment: "环境变量",
    secret: "密钥",
    scenario: "场景变量",
    step_output: "前序步骤输出",
    generated: "动态生成",
    object: "对象",
  };
  return labels[sourceType];
}

function replaceAt<T>(items: T[], index: number, value: T) {
  return items.map((item, itemIndex) => (itemIndex === index ? value : item));
}
function parseInput(value: string) {
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  if (value === "true") return true;
  if (value === "false") return false;
  return value;
}
function escapePointer(value: string) {
  return value.replaceAll("~", "~0").replaceAll("/", "~1");
}
function unescapePointer(value: string) {
  return value.replaceAll("~1", "/").replaceAll("~0", "~");
}
