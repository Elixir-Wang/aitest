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
import { getPerformanceAnalysis, type PerformanceAnalysis } from "@/lib/api-client";

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
  const validity = metric.test_validity ?? {};
  const stageAnalysis = metric.stage_analysis ?? [];
  const capacityAnalysis = metric.capacity_analysis ?? {};
  const failureAnalysis = metric.failure_analysis ?? [];
  const verdict = report.verdict ?? metric.verdict ?? "indeterminate";
  const series = (metric.series ?? []).map((item, index) => ({ index: index + 1, ...item }));

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
        <Button
          onClick={() => router.push(`/projects/${projectId}/performance-tests/${testId}/runs/${runId}`)}
          variant="ghost"
        >
          <ArrowLeft className="size-4" />
          返回 Locust 控制台
        </Button>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge variant="outline">分析 v{analysis.analysis_version}</Badge>
          <Badge variant="outline">指标 v{metric.schema_version ?? 1}</Badge>
          {analysis.model_name ? <Badge variant="secondary">{analysis.model_name}</Badge> : null}
        </div>
      </div>

      <section className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(18rem,0.65fr)]">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <VerdictIcon verdict={verdict} />
            <div>
              <p className="text-muted-foreground text-sm">性能目标结论</p>
              <h2 className="mt-1 font-semibold text-2xl">{verdictLabel(verdict)}</h2>
            </div>
          </div>
          <p className="mt-5 max-w-3xl text-muted-foreground text-sm leading-7">
            {report.executive_summary || "当前报告没有可用的执行摘要。"}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium text-sm">数据质量</span>
            <Badge variant={quality.status === "complete" ? "secondary" : "outline"}>
              {qualityLabel(quality.status)}
            </Badge>
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full bg-primary" style={{ width: `${Math.round((quality.coverage ?? 0) * 100)}%` }} />
          </div>
          <p className="mt-2 text-muted-foreground text-xs">
            证据覆盖 {Math.round((quality.coverage ?? 0) * 100)}% · {quality.sample_count ?? 0} 个时序样本
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
              {(metric.objectives ?? []).map((objective) => (
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
              {(metric.objectives ?? []).length === 0 ? (
                <tr>
                  <td className="px-4 py-5 text-center text-muted-foreground" colSpan={4}>
                    当前运行没有可评估的性能目标。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]">
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
                {!stageAnalysis.length ? (
                  <tr>
                    <td className="px-4 py-5 text-center text-muted-foreground" colSpan={6}>
                      没有可用的阶段采样。
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
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
                {capacityAnalysis.knee_point ? (
                  <p className="mt-4 border-t pt-3 text-muted-foreground text-xs">
                    拐点区间：{capacityAnalysis.knee_point.between_users?.join(" ~ ")} 并发
                  </p>
                ) : null}
              </>
            ) : (
              <p className="text-muted-foreground">{capacityAnalysis.reason || "当前证据不足以判断稳定容量。"}</p>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.7fr)]">
        <div className="space-y-4">
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
            {!failureAnalysis.length ? (
              <p className="p-4 text-muted-foreground text-sm">没有记录到失败或异常分类。</p>
            ) : null}
          </div>
        </div>
        <div className="space-y-4">
          <SectionHeading icon={ShieldCheck} title="测试有效性" />
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium text-sm">{qualityLabel(validity.status)}</span>
              <Badge variant={validity.status === "complete" ? "secondary" : "outline"}>
                {validity.sample_count ?? 0} 个样本
              </Badge>
            </div>
            {(validity.issues ?? []).length ? (
              <p className="mt-3 text-muted-foreground text-xs leading-5">
                {validity.issues?.map(validityIssueLabel).join("；")}
              </p>
            ) : (
              <p className="mt-3 text-muted-foreground text-xs">当前没有发现明显的数据完整性问题。</p>
            )}
          </div>
        </div>
      </section>

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
          <p className="text-muted-foreground text-sm">{report.capacity_summary}</p>
        </section>
      ) : null}

      <section className="space-y-4">
        <SectionHeading icon={CircleHelp} title="诊断发现" />
        {(report.findings ?? []).length ? (
          <div className="divide-y rounded-lg border">
            {(report.findings ?? []).map((finding) => (
              <article className="p-4 sm:p-5" key={finding.id}>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    variant={finding.severity === "high" || finding.severity === "critical" ? "destructive" : "outline"}
                  >
                    {finding.severity.toUpperCase()}
                  </Badge>
                  <Badge variant="secondary">置信度 {Math.round(finding.confidence * 100)}%</Badge>
                  {finding.level ? <Badge variant="outline">{finding.level}</Badge> : null}
                </div>
                <h3 className="mt-3 font-semibold">{finding.title}</h3>
                <p className="mt-2 whitespace-pre-wrap text-muted-foreground text-sm leading-6">{finding.statement}</p>
                {finding.missing_evidence?.length ? (
                  <p className="mt-3 text-muted-foreground text-xs">缺失证据：{finding.missing_evidence.join("、")}</p>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">没有生成可验证的诊断 finding。</p>
        )}
      </section>

      <section className="space-y-4">
        <SectionHeading icon={CheckCircle2} title="优化与复测建议" />
        <div className="divide-y rounded-lg border">
          {(report.recommendations ?? []).map((recommendation) => (
            <div className="grid gap-3 p-4 sm:grid-cols-[4rem_minmax(0,1fr)] sm:p-5" key={recommendation.id}>
              <Badge className="h-fit w-fit" variant="outline">
                {recommendation.priority}
              </Badge>
              <div>
                <p className="font-medium text-sm">{recommendation.action}</p>
                {recommendation.expected_effect ? (
                  <p className="mt-2 text-muted-foreground text-sm">{recommendation.expected_effect}</p>
                ) : null}
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
          {(report.recommendations ?? []).length === 0 ? (
            <p className="p-4 text-muted-foreground text-sm">当前没有可执行或需要跟踪的优化建议。</p>
          ) : null}
        </div>
      </section>

      <section className="border-t pt-5 text-muted-foreground text-xs leading-6">
        <p>
          来源指纹：
          <span className="break-all font-mono">{analysis.source_fingerprint || metric.source_fingerprint || "-"}</span>
        </p>
        <p>
          指标版本：{analysis.calculator_version || metric.calculator_version || "-"} · 提示版本：
          {analysis.prompt_version || "-"} · 生成模型：{analysis.model_name || "-"}
        </p>
        {(quality.issues ?? []).length ? <p>数据限制：{quality.issues?.join("；")}</p> : null}
      </section>
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
