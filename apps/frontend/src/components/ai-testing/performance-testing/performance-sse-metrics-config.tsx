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
  type PerformanceSseEventFact,
  type PerformanceSseMetric,
  type PerformanceSseMetricCandidate,
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

function candidateMetric(candidate: PerformanceSseMetricCandidate): PerformanceSseMetric {
  return {
    id: candidate.metric_id,
    name: candidate.name,
    category: candidate.category,
    timing: candidate.timing,
    match: candidate.match,
    occurrence: "first",
    missing_policy: candidate.recommended_missing_policy,
  };
}

function metricMatchSummary(metric: PerformanceSseMetric) {
  const scope = metric.match.event_name ? `SSE 事件 ${metric.match.event_name} 的` : "SSE 事件的";
  const target = metric.match.source === "event_name" ? "事件类型" : metric.match.path || "事件内容";
  const expected = String(metric.match.expected ?? "");

  if (metric.match.operator === "exists") return `当 ${scope}${target} 存在`;
  if (metric.match.operator === "non_empty") return `当 ${scope}${target} 非空`;
  if (metric.match.operator === "contains") return `当 ${scope}${target} 包含 ${expected}`;
  if (metric.match.operator === "matches") return `当 ${scope}${target} 匹配 ${expected}`;
  return `当 ${scope}${target} 等于 ${expected}`;
}

function metricTimingFormula(metric: PerformanceSseMetric) {
  return `${metric.name}命中时间 - 所属接口请求发起时间`;
}

