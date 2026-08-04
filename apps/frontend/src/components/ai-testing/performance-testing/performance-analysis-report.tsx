"use client";

import { useCallback, useEffect, useState } from "react";

import { useRouter } from "next/navigation";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Gauge,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  createPerformanceAnalysis,
  getPerformanceAnalysis,
  type PerformanceAnalysis,
  type PerformanceMetricSnapshot,
  type PerformanceReportFinding,
} from "@/lib/api-client";

const ACTIVE_ANALYSIS = new Set(["collecting", "analyzing"]);
const TREND_CHART_INITIAL_DIMENSION = { height: 260, width: 480 } as const;

export function PerformanceAnalysisReport({
  projectId,
  testId,
  runId,
  analysisId,
}: {
  projectId: string;
  testId: string;
  runId: string;
  analysisId: string;
}) {
  const router = useRouter();
  const [analysis, setAnalysis] = useState<PerformanceAnalysis | null>(null);
  const [error, setError] = useState("");
  const [reanalyzing, setReanalyzing] = useState(false);

  const load = useCallback(async () => {
    try {
      setError("");
      setAnalysis(await getPerformanceAnalysis(projectId, analysisId));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "性能分析报告加载失败");
    }
  }, [analysisId, projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!analysis || !ACTIVE_ANALYSIS.has(analysis.analysis_status)) return;
    const timer = window.setInterval(() => void load(), 2000);
    return () => window.clearInterval(timer);
  }, [analysis, load]);

  if (error) {
    return (
      <div className="flex min-h-72 flex-col items-center justify-center rounded-lg border bg-card px-6 text-center">
        <AlertTriangle className="mb-3 size-6 text-destructive" />
        <h2 className="font-semibold">报告加载失败</h2>
        <p className="mt-2 max-w-lg text-muted-foreground text-sm">{error}</p>
        <Button className="mt-5" onClick={() => void load()} variant="outline">
          <RefreshCw className="size-4" />
          重新加载
        </Button>
      </div>
    );
  }

  if (!analysis || ACTIVE_ANALYSIS.has(analysis.analysis_status)) {
    return (
      <div className="flex min-h-72 items-center justify-center text-muted-foreground text-sm">
        <LoaderCircle className="mr-2 size-4 animate-spin" />
        {analysis?.analysis_stage === "ai_diagnosis" ? "正在生成诊断结论" : "正在计算性能指标"}
      </div>
    );
  }

  const metric = analysis.metric_snapshot ?? {};
  const report = analysis.report_snapshot ?? {};
  const aggregate = metric.aggregate ?? {};
  const quality = metric.quality ?? {};
  const testScope = metric.test_scope ?? {};
  const endpointMetrics = metric.endpoint_metrics ?? [];
  const sseMetrics = metric.sse_metrics?.metrics ?? [];
  const objectives = metric.objectives ?? [];
  const stageAnalysis = metric.stage_analysis ?? [];
  const capacityAnalysis = metric.capacity_analysis ?? {};
  const failureAnalysis = metric.failure_analysis ?? [];
  const verdict = report.verdict ?? metric.verdict ?? "indeterminate";
  const findings = (report.findings ?? [])
    .filter(
      (finding) => !isRedundantPassFinding(finding, verdict) && isSupportedFinding(finding, metric.latency_analysis),
    )
    .map((finding) => ({
      ...finding,
      severity: normalizedFindingSeverity(finding, verdict, objectives),
    }));
  const findingIds = new Set(findings.map((finding) => finding.id));
  const recommendations = (report.recommendations ?? [])
    .filter((recommendation) => isSupportedRecommendation(recommendation, findingIds))
    .map((recommendation) => ({
      ...recommendation,
      priority: normalizedRecommendationPriority(recommendation, findings, verdict, objectives),
    }))
    .slice(0, 3);
  const series = metric.series ?? [];
  const hasP50Series = series.some(
    (item) => item.p50_response_time_ms !== null && item.p50_response_time_ms !== undefined,
  );
  const scopeItems = buildScopeItems(testScope);
  const unconfiguredMetrics = observedMetricsWithoutObjectives(aggregate, objectives);
  const isFallback = analysis.generation_mode === "deterministic_fallback";
  const showCapacityAnalysis =
    stageAnalysis.length > 1 && Boolean(capacityAnalysis.observed_stable_capacity || capacityAnalysis.knee_point);

  async function reanalyze() {
    try {
      setReanalyzing(true);
      setError("");
      const created = await createPerformanceAnalysis(projectId, runId);
      router.push(`/projects/${projectId}/performance-tests/${testId}/runs/${runId}/analysis/${created.id}`);
    } catch (reanalyzeError) {
      setError(reanalyzeError instanceof Error ? reanalyzeError.message : "重新分析失败");
      setReanalyzing(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-[90rem] space-y-7">
      {isFallback ? (
        <section className="flex flex-col gap-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-950 sm:flex-row sm:items-center sm:justify-between dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
          <div>
            <p className="font-medium text-sm">当前为基础性能报告</p>
            <p className="mt-1 text-sm opacity-80">确定性指标和目标判定已生成；AI 根因分析及修复建议未生成。</p>
          </div>
          <Button disabled={reanalyzing} onClick={() => void reanalyze()} variant="outline">
            {reanalyzing ? <LoaderCircle className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            重新分析
          </Button>
        </section>
      ) : null}

      <section className={`overflow-hidden rounded-lg border border-l-4 bg-card ${verdictAccentClass(verdict)}`}>
        <div className="grid xl:grid-cols-[minmax(34rem,1.15fr)_minmax(22rem,0.85fr)]">
          <div className="p-5 sm:p-6 xl:pr-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-muted-foreground text-xs">
                <span>性能结论</span>
              </div>
              <p className="text-muted-foreground text-xs">
                数据质量 <span className="ml-1 font-medium text-foreground">{qualityLabel(quality.status)}</span>
              </p>
            </div>
            <div className="mt-3 flex items-center gap-2">
              <VerdictGlyph verdict={verdict} />
              <h1 className="font-semibold text-3xl tabular-nums">{verdictLabel(verdict)}</h1>
            </div>
            <p className="mt-2 max-w-xl text-muted-foreground text-sm leading-6">
              {verdictSummary(verdict, objectives.length, aggregate.requests_per_second)}
            </p>

            <div className="mt-5 border-t pt-4">
              <h2 className="font-medium text-muted-foreground text-xs" id="core-metrics-heading">
                核心指标
              </h2>
              <section
                aria-labelledby="core-metrics-heading"
                className="mt-5 grid grid-cols-2 gap-x-6 gap-y-6 sm:grid-cols-3 2xl:grid-cols-5"
              >
                <ReportMetric label="请求总数" value={numberValue(aggregate.request_count)} />
                <ReportMetric label="观测吞吐" suffix=" RPS" value={decimalValue(aggregate.requests_per_second)} />
                <ReportMetric label="失败率" suffix="%" value={percentageValue(aggregate.failure_rate)} />
                <ReportMetric label="P95 响应时间" suffix=" ms" value={nullableValue(aggregate.p95_response_time_ms)} />
                <ReportMetric label="P99 响应时间" suffix=" ms" value={nullableValue(aggregate.p99_response_time_ms)} />
              </section>
            </div>
          </div>

          <div className="border-t bg-muted/20 p-5 sm:p-6 xl:border-t-0 xl:border-l xl:pl-8">
            {scopeItems.length ? (
              <section aria-labelledby="test-config-heading" className="flex h-full flex-col justify-center">
                <div className="flex items-center gap-2 text-muted-foreground text-xs">
                  <Gauge className="size-3.5" />
                  <h2 id="test-config-heading" className="font-medium">
                    测试配置
                  </h2>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-x-8">
                  {scopeItems.map((item) => (
                    <div className="border-t py-3" key={item.label}>
                      <dt className="text-[11px] text-muted-foreground">{item.label}</dt>
                      <dd className="mt-1 truncate font-medium text-sm tabular-nums" title={item.value}>
                        {item.value}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            ) : null}
          </div>
        </div>
      </section>

      {sseMetrics.length ? (
        <section className="space-y-4">
          <SectionHeading icon={Clock3} title="SSE 事件指标" />
          {metric.sse_metrics?.truncated ? (
            <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-amber-900 text-sm dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
              测量文件达到大小上限，以下结果仅基于已保留样本。
            </p>
          ) : null}
          {metric.sse_metrics?.parse_error_count ||
          metric.sse_metrics?.timeout_count ||
          metric.sse_metrics?.end_rule_not_matched_count ? (
            <p className="text-muted-foreground text-sm">
              数据质量：JSON 解析错误 {metric.sse_metrics.parse_error_count ?? 0}，流超时 {metric.sse_metrics.timeout_count ?? 0}
              ，结束规则未命中 {metric.sse_metrics.end_rule_not_matched_count ?? 0}。
            </p>
          ) : null}
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[48rem] text-sm">
              <thead className="bg-muted/50 text-left text-muted-foreground text-xs">
                <tr>
                  <th className="px-4 py-3 font-medium">指标</th>
                  <th className="px-4 py-3 font-medium">样本</th>
                  <th className="px-4 py-3 font-medium">缺失</th>
                  <th className="px-4 py-3 font-medium">失败</th>
                  <th className="px-4 py-3 font-medium">平均</th>
                  <th className="px-4 py-3 font-medium">P50</th>
                  <th className="px-4 py-3 font-medium">P95</th>
                  <th className="px-4 py-3 font-medium">P99</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {sseMetrics.map((item) => (
                  <tr key={item.metric_id}>
                    <td className="px-4 py-3 font-medium">{item.name || item.metric_id}</td>
                    <td className="px-4 py-3 tabular-nums">{numberValue(item.matched_count)}</td>
                    <td className="px-4 py-3 tabular-nums">{numberValue(item.missing_count)}</td>
                    <td className="px-4 py-3 tabular-nums">{numberValue(item.failure_count)}</td>
                    <td className="px-4 py-3 tabular-nums">{millisecondsValue(item.average_ms)}</td>
                    <td className="px-4 py-3 tabular-nums">{millisecondsValue(item.p50_ms)}</td>
                    <td className="px-4 py-3 tabular-nums">{millisecondsValue(item.p95_ms)}</td>
                    <td className="px-4 py-3 tabular-nums">{millisecondsValue(item.p99_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="space-y-4">
        <SectionHeading icon={ShieldCheck} title="性能目标" />
        {objectives.length ? (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[42rem] text-sm">
              <thead className="bg-muted/50 text-left text-muted-foreground text-xs">
                <tr>
                  <th className="px-4 py-3 font-medium">指标</th>
                  <th className="px-4 py-3 font-medium">目标</th>
                  <th className="px-4 py-3 font-medium">实际</th>
                  <th className="px-4 py-3 font-medium">状态</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {objectives.map((objective) => (
                  <tr key={objective.evidence_id}>
                    <td className="px-4 py-3 font-medium">{metricLabel(objective.metric)}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {objective.operator === "lte" ? "≤" : "≥"} {formatMetric(objective.metric, objective.target)}
                    </td>
                    <td className="px-4 py-3">{formatMetric(objective.metric, objective.actual)}</td>
                    <td className="px-4 py-3">
                      <ObjectiveStatus status={objective.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="rounded-lg border bg-card p-4 text-muted-foreground text-sm">
            未配置性能目标，当前指标仅用于观测，不作通过或失败判定。
          </p>
        )}
        {unconfiguredMetrics.length ? (
          <p className="text-muted-foreground text-xs">
            {unconfiguredMetrics.join("、")} 未配置验收目标，仅作为观察指标。
          </p>
        ) : null}
      </section>

      <section className="space-y-4">
        <SectionHeading icon={Activity} title="接口表现" />
        {endpointMetrics.length ? (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[52rem] text-sm">
              <thead className="bg-muted/50 text-left text-muted-foreground text-xs">
                <tr>
                  <th className="px-4 py-3 font-medium">接口</th>
                  <th className="px-4 py-3 font-medium">请求占比</th>
                  <th className="px-4 py-3 font-medium">请求数</th>
                  <th className="px-4 py-3 font-medium">失败率</th>
                  <th className="px-4 py-3 font-medium">平均</th>
                  <th className="px-4 py-3 font-medium">P95</th>
                  <th className="px-4 py-3 font-medium">P99</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {endpointMetrics.map((endpoint) => (
                  <tr key={`${endpoint.method}:${endpoint.name}`}>
                    <td className="max-w-80 px-4 py-2.5">
                      <span className="mr-2 font-semibold text-xs">{endpoint.method}</span>
                      <span className="break-all font-mono text-xs">
                        {endpointDisplayName(endpoint.method, endpoint.name)}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 tabular-nums">{percentageValue(endpoint.request_share)}%</td>
                    <td className="px-4 py-2.5 tabular-nums">{numberValue(endpoint.request_count)}</td>
                    <td className="px-4 py-2.5 tabular-nums">{percentageValue(endpoint.failure_rate)}%</td>
                    <td className="px-4 py-2.5 tabular-nums">{millisecondsValue(endpoint.average_response_time_ms)}</td>
                    <td className="px-4 py-2.5 tabular-nums">{millisecondsValue(endpoint.p95_response_time_ms)}</td>
                    <td className="px-4 py-2.5 tabular-nums">{millisecondsValue(endpoint.p99_response_time_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="rounded-lg border bg-card p-4 text-muted-foreground text-sm">
            当前快照没有可信的接口级统计，未使用全局指标推算接口结果。
          </p>
        )}
        {failureAnalysis.length ? (
          <div className="space-y-3 pt-2">
            <h3 className="font-medium text-sm">失败分类</h3>
            <div className="divide-y rounded-lg border">
              {failureAnalysis.map((failure) => (
                <div className="grid gap-2 p-4 sm:grid-cols-[10rem_minmax(0,1fr)]" key={failure.kind}>
                  <div className="flex items-center justify-between gap-3 sm:block">
                    <p className="font-medium text-sm">{failureKindLabel(failure.kind)}</p>
                    <p className="mt-1 text-muted-foreground text-xs">
                      {failure.count} 次 · {percentageValue(failure.ratio)}%
                    </p>
                  </div>
                  <p className="text-muted-foreground text-sm">{failure.example || "未记录示例原因"}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      {stageAnalysis.length > 1 ? (
        <section
          className={
            showCapacityAnalysis ? "grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]" : "space-y-4"
          }
        >
          <div className="space-y-4">
            <SectionHeading icon={TrendingUp} title="负载阶段" />
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full min-w-[42rem] text-sm">
                <thead className="bg-muted/50 text-left text-muted-foreground text-xs">
                  <tr>
                    <th className="px-4 py-3 font-medium">阶段</th>
                    <th className="px-4 py-3 font-medium">并发</th>
                    <th className="px-4 py-3 font-medium">RPS</th>
                    <th className="px-4 py-3 font-medium">P95</th>
                    <th className="px-4 py-3 font-medium">失败率</th>
                    <th className="px-4 py-3 font-medium">判定</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {stageAnalysis.map((stage) => (
                    <tr key={stage.name}>
                      <td className="px-4 py-3 font-medium">{stage.name}</td>
                      <td className="px-4 py-3 tabular-nums">{stage.actual_users ?? stage.target_users}</td>
                      <td className="px-4 py-3 tabular-nums">{decimalValue(stage.requests_per_second)}</td>
                      <td className="px-4 py-3 tabular-nums">{nullableValue(stage.p95_response_time_ms)}</td>
                      <td className="px-4 py-3 tabular-nums">{percentageValue(stage.failure_rate)}</td>
                      <td className="px-4 py-3">
                        <StageStatus status={stage.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {showCapacityAnalysis ? (
            <div className="space-y-4">
              <SectionHeading icon={Gauge} title="容量判断" />
              <div className="rounded-lg border bg-card p-4 text-sm">
                {capacityAnalysis.observed_stable_capacity ? (
                  <>
                    <p className="text-muted-foreground">观测稳定容量</p>
                    <p className="mt-2 font-semibold text-xl tabular-nums">
                      {capacityAnalysis.observed_stable_capacity.users ?? "-"} 并发
                    </p>
                    <p className="mt-1 text-muted-foreground">
                      {decimalValue(capacityAnalysis.observed_stable_capacity.requests_per_second)} RPS · P95{" "}
                      {nullableValue(capacityAnalysis.observed_stable_capacity.p95_response_time_ms)}
                    </p>
                  </>
                ) : null}
                {capacityAnalysis.knee_point ? (
                  <p className="mt-4 border-t pt-3 text-muted-foreground text-xs">
                    拐点区间：{capacityAnalysis.knee_point.between_users?.join(" ~ ")} 并发
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {series.length ? (
        <section className="space-y-4">
          <SectionHeading icon={TrendingUp} title="运行趋势" />
          <div className="grid gap-4 xl:grid-cols-2">
            <article className="min-w-0 rounded-lg border bg-card px-4 pt-4 pb-3 sm:px-5">
              <header className="flex min-h-20 flex-wrap items-start justify-between gap-4 border-b pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-sm">响应延迟</h3>
                    <span aria-hidden="true" className="h-3 w-px bg-border" />
                    <span className="font-medium text-[11px] text-muted-foreground">核心指标</span>
                  </div>
                  <p className="mt-1 text-muted-foreground text-xs">观察请求响应速度是否稳定</p>
                </div>
                <div className={`grid gap-x-5 tabular-nums ${hasP50Series ? "grid-cols-3" : "grid-cols-2"}`}>
                  {hasP50Series ? (
                    <TrendMetric
                      color="bg-[var(--chart-1)]"
                      label="P50"
                      suffix="ms"
                      value={nullableValue(aggregate.p50_response_time_ms)}
                    />
                  ) : null}
                  <TrendMetric
                    color="bg-[var(--chart-4)]"
                    label="P95"
                    suffix="ms"
                    value={nullableValue(aggregate.p95_response_time_ms)}
                  />
                  <TrendMetric
                    color="bg-destructive"
                    label="P99"
                    suffix="ms"
                    value={nullableValue(aggregate.p99_response_time_ms)}
                  />
                </div>
              </header>
              <div className="h-[17rem] pt-4">
                <ResponsiveContainer height="100%" initialDimension={TREND_CHART_INITIAL_DIMENSION} width="100%">
                  <LineChart data={series} margin={{ bottom: 8, left: 0, right: 8, top: 4 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                    <XAxis
                      axisLine={false}
                      dataKey="sampled_at"
                      minTickGap={36}
                      tickFormatter={formatSampleTimestamp}
                      tickLine={false}
                    />
                    <YAxis
                      axisLine={false}
                      domain={[0, "auto"]}
                      tickFormatter={(value) => `${value} ms`}
                      tickLine={false}
                      width={62}
                    />
                    <TrendTooltip />
                    {hasP50Series ? (
                      <Line
                        dataKey="p50_response_time_ms"
                        dot={false}
                        name="P50"
                        stroke="var(--chart-1)"
                        strokeWidth={2}
                        type="monotone"
                      />
                    ) : null}
                    <Line
                      dataKey="p95_response_time_ms"
                      dot={false}
                      name="P95"
                      stroke="var(--chart-4)"
                      strokeWidth={2.5}
                      type="monotone"
                    />
                    <Line
                      dataKey="p99_response_time_ms"
                      dot={false}
                      name="P99"
                      stroke="var(--destructive)"
                      strokeWidth={2.5}
                      type="monotone"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </article>

            <article className="min-w-0 rounded-lg border bg-card px-4 pt-4 pb-3 sm:px-5">
              <header className="flex min-h-20 items-start justify-between gap-4 border-b pb-4">
                <div>
                  <h3 className="font-medium text-sm">吞吐量</h3>
                  <p className="mt-1 text-muted-foreground text-xs">观察服务处理能力是否稳定</p>
                </div>
                <TrendMetric
                  color="bg-[var(--chart-2)]"
                  label="RPS"
                  value={decimalValue(aggregate.requests_per_second)}
                />
              </header>
              <div className="h-[17rem] pt-4">
                <ResponsiveContainer height="100%" initialDimension={TREND_CHART_INITIAL_DIMENSION} width="100%">
                  <LineChart data={series} margin={{ bottom: 8, left: 0, right: 8, top: 4 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                    <XAxis
                      axisLine={false}
                      dataKey="sampled_at"
                      minTickGap={36}
                      tickFormatter={formatSampleTimestamp}
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals
                      axisLine={false}
                      domain={[0, "auto"]}
                      tickFormatter={(value) => `${value}`}
                      tickLine={false}
                      width={38}
                    />
                    <TrendTooltip />
                    <Line
                      dataKey="requests_per_second"
                      dot={false}
                      name="RPS"
                      stroke="var(--chart-2)"
                      strokeWidth={2.5}
                      type="monotone"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </article>
          </div>
        </section>
      ) : null}

      {!isFallback && findings.length ? (
        <section className="space-y-4">
          <SectionHeading
            icon={CircleHelp}
            title={verdict === "pass" || verdict === "conditional_pass" ? "风险与边界" : "诊断发现"}
          />
          <article className="min-w-0 divide-y rounded-lg border bg-card px-4 sm:px-5">
            {findings.map((finding) => (
              <div className="py-4" key={finding.id}>
                <div className="flex min-w-0 items-start justify-between gap-3">
                  <h3 className="min-w-0 font-medium text-sm leading-5">{finding.title}</h3>
                  <Badge className={severityBadgeClass(finding.severity)} variant="outline">
                    {severityLabel(finding.severity)}
                  </Badge>
                </div>
                <p className="mt-1 whitespace-pre-wrap text-muted-foreground text-xs leading-5">
                  {displayFindingStatement(finding, testScope.users)}
                </p>
              </div>
            ))}
          </article>
        </section>
      ) : null}

      {!isFallback && recommendations.length ? (
        <section className="space-y-4">
          <SectionHeading icon={CheckCircle2} title="优化与复测建议" />
          <article className="min-w-0 divide-y rounded-lg border bg-card px-4 sm:px-5">
            {recommendations.map((recommendation) => (
              <div className="py-4" key={recommendation.id}>
                <div className="flex min-w-0 items-start justify-between gap-3">
                  <p className="min-w-0 text-muted-foreground text-xs leading-5">
                    {recommendationAction(recommendation.action)}
                  </p>
                  <Badge
                    className={`${severityBadgeClass("low")} shrink-0 font-semibold tabular-nums`}
                    variant="outline"
                  >
                    {recommendation.priority}
                  </Badge>
                </div>
                <div className="mt-2 border-t pt-2 text-muted-foreground text-xs leading-5">
                  {recommendation.verification ? (
                    <p>
                      <span className="font-medium text-foreground/80">验证</span>{" "}
                      {recommendationVerification(recommendation.verification)}
                    </p>
                  ) : null}
                  {recommendation.acceptance_criteria?.length ? (
                    <p className="mt-1">
                      <span className="font-medium text-foreground/80">验收</span>{" "}
                      {recommendation.acceptance_criteria.join("；")}
                    </p>
                  ) : null}
                </div>
              </div>
            ))}
          </article>
        </section>
      ) : null}
    </div>
  );
}

function ReportMetric({ label, value, suffix = "" }: { label: string; value: string; suffix?: string }) {
  return (
    <div className="min-w-0">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-2 font-semibold text-2xl tabular-nums">
        {value}
        {value === "不可用" ? null : <span className="ml-1 font-normal text-muted-foreground text-xs">{suffix}</span>}
      </p>
    </div>
  );
}

function TrendMetric({
  color,
  label,
  value,
  suffix = "",
}: {
  color: string;
  label: string;
  value: string;
  suffix?: string;
}) {
  return (
    <div className="min-w-[5.25rem] text-left">
      <p className="flex items-center gap-1.5 text-muted-foreground text-xs">
        <span className={`size-1.5 rounded-full ${color}`} />
        {label}
      </p>
      <p className="mt-1 font-semibold text-lg tabular-nums">
        {value}
        {value === "不可用" || !suffix ? null : <span className="ml-1 text-muted-foreground text-xs">{suffix}</span>}
      </p>
    </div>
  );
}

function TrendTooltip() {
  return (
    <Tooltip
      contentStyle={{
        backgroundColor: "var(--popover)",
        border: "1px solid var(--border)",
        borderRadius: "6px",
        boxShadow: "0 12px 32px rgb(0 0 0 / 32%)",
        color: "var(--popover-foreground)",
        padding: "10px 12px",
      }}
      cursor={{
        stroke: "var(--muted-foreground)",
        strokeDasharray: "3 3",
        strokeOpacity: 0.4,
      }}
      formatter={(value, name) => [formatTrendValue(value, String(name)), name]}
      itemStyle={{ padding: "2px 0" }}
      labelFormatter={(value) => `采样时间：${formatSampleTimestamp(value)}`}
      labelStyle={{
        color: "var(--muted-foreground)",
        fontSize: "12px",
        marginBottom: "6px",
      }}
    />
  );
}

function SectionHeading({ icon: Icon, id, title }: { icon: typeof Activity; id?: string; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="size-4 text-muted-foreground" />
      <h2 className="font-semibold text-base" id={id}>
        {title}
      </h2>
    </div>
  );
}

function VerdictGlyph({ verdict }: { verdict: string }) {
  const Icon = verdict === "pass" ? CheckCircle2 : verdict === "fail" ? AlertTriangle : CircleHelp;
  const colorClass =
    verdict === "pass"
      ? "text-emerald-600 dark:text-emerald-400"
      : verdict === "fail"
        ? "text-destructive"
        : verdict === "conditional_pass"
          ? "text-amber-600 dark:text-amber-400"
          : "text-muted-foreground";
  return <Icon className={`size-6 shrink-0 ${colorClass}`} />;
}

function verdictAccentClass(verdict: string) {
  if (verdict === "pass") return "border-l-emerald-500";
  if (verdict === "fail") return "border-l-destructive";
  if (verdict === "conditional_pass") return "border-l-amber-500";
  return "border-l-muted-foreground";
}

type TestScope = NonNullable<PerformanceAnalysis["metric_snapshot"]["test_scope"]>;

function buildScopeItems(scope: TestScope) {
  const items: Array<{ label: string; value: string }> = [];
  if (scope.environment_name) items.push({ label: "环境", value: scope.environment_name });
  if (scope.load_mode) items.push({ label: "负载", value: loadModeLabel(scope.load_mode) });
  if (scope.users) items.push({ label: "用户", value: `${scope.users}` });
  if (scope.spawn_rate) items.push({ label: "启动", value: `${scope.spawn_rate.toFixed(2)}/s` });
  if (scope.duration_seconds) items.push({ label: "时长", value: `${scope.duration_seconds}s` });
  if (scope.stage_count && scope.stage_count > 0) items.push({ label: "阶段", value: `${scope.stage_count}` });
  if (scope.wait_time_min_seconds !== null && scope.wait_time_min_seconds !== undefined) {
    const max = scope.wait_time_max_seconds ?? scope.wait_time_min_seconds;
    items.push({ label: "等待", value: `${scope.wait_time_min_seconds}~${max}s` });
  }
  return items;
}

function verdictSummary(verdict: string, objectiveCount: number, rps?: number) {
  const objectiveText = objectiveCount ? `${objectiveCount} 项已配置性能目标` : "";
  const observedText = rps === undefined ? "" : `，观测吞吐 ${rps.toFixed(2)} RPS`;
  if (!objectiveCount) return `当前结果仅用于观测，不作通过或失败判定${observedText}。`;
  if (verdict === "pass") return `${objectiveText}全部通过${observedText}。`;
  if (verdict === "conditional_pass") return `${objectiveText}通过，但存在影响结论范围的数据限制${observedText}。`;
  if (verdict === "fail") return `${objectiveText}中至少一项未通过${observedText}。`;
  return `当前证据不足以完成${objectiveText}判定${observedText}。`;
}

function endpointDisplayName(method: string, name: string) {
  const trimmed = name.trim();
  const methodPrefix = `${method.trim()} `;
  return method && trimmed.toUpperCase().startsWith(methodPrefix.toUpperCase())
    ? trimmed.slice(methodPrefix.length).trim()
    : trimmed;
}

function observedMetricsWithoutObjectives(
  aggregate: NonNullable<PerformanceAnalysis["metric_snapshot"]["aggregate"]>,
  objectives: Array<{ metric: string }>,
) {
  const configured = new Set(objectives.map((objective) => objective.metric));
  const observed: Array<[string, string, number | null | undefined]> = [
    ["P95", "p95_response_time_ms", aggregate.p95_response_time_ms],
    ["P99", "p99_response_time_ms", aggregate.p99_response_time_ms],
    ["吞吐量", "requests_per_second", aggregate.requests_per_second],
  ];
  return observed
    .filter(([, metric, value]) => value !== null && value !== undefined && !configured.has(metric))
    .map(([label]) => label);
}

function isRedundantPassFinding(finding: { title: string; statement: string }, verdict: string) {
  if (verdict !== "pass" && verdict !== "conditional_pass") return false;
  const text = `${finding.title} ${finding.statement}`;
  const passSummary =
    /(?:目标|指标|验收|测试有效性|performance).*?(?:通过|满足|达成|合格|passed)|(?:全部|均).*?(?:通过|满足|达成|合格|passed)/i.test(
      text,
    );
  const materialConcern = /无法|不足|限制|风险|异常|缺少|不能|未评估|未配置|仅(?:验证|覆盖)|不代表/i.test(text);
  return passSummary && !materialConcern;
}

function isCapacityBoundaryFinding(finding: { title: string; statement: string; evidence_refs?: string[] }) {
  const text = `${finding.title} ${finding.statement}`;
  const capacityBoundary =
    finding.evidence_refs?.includes("capacity:summary") ||
    /容量上限|容量拐点|性能拐点|固定(?:单阶段)?负载|阶梯加压/i.test(text);
  return Boolean(capacityBoundary) && !hasPerformanceFailureSignal(text);
}

function hasPerformanceFailureSignal(text: string) {
  if (/请求失败|失败请求|失败率(?:上升|恶化|超标|非零)|退化|恶化|超时|错误|目标未通过/i.test(text)) {
    return true;
  }
  return [...text.matchAll(/失败率\s*(?:为|=|：|:|>|≥)?\s*(\d+(?:\.\d+)?)\s*%/gi)].some(
    (match) => Number(match[1]) > 0,
  );
}

function displayFindingStatement(
  finding: { title: string; statement: string; evidence_refs?: string[] },
  users?: number | null,
) {
  const exposesInternalCapacityFields =
    /load\.mode|stages|capacity_analysis|can_claim_stable_capacity|knee_point|\b(?:false|null)\b/i.test(
      finding.statement,
    );
  if (!isCapacityBoundaryFinding(finding) || !exposesInternalCapacityFields) return finding.statement;
  const loadScope = users && users > 0 ? `${users} 用户固定负载` : "当前固定负载";
  return `本次仅验证了 ${loadScope}下的表现。由于未进行分阶段加压，当前结果不能用于判断系统容量上限或性能拐点，也不能据此宣称已获得稳定容量。`;
}

function shouldDemoteCapacityBoundary(
  finding: { title: string; statement: string; evidence_refs?: string[] },
  verdict: string,
  objectives: Array<{ metric: string }>,
) {
  return (
    (verdict === "pass" || verdict === "conditional_pass") &&
    !objectives.some((objective) => objective.metric === "requests_per_second") &&
    isCapacityBoundaryFinding(finding)
  );
}

function normalizedFindingSeverity(
  finding: PerformanceReportFinding,
  verdict: string,
  objectives: Array<{ metric: string }>,
) {
  return shouldDemoteCapacityBoundary(finding, verdict, objectives) ? "low" : finding.severity;
}

function normalizedRecommendationPriority(
  recommendation: { priority: string; finding_refs?: string[] },
  findings: Array<{ id: string; title: string; statement: string; evidence_refs?: string[] }>,
  verdict: string,
  objectives: Array<{ metric: string }>,
) {
  const refs = new Set(recommendation.finding_refs ?? []);
  const referencedFindings = findings.filter((finding) => refs.has(finding.id));
  return referencedFindings.length > 0 &&
    referencedFindings.every((finding) => shouldDemoteCapacityBoundary(finding, verdict, objectives))
    ? "P2"
    : recommendation.priority;
}

function severityLabel(severity: string) {
  return { critical: "严重", high: "高", medium: "中", low: "低" }[severity] ?? severity.toUpperCase();
}

function severityBadgeClass(severity: string) {
  if (severity === "critical" || severity === "high") {
    return "border-destructive/30 bg-destructive/5 text-destructive";
  }
  if (severity === "medium") return "border-amber-500/30 bg-amber-500/5 text-amber-700 dark:text-amber-300";
  return "border-sky-500/30 bg-sky-500/5 text-sky-700 dark:text-sky-300";
}

function isSupportedFinding(
  finding: { title: string; statement: string },
  latencyAnalysis: PerformanceMetricSnapshot["latency_analysis"],
) {
  const text = `${finding.title} ${finding.statement}`;
  if (/p99_sample_size_limited|P99.*样本量|尾部延迟置信度不足/i.test(text)) return false;
  if (latencyAnalysis?.can_claim_direction !== true) {
    if (/P(?:50|95|99)|延迟|响应时间/i.test(text) && /下降|上升|改善|恶化|收敛|稳定趋势|持续变好|持续变差/.test(text)) {
      return false;
    }
  }
  return true;
}

function recommendationVerification(value: string) {
  if (exposesInternalCapacityFields(value) || /拐点.*非空/i.test(value)) {
    return "复测后报告应给出容量拐点，或明确当前配置下已验证的最大稳定负载，并展示各级 P95、P99、失败率与吞吐量随负载变化的曲线。";
  }
  return value;
}

function recommendationAction(value: string) {
  return exposesInternalCapacityFields(value) ? "补充分阶段阶梯加压复测。" : value;
}

function exposesInternalCapacityFields(value: string) {
  return /load\.mode|stages|capacity_analysis|can_claim_stable_capacity|knee_point|\b(?:true|false|null)\b/i.test(
    value,
  );
}

function isSupportedRecommendation(
  recommendation: { action: string; expected_effect?: string; verification?: string; finding_refs?: string[] },
  findingIds: Set<string>,
) {
  const { action, expected_effect: expectedEffect, finding_refs: findingRefs, verification } = recommendation;
  const text = `${action} ${expectedEffect ?? ""} ${verification ?? ""}`;
  if (/服务端资源|server.resource|CPU|内存|数据库连接|连接池|调用链|resource_correlation/i.test(text)) {
    return false;
  }
  const refs = findingRefs ?? [];
  return refs.length > 0 && refs.every((ref) => findingIds.has(ref));
}

function loadModeLabel(value: string) {
  return (
    {
      fixed: "固定负载",
      gradient: "阶梯加压",
      stress: "压力测试",
      spike: "峰值测试",
      endurance: "稳定性测试",
    }[value] ?? value
  );
}

function ObjectiveStatus({ status }: { status: string }) {
  if (status === "passed") return <Badge variant="secondary">通过</Badge>;
  if (status === "failed") return <Badge variant="destructive">未通过</Badge>;
  return <Badge variant="outline">未判断</Badge>;
}

function StageStatus({ status }: { status?: string }) {
  if (status === "degraded") return <Badge variant="destructive">退化</Badge>;
  if (status === "stable") return <Badge variant="secondary">稳定</Badge>;
  return <Badge variant="outline">证据不足</Badge>;
}

function failureKindLabel(value: string) {
  return (
    (
      {
        timeout: "超时",
        connection_error: "连接错误",
        assertion_failure: "断言失败",
        rate_limit: "限流",
        http_4xx: "HTTP 4xx",
        http_5xx: "HTTP 5xx",
        unknown: "未知错误",
      } as Record<string, string>
    )[value] ?? value
  );
}

function verdictLabel(value: string) {
  return (
    { pass: "通过", conditional_pass: "有条件通过", fail: "不通过", indeterminate: "无法判断" }[value] ?? "无法判断"
  );
}

function qualityLabel(value?: string) {
  return { complete: "基础数据完整", partial: "部分可用", invalid: "数据无效" }[value ?? ""] ?? "未知";
}

function metricLabel(value: string) {
  if (value.startsWith("sse:")) {
    const [, metricId, percentile] = value.split(":");
    return `${metricId} ${percentile.replace("_ms", "").toUpperCase()}`;
  }
  return (
    {
      failure_rate: "失败率",
      average_response_time_ms: "平均响应时间",
      p95_response_time_ms: "P95 响应时间",
      requests_per_second: "平均吞吐量",
    }[value] ?? value
  );
}

function formatMetric(metric: string, value: number | null) {
  if (value === null || value === undefined) return "不可用";
  if (metric === "failure_rate") return `${(value * 100).toFixed(2)}%`;
  if (metric.includes("response_time") || metric.startsWith("sse:")) return `${value.toFixed(2)} ms`;
  if (metric === "requests_per_second") return `${value.toFixed(2)} RPS`;
  return value.toFixed(2);
}

function formatSampleTimestamp(value: unknown) {
  const text = String(value ?? "").trim();
  if (!text) return "-";

  const numericTimestamp = Number(text);
  let date: Date | null = null;
  if (Number.isFinite(numericTimestamp) && numericTimestamp >= 1_000_000_000_000) {
    date = new Date(numericTimestamp);
  } else if (Number.isFinite(numericTimestamp) && numericTimestamp >= 1_000_000_000) {
    date = new Date(numericTimestamp * 1000);
  } else if (/^\d{4}-\d{2}-\d{2}[T\s]/.test(text)) {
    date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(text) ? text : `${text}Z`);
  }

  return date && !Number.isNaN(date.getTime())
    ? date.toLocaleTimeString("zh-CN", { hour: "2-digit", hour12: false, minute: "2-digit", second: "2-digit" })
    : text;
}

function formatTrendValue(value: unknown, name: string) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return "不可用";
  return name === "RPS" ? `${numericValue.toFixed(2)} RPS` : `${numericValue.toFixed(2)} ms`;
}

function numberValue(value?: number) {
  return Math.round(value ?? 0).toLocaleString("zh-CN");
}
function decimalValue(value?: number) {
  return (value ?? 0).toFixed(2);
}
function percentageValue(value?: number) {
  return ((value ?? 0) * 100).toFixed(2);
}
function nullableValue(value?: number | null) {
  return value === null || value === undefined ? "不可用" : value.toFixed(2);
}

function millisecondsValue(value?: number | null) {
  return value === null || value === undefined ? "不可用" : `${value.toFixed(2)} ms`;
}
