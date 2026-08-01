"use client";

import { Check, CircleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./api-orchestration-select";
import type { ApiScenarioAiPlanValueSource, ApiScenarioAiReviewField } from "@/lib/api-client";

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

function sourceValue(source: ApiScenarioAiPlanValueSource) {
  switch (source.type) {
    case "literal":
      return typeof source.value === "string" ? source.value : JSON.stringify(source.value ?? "");
    case "environment":
    case "secret":
      return source.key ?? "";
    case "scenario":
    case "user_input":
      return source.name ?? "";
    case "step_output":
      return [source.step_id, source.variable].filter(Boolean).join(".");
    case "generated":
      return source.generator === "random_string"
        ? `${source.generator}:${source.length ?? 12}`
        : (source.generator ?? "");
    case "object":
      return JSON.stringify(source.properties ?? {});
  }
}

function parseJsonValue(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function sourceDisplayValue(source: ApiScenarioAiPlanValueSource) {
  switch (source.type) {
    case "environment":
      return `\${env.${source.key ?? ""}}`;
    case "secret":
      return `\${secret.${source.key ?? ""}}`;
    case "scenario":
      return `\${scenario.${source.name ?? ""}}`;
    case "user_input":
      return `\${input.${source.name ?? ""}}`;
    case "step_output":
      return `\${steps.${source.step_id ?? ""}.${source.variable ?? ""}}`;
    default:
      return sourceValue(source);
  }
}

function changeSourceType(
  source: ApiScenarioAiPlanValueSource,
  type: ApiScenarioAiPlanValueSource["type"],
): ApiScenarioAiPlanValueSource {
  const value = sourceValue(source);
  switch (type) {
    case "literal":
      return { type, value: parseJsonValue(value) };
    case "environment":
    case "secret":
      return { type, key: value };
    case "scenario":
    case "user_input":
      return { type, name: value };
    case "step_output": {
      const [stepId = "", ...variableParts] = value.split(".");
      return { type, step_id: stepId, variable: variableParts.join(".") };
    }
    case "generated":
      return { type, generator: "uuid4" };
    case "object":
      return { type, properties: {} };
  }
}

function changeSourceValue(source: ApiScenarioAiPlanValueSource, value: string): ApiScenarioAiPlanValueSource {
  switch (source.type) {
    case "literal":
      return { type: "literal", value: parseJsonValue(value) };
    case "environment":
    case "secret":
      return { type: source.type, key: value };
    case "scenario":
    case "user_input":
      return { type: source.type, name: value };
    case "step_output": {
      const [stepId = "", ...variableParts] = value.split(".");
      return { type: "step_output", step_id: stepId, variable: variableParts.join(".") };
    }
    case "generated": {
      const [generator = "uuid4", length] = value.split(":");
      return {
        type: "generated",
        generator,
        ...(generator === "random_string" ? { length: Number(length) || 12 } : {}),
      };
    }
    case "object": {
      const parsed = parseJsonValue(value);
      return {
        type: "object",
        properties: typeof parsed === "object" && parsed ? (parsed as Record<string, never>) : {},
      };
    }
  }
}

function SourcePreview({ source }: { source: ApiScenarioAiPlanValueSource }) {
  const value = sourceDisplayValue(source);
  return (
    <div className="min-w-0 space-y-1">
      <Badge className="h-5 px-1.5 text-[10px]" variant="secondary">
        {sourceLabels[source.type]}
      </Badge>
      <div className="break-all font-mono text-[11px] text-muted-foreground">{value === "" ? "-" : value}</div>
    </div>
  );
}

export function ApiScenarioAiReviewFieldRow({
  field,
  onChange,
  onConfirm,
}: {
  field: ApiScenarioAiReviewField;
  onChange: (source: ApiScenarioAiPlanValueSource) => void;
  onConfirm: () => void;
}) {
  const resolved = field.resolved ?? field.proposal;
  return (
    <div className="grid gap-3 border-t px-3 py-3 first:border-t-0 md:grid-cols-[minmax(130px,1fr)_minmax(150px,1fr)_minmax(260px,1.6fr)_110px] md:items-center">
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 font-medium text-xs">
          <span className="truncate">{field.display_name}</span>
          {field.required ? <span className="text-destructive">*</span> : null}
        </div>
        <div className="mt-1 truncate font-mono text-[10px] text-muted-foreground">{field.path}</div>
      </div>
      <div>
        <div className="mb-1 text-[10px] text-muted-foreground md:hidden">AI 建议</div>
        <SourcePreview source={field.proposal} />
      </div>
      <div className="space-y-2">
        <div className="text-[10px] text-muted-foreground md:hidden">最终值</div>
        <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2">
          <Select
            onValueChange={(type) => onChange(changeSourceType(resolved, type as ApiScenarioAiPlanValueSource["type"]))}
            value={resolved.type}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(sourceLabels).map(([type, label]) => (
                <SelectItem key={type} value={type}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            className="h-8 font-mono text-xs"
            onChange={(event) => onChange(changeSourceValue(resolved, event.target.value))}
            value={sourceValue(resolved)}
          />
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
