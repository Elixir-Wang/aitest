"use client";

import { useCallback, useEffect, useState } from "react";

import { useRouter } from "next/navigation";

import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Gauge,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { createPerformanceAnalysis, getPerformanceAnalysis, type PerformanceAnalysis } from "@/lib/api-client";

const ACTIVE_ANALYSIS = new Set(["collecting", "analyzing"]);

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
  const objectives = metric.objectives ?? [];
  const stageAnalysis = metric.stage_analysis ?? [];
  const capacityAnalysis = metric.capacity_analysis ?? {};
  const failureAnalysis = metric.failure_analysis ?? [];
  const findings = report.findings ?? [];
  const recommendations = (report.recommendations ?? []).slice(0, 3);
  const verdict = report.verdict ?? metric.verdict ?? "indeterminate";
  const series = (metric.series ?? []).map((item, index) => ({ index: index + 1, ...item }));
  const isFallback = analysis.generation_mode === "deterministic_fallback";
  const showCapacityAnalysis =
    stageAnalysis.length > 1 && Boolean(capacityAnalysis.observed_stable_capacity || capacityAnalysis.knee_point);
  const evidenceGaps = Array.from(
    new Set([
      ...(quality.issues ?? []).map(validityIssueLabel),
      ...(quality.diagnostic_missing_evidence ?? []),
      ...findings.flatMap((finding) => finding.missing_evidence ?? []),
    ]),
  );

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
    <div className="space-y-8">
      <div className="border-b pb-4">
        <Button
          onClick={() => router.push(`/projects/${projectId}/performance-tests/${testId}/runs/${runId}`)}
          variant="ghost"
        >
          <ArrowLeft className="size-4" />
          返回 Locust 控制台
        </Button>
      </div>

      {isFallback ? (
        <section className="flex flex-col gap-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-950 sm:flex-row sm:items-center sm:justify-between dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
          <div>
            <p className="font-medium text-sm">当前为基础性能报告</p>
            <p className="mt-1 text-sm opacity-80">压测指标和目标结论完整；AI 根因分析及修复建议未生成。</p>
          </div>
          <Button disabled={reanalyzing} onClick={() => void reanalyze()} variant="outline">
            {reanalyzing ? <LoaderCircle className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            重新分析
          </Button>
        </section>
      ) : null}

      <section className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(18rem,0.65fr)]">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <VerdictIcon verdict={verdict} />
            <div>
              <p className="text-muted-foreground text-sm">性能目标结论</p>
              <h2 className="mt-1 font-semibold text-2xl">{verdictLabel(verdict)}</h2>
            </div>
          </div>
          <p className="mt-4 max-w-2xl text-muted-foreground text-sm leading-6">
            {objectives.length
              ? "结论依据已配置的性能目标和本次运行指标生成。"
              : "未配置性能目标，当前结果仅用于观测，不作通过或失败判定。"}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium text-sm">数据质量</span>
            <Badge variant={quality.status === "complete" ? "secondary" : "outline"}>
              {qualityLabel(quality.status)}
            </Badge>
          </div>
          <p className="mt-3 text-muted-foreground text-xs leading-5">
            {(quality.issues ?? []).length
              ? `${quality.issues?.length} 项数据限制，详见报告末尾。`
              : "未发现影响基础指标计算的问题。"}
          </p>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <ReportMetric icon={Activity} label="请求总数" value={numberValue(aggregate.request_count)} />
        <ReportMetric icon={Gauge} label="观测吞吐" suffix=" RPS" value={decimalValue(aggregate.requests_per_second)} />
        <ReportMetric icon={AlertTriangle} label="失败率" suffix="%" value={percentageValue(aggregate.failure_rate)} />
        <ReportMetric
          icon={Clock3}
          label="P95 响应时间"
          suffix=" ms"
          value={nullableValue(aggregate.p95_response_time_ms)}
        />
      </section>

      {objectives.length ? (
        <section className="space-y-4">
        <SectionHeading icon={ShieldCheck} title="性能目标" />
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
        </section>
      ) : null}

      {stageAnalysis.length > 1 ? (
        <section
          className={showCapacityAnalysis ? "grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]" : "space-y-4"}
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

      {failureAnalysis.length ? (
        <section className="space-y-4">
          <SectionHeading icon={AlertTriangle} title="失败分类" />
          <div className="divide-y rounded-lg border">
            {failureAnalysis.map((failure) => (
              <div className="grid gap-2 p-4 sm:grid-cols-[10rem_minmax(0,1fr)]" key={failure.kind}>
                <div className="flex items-center justify-between gap-3 sm:block">
                  <p className="font-medium text-sm">{failureKindLabel(failure.kind)}</p>
                  <p className="mt-1 text-muted-foreground text-xs">
                    {failure.count} 次 · {percentageValue(failure.ratio)}
                  </p>
                </div>
                <p className="text-muted-foreground text-sm">{failure.example || "未记录示例原因"}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {series.length ? (
        <section className="space-y-4">
          <SectionHeading icon={TrendingUp} title="运行趋势" />
          <div className="h-[22rem] rounded-lg border bg-card p-4">
            <ResponsiveContainer height="100%" width="100%">
              <LineChart data={series} margin={{ bottom: 4, left: 0, right: 12, top: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="index" tickLine={false} />
                <YAxis tickLine={false} yAxisId="left" />
                <YAxis orientation="right" tickLine={false} yAxisId="right" />
                <Tooltip />
                <Legend />
                <Line
                  dataKey="requests_per_second"
                  dot={false}
                  name="RPS"
                  stroke="var(--chart-1)"
                  strokeWidth={2}
                  yAxisId="left"
                />
                <Line
                  dataKey="p95_response_time_ms"
                  dot={false}
                  name="P95 ms"
                  stroke="var(--chart-2)"
                  strokeWidth={2}
                  yAxisId="right"
                />
                <Line
                  dataKey="p99_response_time_ms"
                  dot={false}
                  name="P99 ms"
                  stroke="var(--chart-3)"
                  strokeWidth={2}
                  yAxisId="right"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}

      {!isFallback ? (
        <>
          {findings.length ? (
            <section className="space-y-4">
              <SectionHeading icon={CircleHelp} title="诊断发现" />
              <div className="divide-y rounded-lg border">
                {findings.map((finding) => (
                  <article className="p-4 sm:p-5" key={finding.id}>
                    <Badge
                      variant={
                        finding.severity === "high" || finding.severity === "critical" ? "destructive" : "outline"
                      }
                    >
                      {finding.severity.toUpperCase()}
                    </Badge>
                    <h3 className="mt-3 font-semibold">{finding.title}</h3>
                    <p className="mt-2 whitespace-pre-wrap text-muted-foreground text-sm leading-6">{finding.statement}</p>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {recommendations.length ? (
            <section className="space-y-4">
              <SectionHeading icon={CheckCircle2} title="优化与复测建议" />
              <div className="divide-y rounded-lg border">
                {recommendations.map((recommendation) => (
                  <div
                    className="grid gap-3 p-4 sm:grid-cols-[4rem_minmax(0,1fr)] sm:p-5"
                    key={recommendation.id}
                  >
                    <Badge className="h-fit w-fit" variant="outline">
                      {recommendation.priority}
                    </Badge>
                    <div>
                      <p className="font-medium text-sm">{recommendation.action}</p>
                      {recommendation.verification ? (
                        <p className="mt-2 text-muted-foreground text-xs">验证：{recommendation.verification}</p>
                      ) : null}
                      {recommendation.acceptance_criteria?.length ? (
                        <p className="mt-2 text-muted-foreground text-xs">
                          验收：{recommendation.acceptance_criteria.join("；")}
                        </p>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </>
      ) : null}

      {evidenceGaps.length ? (
        <section className="space-y-4">
          <SectionHeading icon={ShieldCheck} title="数据限制" />
          <ul className="space-y-2 rounded-lg border bg-card p-4 text-muted-foreground text-sm">
            {evidenceGaps.map((gap) => (
              <li key={gap}>• {gap}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <details className="border-t pt-5 text-muted-foreground text-xs leading-6">
        <summary className="cursor-pointer select-none font-medium">生成信息</summary>
        <div className="mt-3 space-y-1">
          <p>
            来源指纹：
            <span className="break-all font-mono">{analysis.source_fingerprint || metric.source_fingerprint || "-"}</span>
          </p>
          <p>
            指标版本：{analysis.calculator_version || metric.calculator_version || "-"} · 提示版本：
            {analysis.prompt_version || "-"} · 生成模型：{analysis.model_name || "-"}
          </p>
        </div>
      </details>
    </div>
  );
}

function ReportMetric({
  icon: Icon,
  label,
  value,
  suffix = "",
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  suffix?: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2 text-muted-foreground text-xs">
        <Icon className="size-4" />
        {label}
      </div>
      <p className="mt-3 font-semibold text-xl tabular-nums">
        {value}
        {value === "不可用" ? null : <span className="ml-1 font-normal text-muted-foreground text-xs">{suffix}</span>}
      </p>
    </div>
  );
}

function SectionHeading({ icon: Icon, title }: { icon: typeof Activity; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="size-4 text-muted-foreground" />
      <h2 className="font-semibold text-base">{title}</h2>
    </div>
  );
}

function VerdictIcon({ verdict }: { verdict: string }) {
  const Icon = verdict === "pass" ? CheckCircle2 : verdict === "fail" ? AlertTriangle : CircleHelp;
  return (
    <div className="flex size-11 items-center justify-center rounded-lg border bg-card">
      <Icon className="size-5" />
    </div>
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
  return { complete: "完整", partial: "部分可用", invalid: "无效" }[value ?? ""] ?? "未知";
}

function validityIssueLabel(value: string) {
  return (
    (
      {
        run_manually_stopped: "由测试人员手动停止，实际指标仅覆盖停止前的运行窗口",
        run_terminal_status: "运行未正常完成",
        time_series_missing: "缺少时序采样",
        p95_response_time_missing: "缺少 P95 响应时间",
        too_few_time_series_samples: "时序样本数量偏少",
        load_stage_missing: "缺少负载阶段配置",
        measurement_window_contains_no_requests: "测量窗口内没有请求",
      } as Record<string, string>
    )[value] ?? value
  );
}

function metricLabel(value: string) {
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
  if (metric.includes("response_time")) return `${value.toFixed(2)} ms`;
  if (metric === "requests_per_second") return `${value.toFixed(2)} RPS`;
  return value.toFixed(2);
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
