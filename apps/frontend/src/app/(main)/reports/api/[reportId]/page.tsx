"use client";

import { useEffect, useState } from "react";

import { useParams } from "next/navigation";

import { Activity, AlertTriangle, CheckCircle2, CircleHelp, LoaderCircle, XCircle } from "lucide-react";

import { PageShell } from "@/components/ai-testing/page-shell";
import { StatusBadge, type StatusBadgeTone } from "@/components/ui/status-badge";
import { type ApiBatchReportDetail, formatDateTime, getApiBatchReportDetail } from "@/lib/api-client";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  const params = useParams<{ reportId: string }>();
  const reportId = params.reportId;
  const [report, setReport] = useState<ApiBatchReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let disposed = false;
    setLoading(true);
    getApiBatchReportDetail(reportId)
      .then((item) => {
        if (!disposed) setReport(item);
      })
      .catch((requestError) => {
        if (!disposed) setError(requestError instanceof Error ? requestError.message : "接口报告加载失败");
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
    };
  }, [reportId]);

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("reports", { label: report?.name || "接口报告" })}
      description="查看批量运行的确定性汇总和场景执行结果。"
      projectScope="all"
      title={report?.name || "接口批次报告"}
    >
      {loading ? (
        <div className="flex min-h-72 items-center justify-center text-muted-foreground text-sm">
          <LoaderCircle className="mr-2 size-4 animate-spin" />
          接口报告加载中
        </div>
      ) : error || !report ? (
        <div className="flex min-h-72 flex-col items-center justify-center rounded-lg border bg-card px-6 text-center">
          <AlertTriangle className="mb-3 size-6 text-destructive" />
          <h2 className="font-semibold">报告加载失败</h2>
          <p className="mt-2 max-w-lg text-muted-foreground text-sm">{error || "接口报告不存在"}</p>
        </div>
      ) : (
        <div className="mx-auto w-full max-w-[90rem] space-y-7">
          <section
            className={`overflow-hidden rounded-lg border border-l-4 bg-card ${resultAccentClass(report.result)}`}
          >
            <div className="grid xl:grid-cols-[minmax(34rem,1.15fr)_minmax(22rem,0.85fr)]">
              <div className="p-5 sm:p-6 xl:pr-8">
                <p className="text-muted-foreground text-xs">批次结果</p>
                <div className="mt-3 flex items-center gap-2">
                  <ResultGlyph result={report.result} />
                  <h1 className="font-semibold text-3xl tabular-nums">{resultLabel(report.result)}</h1>
                </div>
                <p className="mt-2 max-w-xl text-muted-foreground text-sm leading-6">{resultSummary(report)}</p>

                <div className="mt-5 border-t pt-4">
                  <h2 className="font-medium text-muted-foreground text-xs" id="batch-metrics-heading">
                    核心指标
                  </h2>
                  <section
                    aria-labelledby="batch-metrics-heading"
                    className="mt-5 grid grid-cols-2 gap-x-6 gap-y-6 sm:grid-cols-4"
                  >
                    <ReportMetric label="场景总数" value={String(report.counts.total)} />
                    <ReportMetric label="通过" value={String(report.counts.passed)} />
                    <ReportMetric label="失败/异常" value={String(report.counts.failed + report.counts.error)} />
                    <ReportMetric label="通过率" value={formatPercent(report.pass_rate)} />
                  </section>
                </div>
              </div>

              <div className="border-t bg-muted/20 p-5 sm:p-6 xl:border-t-0 xl:border-l xl:pl-8">
                <section aria-labelledby="run-context-heading" className="flex h-full flex-col justify-center">
                  <div className="flex items-center gap-2 text-muted-foreground text-xs">
                    <Activity className="size-3.5" />
                    <h2 className="font-medium" id="run-context-heading">
                      运行信息
                    </h2>
                  </div>
                  <dl className="mt-4 grid grid-cols-2 gap-x-8">
                    <ContextItem label="项目" value={report.project_name} />
                    <ContextItem label="运行环境" value={report.environment.name} />
                    <ContextItem label="接口地址" value={report.environment.api_base_url || "未配置"} />
                    <ContextItem label="完成时间" value={formatDateTime(report.finished_at || report.created_at)} />
                  </dl>
                </section>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <div className="flex items-center gap-2">
              <Activity className="size-4 text-muted-foreground" />
              <h2 className="font-semibold text-base">场景结果</h2>
            </div>
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full min-w-[52rem] text-sm">
                <thead className="bg-muted/50 text-left text-muted-foreground text-xs">
                  <tr>
                    <th className="px-4 py-3 font-medium">场景名称</th>
                    <th className="px-4 py-3 font-medium">步骤数</th>
                    <th className="px-4 py-3 font-medium">结果</th>
                    <th className="px-4 py-3 font-medium">错误摘要</th>
                    <th className="px-4 py-3 font-medium">完成时间</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {report.runs.map((run) => (
                    <tr key={run.id}>
                      <td className="px-4 py-3 font-medium">{run.scenario_name}</td>
                      <td className="px-4 py-3 tabular-nums">{run.step_count}</td>
                      <td className="px-4 py-3">
                        <StatusBadge tone={runTone(run.status)}>{runStatusLabel(run.status)}</StatusBadge>
                      </td>
                      <td className="max-w-md truncate px-4 py-3 text-muted-foreground" title={run.error_message}>
                        {run.error_message || "-"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-muted-foreground tabular-nums">
                        {formatDateTime(run.finished_at || run.created_at)}
                      </td>
                    </tr>
                  ))}
                  {report.runs.length === 0 ? (
                    <tr>
                      <td className="px-4 py-10 text-center text-muted-foreground" colSpan={5}>
                        本批次暂无场景运行记录
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </PageShell>
  );
}

function ReportMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-1 font-semibold text-2xl tabular-nums">{value}</p>
    </div>
  );
}

function ContextItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-t py-3">
      <dt className="text-[11px] text-muted-foreground">{label}</dt>
      <dd className="mt-1 truncate font-medium text-sm tabular-nums" title={value}>
        {value}
      </dd>
    </div>
  );
}