function customCandidate(fact: PerformanceSseEventFact): PerformanceSseMetricCandidate {
  return {
    suggestion_key: `custom_${fact.fact_id}`,
    metric_id: fact.metric_id,
    name: `事件 ${fact.normalized_value} 首次到达时间`,
    category: "custom_event",
    timing: {
      scope: "request",
      start: "request_started",
      source_request_id: null,
      source_request_name: null,
    },
    match: {
      event_name: fact.event_name,
      source: "data_json",
      path: fact.path,
      operator: "equals",
      expected: fact.normalized_value,
    },
    occurrence: "first",
    recommended_missing_policy: "record_null",
    source: "structural",
    recommendation_level: "optional",
    recommendation_score: 0.5,
    semantic_confidence: 0.4,
    reason: "用户从真实事件目录中手动添加。",
    uncertainty: "事件的准确业务含义需要人工确认。",
    evidence_fact_ids: [fact.fact_id],
    validation: {
      valid: fact.matched_count > 0,
      matched_count: fact.matched_count,
      first_event_sequence: fact.first_sequence,
      sample_elapsed_ms: fact.first_offset_ms,
      sample_event: null,
    },
  };
}

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
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [verified, setVerified] = useState(Boolean(value));
  const [validation, setValidation] = useState<PerformanceSseMetricGenerationResult["validation"]>(undefined);
  const [draftFingerprint, setDraftFingerprint] = useState("");

  const evidence = useMemo(() => {
    const items = new Map(result?.candidates.map((candidate) => [candidate.metric_id, candidate.validation]) ?? []);
    validation?.metrics.forEach((item) => {
      items.set(item.metric_id, { ...item, valid: item.matched_count > 0 });
    });
    return items;
  }, [result, validation]);

  function buildDraft(
    generated: PerformanceSseMetricGenerationResult,
    keys: string[],
    current?: PerformanceSseConfig | null,
  ): PerformanceSseConfig {
    const currentMetrics = new Map(current?.metrics.map((metric) => [metric.id, metric]) ?? []);
    return {
      max_stream_seconds: maxStreamSeconds,
      metrics: generated.candidates
        .filter((candidate) => keys.includes(candidate.suggestion_key))
        .map((candidate) => currentMetrics.get(candidate.metric_id) ?? candidateMetric(candidate)),
      end_rule: current?.end_rule ?? null,
    };
  }

  function requestFingerprint() {
    return JSON.stringify({
      projectId,
      targetType,
      endpointId,
      scenarioId,
      scenarioStepId,
      environmentId,
      maxStreamSeconds,
      request: getRequestValues(),
    });
  }

  function openPendingDraft() {
    if (draftFingerprint && draftFingerprint !== requestFingerprint()) {
      setVerified(false);
      setValidation(undefined);
      toast.info("请求配置已变化，请使用新请求重新验证");
    }
    setOpen(true);
  }

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
      if (candidate) {
        setDraft(generated.candidate_sse ?? candidate);
        setValidation(generated.validation);
        setVerified(Boolean(generated.validation?.valid));
        setDraftFingerprint(requestFingerprint());
        if (generated.validation?.valid) toast.success("当前指标配置已通过样本验证");
      } else {
        const currentConfig = value ?? draft;
        const currentMetricIds = new Set(currentConfig?.metrics.map((metric) => metric.id) ?? []);
        const selectedKeys = generated.candidates
          .filter((candidate) =>
            currentMetricIds.size > 0
              ? currentMetricIds.has(candidate.metric_id)
              : candidate.recommendation_level === "recommended",
          )
          .map((item) => item.suggestion_key);
        const nextDraft = buildDraft(generated, selectedKeys, currentConfig);
        const generatedMetricIds = new Set(generated.candidates.map((candidate) => candidate.metric_id));
        const unmatchedCurrentMetrics =
          currentConfig?.metrics.filter((metric) => !generatedMetricIds.has(metric.id)) ?? [];
        nextDraft.metrics.push(...unmatchedCurrentMetrics);
        setResult(generated);
        setSelectedKeys(selectedKeys);
        setDraft(nextDraft);
        setValidation(undefined);
        setDraftFingerprint(requestFingerprint());
        setVerified(
          nextDraft.metrics.length > 0 &&
            unmatchedCurrentMetrics.length === 0 &&
            generated.candidates
              .filter((item) => selectedKeys.includes(item.suggestion_key))
              .every((item) => item.validation.valid),
        );
        if (generated.candidates.length > 0) {
          toast.success(`已发现并验证 ${generated.candidates.length} 个候选指标`);
        } else {
          toast.info(generated.messages[0] ?? "本次样本未发现高可信度性能指标");
        }
      }
      setOpen(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "SSE 指标发现失败");
    } finally {
      setLoading(false);
    }
  }

  function generate() {
    if (value && !window.confirm("重新运行将生成新的指标建议，当前配置不会立即被覆盖。是否继续？")) return;
    void run();
  }

  function toggleCandidate(candidate: PerformanceSseMetricCandidate) {
    if (!result) return;
    const nextKeys = selectedKeys.includes(candidate.suggestion_key)
      ? selectedKeys.filter((key) => key !== candidate.suggestion_key)
      : [...selectedKeys, candidate.suggestion_key];
    setSelectedKeys(nextKeys);
    setDraft(buildDraft(result, nextKeys, draft));
    setValidation(undefined);
    setVerified(
      nextKeys.length > 0 &&
        result.candidates
          .filter((item) => nextKeys.includes(item.suggestion_key))
          .every((item) => item.validation.valid),
    );
  }

  function addFact(fact: PerformanceSseEventFact) {
    if (!result) return;
    const candidate = customCandidate(fact);
    const nextResult = { ...result, candidates: [...result.candidates, candidate] };
    const nextKeys = [...selectedKeys, candidate.suggestion_key];
    setResult(nextResult);
    setSelectedKeys(nextKeys);
    setDraft(buildDraft(nextResult, nextKeys, draft));
    setVerified(true);
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

  function toggleRecommendedEndRule() {
    if (!draft || !result?.end_rule_candidate) return;
    const recommended = result.end_rule_candidate.match;
    const enabled = JSON.stringify(draft.end_rule) === JSON.stringify(recommended);
    setDraft({ ...draft, end_rule: enabled ? null : recommended });
    if (!enabled) setVerified(false);
    setValidation(undefined);
  }

  function removeEndRule() {
    if (!draft) return;
    setDraft({ ...draft, end_rule: null });
    setValidation(undefined);
  }

  function apply() {
    if (!draft || !verified || draft.metrics.length === 0) return;
    if (draftFingerprint && draftFingerprint !== requestFingerprint()) {
      setVerified(false);
      setValidation(undefined);
      toast.info("请求配置已变化，请使用新请求重新验证");
      return;
    }
    onChange({ ...draft, max_stream_seconds: maxStreamSeconds });
    setValidation(undefined);
    setOpen(false);
  }

  const hasPendingDraft = Boolean(result && JSON.stringify(draft) !== JSON.stringify(value));

  return (
    <div className="rounded-lg border bg-muted/20 p-4 md:col-span-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 font-medium">
            <Sparkles className="size-4 text-primary" />
            业务响应指标
          </div>
          {hasPendingDraft ? (
            <div className="mt-2 space-y-1 text-sm">
              <p>已发现 {result?.candidates.length ?? 0} 个候选指标，等待确认应用。</p>
              <p className="text-muted-foreground text-xs">关闭弹窗不会丢失结果，可随时查看生成结果。</p>
            </div>
          ) : !value ? (
            <p className="mt-1 text-muted-foreground text-sm">运行真实接口，分析 SSE 流中值得观测的业务事件。</p>
          ) : (
            <div className="mt-2 space-y-1 text-sm">
              {value.metrics.map((metric) => (
                <div className="flex flex-wrap items-center gap-2" key={metric.id}>
                  <CheckCircle2 className="size-4 text-emerald-600" />
                  <span>{metric.name}</span>
                  <code className="text-muted-foreground text-xs">
                    {String(metric.match.expected ?? metric.match.operator)}
                  </code>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="flex gap-2">
          {hasPendingDraft ? (
            <Button disabled={loading} onClick={openPendingDraft} type="button">
              查看生成结果
            </Button>
          ) : null}
          <Button
            disabled={loading}
            onClick={generate}
            type="button"
            variant={value || hasPendingDraft ? "outline" : "default"}
          >
            {loading ? <LoaderCircle className="animate-spin" /> : <Sparkles />}
            {value || hasPendingDraft ? "重新生成" : "运行样本并发现指标"}
          </Button>
          {value && !hasPendingDraft ? (
            <Button
              onClick={() => {
                setDraft(value);
                setVerified(true);
                setDraftFingerprint(requestFingerprint());
                setOpen(true);
                if (!result) {
                  void run();
                }
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
        <DialogContent className="max-h-[min(760px,calc(100vh-2rem))] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>SSE 指标配置</DialogTitle>
            <DialogDescription>
              {verified ? "所选规则已通过真实样本验证。" : "待验证：修改匹配规则后必须重新验证。"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {result ? (
              <div className="space-y-3">
                <div>
                  <strong>候选指标</strong>
                  <p className="text-muted-foreground text-xs">按真实样本证据推荐，不预设固定业务事件。</p>
                </div>
                {result.candidates.length === 0 ? (
                  <p className="rounded-lg border border-dashed p-4 text-muted-foreground text-sm">
                    本次样本未发现高可信度指标，可从其他事件中手动添加。
                  </p>
                ) : null}
                {result.candidates.map((candidate) => (
                  <label className="flex cursor-pointer gap-3 rounded-lg border p-4" key={candidate.suggestion_key}>
                    <input
                      checked={selectedKeys.includes(candidate.suggestion_key)}
                      className="mt-1"
                      onChange={() => toggleCandidate(candidate)}
                      type="checkbox"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center justify-between gap-2">
                        <strong>{candidate.name}</strong>
                        <span className="text-emerald-600 text-xs">
                          {candidate.recommendation_level === "recommended" ? "推荐" : "可选"}
                        </span>
                      </span>
                      <code className="mt-1 block break-all text-muted-foreground text-xs">
                        {candidate.match.path} = {String(candidate.match.expected)}
                      </code>
                      <span className="mt-2 block text-muted-foreground text-xs">
                        样本事件 #{candidate.validation.first_event_sequence ?? "-"} ·{" "}
                        {candidate.validation.sample_elapsed_ms ?? "-"} ms · 命中 {candidate.validation.matched_count}{" "}
                        次
                      </span>
                      <span className="mt-1 block text-xs">推荐原因：{candidate.reason}</span>
                      {candidate.uncertainty ? (
                        <span className="mt-1 block text-amber-700 text-xs">{candidate.uncertainty}</span>
                      ) : null}
                    </span>
                  </label>
                ))}
              </div>
            ) : null}

            {draft?.metrics.map((metric, index) => {
              const item = evidence.get(metric.id);
              const fieldPrefix = `sse-metric-${metric.id}-${index}`;
              return (
                <div className="rounded-lg border p-4" key={metric.id}>
                  <div className="flex items-center justify-between gap-3">
                    <strong>{metric.name}</strong>
                    <span className={verified ? "text-emerald-600 text-xs" : "text-amber-600 text-xs"}>
                      {verified ? "已验证" : "待验证"}
                    </span>
                  </div>
                  <div className="mt-3 rounded-md bg-muted/60 px-3 py-2 text-sm">
                    <dl className="grid gap-2 sm:grid-cols-[88px_1fr]">
                      <dt className="text-muted-foreground text-xs">所属接口</dt>
                      <dd className="break-all">
                        {metric.timing.source_request_name ??
                          metric.timing.source_request_id ??
                          scenarioStepId ??
                          "当前 SSE 请求"}
                      </dd>
                      <dt className="text-muted-foreground text-xs">开始时间</dt>
                      <dd>所属 SSE 接口请求发起</dd>
                      <dt className="text-muted-foreground text-xs">结束条件</dt>
                      <dd className="break-all">{metricMatchSummary(metric)}</dd>
                      <dt className="text-muted-foreground text-xs">计算方式</dt>
                      <dd>{metricTimingFormula(metric)}</dd>
                    </dl>
                  </div>
                  {item ? (
                    <p className="mt-2 text-muted-foreground text-xs">
                      样本事件 #{item.first_event_sequence ?? "-"} · {item.sample_elapsed_ms ?? "-"} ms · 命中{" "}
                      {item.matched_count} 次{item.matched_count > 1 ? "，仅取首次" : ""}
                    </p>
                  ) : null}
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm">高级匹配规则</summary>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <label className="space-y-1 text-sm" htmlFor={`${fieldPrefix}-name`}>
                        <span className="text-muted-foreground text-xs">指标名称</span>
                        <Input
                          id={`${fieldPrefix}-name`}
                          onChange={(event) => updateMetric(index, "name", event.target.value)}
                          value={metric.name}
                        />
                      </label>
                      <label className="space-y-1 text-sm" htmlFor={`${fieldPrefix}-event-name`}>
                        <span className="text-muted-foreground text-xs">SSE 事件类型</span>
                        <Input
                          id={`${fieldPrefix}-event-name`}
                          onChange={(event) => updateMetric(index, "event_name", event.target.value)}
                          value={metric.match.event_name}
                        />
                      </label>
                      <label className="space-y-1 text-sm" htmlFor={`${fieldPrefix}-path`}>
                        <span className="text-muted-foreground text-xs">JSON 字段路径</span>
                        <Input
                          id={`${fieldPrefix}-path`}
                          onChange={(event) => updateMetric(index, "path", event.target.value)}
                          value={metric.match.path}
                        />
                      </label>
                      <label className="space-y-1 text-sm" htmlFor={`${fieldPrefix}-expected`}>
                        <span className="text-muted-foreground text-xs">期望值</span>
                        <Input
                          id={`${fieldPrefix}-expected`}
                          onChange={(event) => updateMetric(index, "expected", event.target.value)}
                          value={String(metric.match.expected ?? "")}
                        />
                      </label>
                      <label className="space-y-1 text-sm sm:col-span-2" htmlFor={`${fieldPrefix}-missing-policy`}>
                        <span className="text-muted-foreground text-xs">未命中时</span>
                        <select
                          className="block h-9 w-full rounded-md border bg-background px-3 text-sm"
                          id={`${fieldPrefix}-missing-policy`}
                          onChange={(event) =>
                            updateMissingPolicy(index, event.target.value as "record_null" | "fail_request" | "ignore")
                          }
                          value={metric.missing_policy}
                        >
                          <option value="record_null">记录为缺失，不影响请求</option>
                          <option value="fail_request">将请求标记为失败</option>
                          <option value="ignore">忽略本次指标</option>
                        </select>
                        <span className="block text-muted-foreground text-xs">仅在本次请求未找到匹配事件时生效。</span>
                      </label>
                    </div>
                  </details>
                  {item?.sample_event ? (
                    <details className="mt-3">
                      <summary className="cursor-pointer text-sm">查看命中事件</summary>
                      <pre className="mt-3 overflow-x-auto rounded bg-muted p-3 text-xs">
                        样本事件：{JSON.stringify(item.sample_event, null, 2)}
                      </pre>
                    </details>
                  ) : null}
                </div>
              );
            })}

            {result?.event_facts.length ? (
              <details>
                <summary className="cursor-pointer font-medium">其他事件</summary>
                <div className="mt-3 space-y-2">
                  {result.event_facts.map((fact) => {
                    const used = result.candidates.some((candidate) =>
                      candidate.evidence_fact_ids.includes(fact.fact_id),
                    );
                    return (
                      <div
                        className="flex items-center justify-between gap-3 rounded-lg border p-3 text-sm"
                        key={fact.fact_id}
                      >
                        <div className="min-w-0">
                          <code className="block break-all text-xs">
                            {fact.path} = {fact.normalized_value}
                          </code>
                          <span className="text-muted-foreground text-xs">
                            首次 {fact.first_offset_ms} ms · 命中 {fact.matched_count} 次
                          </span>
                        </div>
                        <Button disabled={used} onClick={() => addFact(fact)} size="sm" type="button" variant="outline">
                          {used ? "已作为候选" : "添加为自定义指标"}
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </details>
            ) : null}

            {result?.end_rule_candidate ? (
              <div className="space-y-2 rounded-lg border p-4 text-sm">
                <label className="flex cursor-pointer items-start gap-2">
                  <input
                    checked={JSON.stringify(draft?.end_rule) === JSON.stringify(result.end_rule_candidate.match)}
                    className="mt-1"
                    onChange={toggleRecommendedEndRule}
                    type="checkbox"
                  />
                  <span>
                    <span className="block font-medium">启用推荐结束规则</span>
                    <span className="block text-muted-foreground text-xs">
                      默认不启用；启用后必须匹配该事件，否则请求会被标记为失败。
                    </span>
                  </span>
                </label>
                {JSON.stringify(draft?.end_rule) !== JSON.stringify(result.end_rule_candidate.match) ? (
                  <p className="text-muted-foreground text-xs">不启用结束规则，SSE 流自然结束时视为完成。</p>
                ) : null}
                <code className="block break-all text-xs">
                  {result.end_rule_candidate.match.path} = {String(result.end_rule_candidate.match.expected)}
                </code>
              </div>
            ) : null}

            {draft?.end_rule ? (
              <div className="flex items-center justify-between gap-3 rounded-lg border p-4 text-sm">
                <span>
                  当前流结束规则：
                  <code>
                    {draft.end_rule.path} = {String(draft.end_rule.expected)}
                  </code>
                </span>
                <Button onClick={removeEndRule} size="sm" type="button" variant="outline">
                  移除结束规则
                </Button>
              </div>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              disabled={loading || !draft || draft.metrics.length === 0}
              onClick={() => draft && void run(draft)}
              type="button"
              variant="outline"
            >
              {loading ? <LoaderCircle className="animate-spin" /> : null}
              重新验证
            </Button>
            <Button onClick={() => setOpen(false)} type="button" variant="outline">
              暂存并关闭
            </Button>
            <Button
              disabled={!draft || draft.metrics.length === 0 || !verified || loading}
              onClick={apply}
              type="button"
            >
              应用
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
