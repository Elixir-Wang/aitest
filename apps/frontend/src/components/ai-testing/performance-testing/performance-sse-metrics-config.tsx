"use client";

import { useMemo, useState } from "react";

import { CheckCircle2, LoaderCircle, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  generatePerformanceSseMetrics,
  type PerformanceSseConfig,
  type PerformanceSseMetricGenerationPayload,
  type PerformanceSseMetricGenerationResult,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

type RequestValues = Pick<
  PerformanceSseMetricGenerationPayload,
  "path_parameters" | "query_parameters" | "headers" | "body"
>;

type PerformanceSseMetricsConfigProps = {
  projectId: string;
  targetType: "endpoint" | "scenario";
  endpointId?: string;
  scenarioId?: string;
  scenarioStepId?: string;
  environmentId: string;
  maxStreamSeconds: number;
  value: PerformanceSseConfig | null;
  getRequestValues: () => RequestValues;
  onChange: (value: PerformanceSseConfig) => void;
};

export function PerformanceSseMetricsConfig({
  projectId,
  targetType,
  endpointId,
  scenarioId,
  scenarioStepId,
  environmentId,
  maxStreamSeconds,
  value,
  getRequestValues,
  onChange,
}: PerformanceSseMetricsConfigProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState<PerformanceSseConfig | null>(value);
  const [result, setResult] = useState<PerformanceSseMetricGenerationResult | null>(null);
  const [verified, setVerified] = useState(Boolean(value));
  const evidence = useMemo(
    () => new Map(result?.validation.metrics.map((item) => [item.metric_id, item]) ?? []),
    [result],
  );

  async function run(candidate?: PerformanceSseConfig) {
    const hasTarget = targetType === "endpoint" ? Boolean(endpointId) : Boolean(scenarioId && scenarioStepId);
    if (!projectId || !hasTarget || !environmentId) {
      toast.error(targetType === "endpoint" ? "请先选择项目、接口和环境" : "请先选择项目、场景、SSE 步骤和环境");
      return;
    }
    setLoading(true);
    try {
      const generated = await generatePerformanceSseMetrics(projectId, {
        ...(targetType === "endpoint"
          ? { endpoint_id: endpointId }
          : { scenario_id: scenarioId, scenario_step_id: scenarioStepId }),
        api_environment_id: environmentId,
        ...getRequestValues(),
        max_stream_seconds: maxStreamSeconds,
        ...(candidate ? { candidate_sse: { ...candidate, max_stream_seconds: maxStreamSeconds } } : {}),
      });
      setResult(generated);
      setDraft(generated.candidate_sse);
      setVerified(generated.validation.valid);
      setOpen(true);
      generated.warnings.forEach((warning) => {
        toast.warning(warning);
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "SSE 指标生成失败");
    } finally {
      setLoading(false);
    }
  }

  function generate() {
    if (value && !window.confirm("重新运行将生成新的指标建议，当前配置不会立即被覆盖。是否继续？")) return;
    void run();
  }

  function updateMetric(index: number, field: "name" | "path" | "expected" | "event_name", next: string) {
    if (!draft) return;
    const metrics = draft.metrics.map((metric, metricIndex) => {
      if (metricIndex !== index) return metric;
      if (field === "name") return { ...metric, name: next };
      return { ...metric, match: { ...metric.match, [field]: next } };
    });
    setDraft({ ...draft, metrics });
    if (field !== "name") setVerified(false);
  }

  function updateMissingPolicy(index: number, missingPolicy: "record_null" | "fail_request" | "ignore") {
    if (!draft) return;
    setDraft({
      ...draft,
      metrics: draft.metrics.map((metric, metricIndex) =>
        metricIndex === index ? { ...metric, missing_policy: missingPolicy } : metric,
      ),
    });
  }

  function apply() {
    if (!draft || !verified) return;
    onChange({ ...draft, max_stream_seconds: maxStreamSeconds });
    setOpen(false);
  }

  return (
    <div className="rounded-lg border bg-muted/20 p-4 md:col-span-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 font-medium">
            <Sparkles className="size-4 text-primary" />
            业务响应指标
          </div>
          {!value ? (
            <p className="mt-1 text-muted-foreground text-sm">
              运行真实接口编排，识别 LLM 调用开始、首次回答和流结束事件。
            </p>
          ) : (
            <div className="mt-2 space-y-1 text-sm">
              {value.metrics.map((metric) => {
                const item = evidence.get(metric.id);
                return (
                  <div className="flex flex-wrap items-center gap-2" key={metric.id}>
                    <CheckCircle2 className="size-4 text-emerald-600" />
                    <span>{metric.name}</span>
                    <code className="text-muted-foreground text-xs">
                      {String(metric.match.expected ?? metric.match.operator)}
                    </code>
                    {item ? (
                      <span className="text-muted-foreground text-xs">
                        样本 {item.sample_elapsed_ms ?? "-"} ms · 命中 {item.matched_count} 次
                        {item.matched_count > 1 ? "，仅取首次" : ""}
                      </span>
                    ) : null}
                  </div>
                );
              })}
              {value.end_rule ? (
                <div className="text-muted-foreground text-xs">
                  流结束：{String(value.end_rule.expected ?? value.end_rule.operator)} · 已验证
                </div>
              ) : null}
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <Button disabled={loading} onClick={generate} type="button" variant={value ? "outline" : "default"}>
            {loading ? <LoaderCircle className="animate-spin" /> : <Sparkles />}
            {value ? "重新生成" : "运行接口编排并生成指标"}
          </Button>
          {value ? (
            <Button
              onClick={() => {
                setDraft(value);
                setVerified(true);
                setOpen(true);
              }}
              type="button"
              variant="outline"
            >
              配置指标
            </Button>
          ) : null}
        </div>
      </div>

      <Dialog onOpenChange={setOpen} open={open}>
        <DialogContent className="max-h-[min(760px,calc(100vh-2rem))] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>SSE 指标配置</DialogTitle>
            <DialogDescription>
              {verified ? "规则已通过真实样本验证。" : "待验证：修改匹配规则后必须重新验证。"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            {draft?.metrics.map((metric, index) => {
              const item = evidence.get(metric.id);
              return (
                <div className="rounded-lg border p-4" key={metric.id}>
                  <div className="flex items-center justify-between gap-3">
                    <strong>{metric.name}</strong>
                    <span className={verified ? "text-emerald-600 text-xs" : "text-amber-600 text-xs"}>
                      {verified ? "已验证" : "待验证"}
                    </span>
                  </div>
                  <code className="mt-2 block break-all text-muted-foreground text-xs">
                    {metric.match.path || "事件名"} = {String(metric.match.expected ?? metric.match.operator)}
                  </code>
                  {item ? (
                    <p className="mt-2 text-muted-foreground text-xs">
                      样本事件 #{item.first_event_sequence ?? "-"} · {item.sample_elapsed_ms ?? "-"} ms · 命中{" "}
                      {item.matched_count} 次{item.matched_count > 1 ? "，仅取首次" : ""}
                    </p>
                  ) : null}
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm">展开配置</summary>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <Input
                        onChange={(event) => updateMetric(index, "name", event.target.value)}
                        value={metric.name}
                      />
                      <Input
                        onChange={(event) => updateMetric(index, "event_name", event.target.value)}
                        value={metric.match.event_name}
                      />
                      <Input
                        onChange={(event) => updateMetric(index, "path", event.target.value)}
                        value={metric.match.path}
                      />
                      <Input
                        onChange={(event) => updateMetric(index, "expected", event.target.value)}
                        value={String(metric.match.expected ?? "")}
                      />
                      <select
                        className="h-9 rounded-md border bg-background px-3 text-sm"
                        onChange={(event) =>
                          updateMissingPolicy(index, event.target.value as "record_null" | "fail_request" | "ignore")
                        }
                        value={metric.missing_policy}
                      >
                        <option value="record_null">记录为空</option>
                        <option value="fail_request">请求失败</option>
                        <option value="ignore">忽略指标</option>
                      </select>
                    </div>
                    {item?.sample_event ? (
                      <pre className="mt-3 overflow-x-auto rounded bg-muted p-3 text-xs">
                        样本事件：{JSON.stringify(item.sample_event, null, 2)}
                      </pre>
                    ) : null}
                  </details>
                </div>
              );
            })}
            {draft?.end_rule ? (
              <div className="rounded-lg border p-4 text-sm">
                流结束：
                <code>
                  {draft.end_rule.path} = {String(draft.end_rule.expected)}
                </code>
                {result ? ` · 命中 ${result.validation.end_rule.matched_count} 次` : ""}
              </div>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              disabled={loading || !draft}
              onClick={() => draft && void run(draft)}
              type="button"
              variant="outline"
            >
              {loading ? <LoaderCircle className="animate-spin" /> : null}
              重新验证
            </Button>
            <Button onClick={() => setOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={!draft || !verified || loading} onClick={apply} type="button">
              应用
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