function ResultGlyph({ result }: { result: ApiBatchReportDetail["result"] }) {
  if (result === "passed") return <CheckCircle2 className="size-6 shrink-0 text-emerald-600" />;
  if (result === "observed") return <CircleHelp className="size-6 shrink-0 text-amber-600" />;
  if (result === "failed") return <XCircle className="size-6 shrink-0 text-red-600" />;
  return <AlertTriangle className="size-6 shrink-0 text-red-600" />;
}

function resultAccentClass(result: ApiBatchReportDetail["result"]) {
  if (result === "passed") return "border-l-emerald-500";
  if (result === "observed") return "border-l-amber-500";
  return "border-l-red-500";
}

function resultSummary(report: ApiBatchReportDetail) {
  if (report.result === "passed") return `本批次 ${report.counts.total} 个场景全部通过，未发现失败或执行异常。`;
  if (report.result === "observed")
    return `本批次有 ${report.counts.observed} 个场景需要确认，请结合场景结果核对观测项。`;
  if (report.result === "failed") return `本批次有 ${report.counts.failed} 个场景失败，请优先检查错误摘要。`;
  return `本批次有 ${report.counts.error} 个场景执行异常，请检查运行环境与错误摘要。`;
}

function formatPercent(value: number) {
  return new Intl.NumberFormat("zh-CN", { style: "percent", maximumFractionDigits: 1 }).format(value);
}

function resultLabel(result: ApiBatchReportDetail["result"]) {
  if (result === "passed") return "通过";
  if (result === "observed") return "待确认";
  if (result === "failed") return "失败";
  return "异常";
}

function runStatusLabel(status: string) {
  if (status === "passed") return "通过";
  if (status === "observed") return "待确认";
  if (status === "failed") return "失败";
  if (status === "queued") return "排队中";
  if (status === "running") return "运行中";
  return "异常";
}

function runTone(status: string): StatusBadgeTone {
  if (status === "passed") return "success";
  if (status === "observed") return "warning";
  if (status === "queued" || status === "running") return "processing";
  return "destructive";
}
