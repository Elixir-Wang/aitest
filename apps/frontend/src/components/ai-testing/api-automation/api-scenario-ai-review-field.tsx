"use client";

import { Check, CircleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { ApiScenarioAiPlanValueSource, ApiScenarioAiReviewField } from "@/lib/api-client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./api-orchestration-select";

const sourceLabels: Record<ApiScenarioAiPlanValueSource["type"], string> = {
  literal: "固定值",
  user_input: "运行时输入",
  environment: "环境变量",
  secret: "密钥引用",
  scenario: "场景变量",
  step_output: "上游输出",
  generated: "动态生成",
  object: "对象",
};

export type ApiScenarioAiReviewSourceOptions = {
  environmentVariables: string[];
  scenarioVariables: string[];
  secretKeys: string[];
  userInputs: string[];
  stepOutputs: Array<{ stepId: string; stepName: string; variable: string }>;
};

function parseJsonValue(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function changeSourceType(
  type: ApiScenarioAiPlanValueSource["type"],
  options: ApiScenarioAiReviewSourceOptions,
): ApiScenarioAiPlanValueSource {
  switch (type) {
    case "literal":
      return { type, value: "" };
    case "environment":
      return { type, key: options.environmentVariables[0] ?? "" };
    case "secret":
      return { type, key: options.secretKeys[0] ?? "" };
    case "scenario":
      return { type, name: options.scenarioVariables[0] ?? "" };
    case "user_input":
      return { type, name: options.userInputs[0] ?? "" };
    case "step_output":
      return options.stepOutputs[0]
        ? { type, step_id: options.stepOutputs[0].stepId, variable: options.stepOutputs[0].variable }
        : { type, step_id: "", variable: "" };
    case "generated":
      return { type, generator: "uuid4" };
    case "object":
      return { type, properties: {} };
  }
}

function changeLiteralValue(source: ApiScenarioAiPlanValueSource, value: string): ApiScenarioAiPlanValueSource {
  return { ...source, type: "literal", value: parseJsonValue(value) };
}

function sourceOptionsWithCurrent(options: string[], current?: string) {
  return Array.from(new Set([...(current ? [current] : []), ...options]));
}

function sourceHasOptions(type: ApiScenarioAiPlanValueSource["type"], options: ApiScenarioAiReviewSourceOptions) {
  switch (type) {
    case "environment":
      return options.environmentVariables.length > 0;
    case "secret":
      return options.secretKeys.length > 0;
    case "scenario":
      return options.scenarioVariables.length > 0;
    case "user_input":
      return options.userInputs.length > 0;
    case "step_output":
      return options.stepOutputs.length > 0;
    default:
      return true;
  }
}

function SourceValueEditor({
  field,
  source,
  options,
  onChange,
}: {
  field: ApiScenarioAiReviewField;
  source: ApiScenarioAiPlanValueSource;
  options: ApiScenarioAiReviewSourceOptions;
  onChange: (source: ApiScenarioAiPlanValueSource) => void;
}) {
  switch (source.type) {
    case "literal":
      if (field.value_type === "boolean") {
        return (
          <Select
            onValueChange={(value) => onChange({ type: "literal", value: value === "true" })}
            value={String(source.value)}
          >
            <SelectTrigger className="h-8 min-w-0 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="true">true</SelectItem>
              <SelectItem value="false">false</SelectItem>
            </SelectContent>
          </Select>
        );
      }
      return (
        <Input
          className="h-8 min-w-0 font-mono text-xs"
          onChange={(event) => onChange(changeLiteralValue(source, event.target.value))}
          type={field.value_type === "integer" || field.value_type === "number" ? "number" : "text"}
          value={source.value == null ? "" : String(source.value)}
        />
      );
    case "environment":
      return (
        <ReferenceSelect
          onChange={(key) => onChange({ type: "environment", key })}
          options={sourceOptionsWithCurrent(options.environmentVariables, source.key)}
          placeholder="选择环境变量"
          value={source.key ?? ""}
        />
      );
    case "secret":
      return (
        <ReferenceSelect
          onChange={(key) => onChange({ type: "secret", key })}
          options={sourceOptionsWithCurrent(options.secretKeys, source.key)}
          placeholder="选择密钥"
          value={source.key ?? ""}
        />
      );
    case "user_input":
      return (
        <ReferenceSelect
          onChange={(name) => onChange({ type: "user_input", name })}
          options={sourceOptionsWithCurrent(options.userInputs, source.name)}
          placeholder="选择运行时输入"
          value={source.name ?? ""}
        />
      );
    case "scenario":
      return (
        <ReferenceSelect
          onChange={(name) => onChange({ type: "scenario", name })}
          options={sourceOptionsWithCurrent(options.scenarioVariables, source.name)}
          placeholder="选择场景变量"
          value={source.name ?? ""}
        />
      );
    case "step_output":
      return (
        <Select
          onValueChange={(value) => {
            const candidate = options.stepOutputs.find((item) => `${item.stepId}:${item.variable}` === value);
            if (candidate) onChange({ type: "step_output", step_id: candidate.stepId, variable: candidate.variable });
          }}
          value={`${source.step_id ?? ""}:${source.variable ?? ""}`}
        >
          <SelectTrigger className="h-8 min-w-0 text-xs">
            <SelectValue placeholder="选择上游输出" />
          </SelectTrigger>
          <SelectContent>
            {options.stepOutputs.map((item) => (
              <SelectItem key={`${item.stepId}:${item.variable}`} value={`${item.stepId}:${item.variable}`}>
                {item.stepName}.{item.variable}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    case "generated":
      return (
        <Select
          onValueChange={(generator) =>
            onChange({ type: "generated", generator, ...(generator === "random_string" ? { length: 12 } : {}) })
          }
          value={source.generator ?? "uuid4"}
        >
          <SelectTrigger className="h-8 min-w-0 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="uuid4">UUID</SelectItem>
            <SelectItem value="timestamp_ms">毫秒时间戳</SelectItem>
            <SelectItem value="timestamp_iso">ISO 时间</SelectItem>
            <SelectItem value="random_string">随机字符串</SelectItem>
          </SelectContent>
        </Select>
      );
    case "object":
      return (
        <Textarea
          className="min-h-20 min-w-0 font-mono text-xs"
          onChange={(event) => {
            const parsed = parseJsonValue(event.target.value);
            if (parsed && typeof parsed === "object" && !Array.isArray(parsed))
              onChange({ type: "object", properties: parsed as Record<string, ApiScenarioAiPlanValueSource> });
          }}
          value={JSON.stringify(source.properties ?? {}, null, 2)}
        />
      );
  }
}

function ReferenceSelect({
  onChange,
  options,
  placeholder,
  value,
}: {
  onChange: (value: string) => void;
  options: string[];
  placeholder: string;
  value: string;
}) {
  return (
    <Select onValueChange={onChange} value={value}>
      <SelectTrigger className="h-8 min-w-0 text-xs">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option} value={option}>
            {option}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function ApiScenarioAiReviewFieldRow({
  field,
  sourceOptions,
  onChange,
  onConfirm,
}: {
  field: ApiScenarioAiReviewField;
  sourceOptions: ApiScenarioAiReviewSourceOptions;
  onChange: (source: ApiScenarioAiPlanValueSource) => void;
  onConfirm: () => void;
}) {
  const resolved = field.resolved ?? field.proposal;
  return (
    <div className="grid gap-3 border-t px-3 py-3 first:border-t-0 md:grid-cols-[minmax(160px,1fr)_minmax(340px,1.8fr)_110px] md:items-center">
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 font-medium text-xs">
          <span className="truncate">{field.display_name}</span>
          {field.required ? <span className="text-destructive">*</span> : null}
        </div>
        <div className="mt-1 truncate font-mono text-[10px] text-muted-foreground">{field.path}</div>
      </div>
      <div className="space-y-2">
        <div className="text-[10px] text-muted-foreground md:hidden">最终值</div>
        <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2">
          <Select
            onValueChange={(type) =>
              onChange(changeSourceType(type as ApiScenarioAiPlanValueSource["type"], sourceOptions))
            }
            value={resolved.type}
          >
            <SelectTrigger className="h-8 min-w-0 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(sourceLabels).map(([type, label]) => (
                <SelectItem
                  disabled={!sourceHasOptions(type as ApiScenarioAiPlanValueSource["type"], sourceOptions)}
                  key={type}
                  value={type}
                >
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <SourceValueEditor field={field} onChange={onChange} options={sourceOptions} source={resolved} />
        </div>
      </div>
      <div className="flex items-center justify-between gap-2 md:justify-end">
        <Badge variant={field.status === "pending" ? "outline" : "secondary"}>
          {field.status === "pending" ? <CircleAlert className="size-3" /> : <Check className="size-3" />}
          {field.status === "pending" ? "待确认" : field.status === "resolved" ? "自动确定" : "已确认"}
        </Badge>
        {field.status === "pending" ? (
          <Button className="h-7 px-2 text-xs" onClick={onConfirm} size="sm" variant="outline">
            确认
          </Button>
        ) : null}
      </div>
    </div>
  );
}
