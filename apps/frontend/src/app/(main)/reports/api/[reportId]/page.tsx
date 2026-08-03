"use client";

import { useEffect, useState } from "react";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ArrowLeft, Loader2 } from "lucide-react";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";
import { StatusBadge, type StatusBadgeTone } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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
      actions={
        <Button asChild variant="outline">
          <Link href="/reports">
            <ArrowLeft className="size-4" />
            返回报告中心
          </Link>
        </Button>
      }
      breadcrumbs={moduleBreadcrumbs("reports", { label: report?.name || "接口报告" })}
      description="查看批量运行的确定性汇总和场景执行结果。"
      projectScope="all"
      title={report?.name || "接口批次报告"}
    >
      {loading ? (
        <ShellSection className="flex min-h-64 items-center justify-center text-muted-foreground">
          <Loader2 className="mr-2 size-5 animate-spin" />
          接口报告加载中
        </ShellSection>
      ) : error || !report ? (
        <ShellSection className="flex min-h-64 items-center justify-center text-destructive">
          {error || "接口报告不存在"}
        </ShellSection>
      ) : (
        <>
          <ShellSection>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <ReportMetric label="批次结果" value={resultLabel(report.result)} />
              <ReportMetric label="场景总数" value={String(report.counts.total)} />
              <ReportMetric label="通过" value={String(report.counts.passed)} />
              <ReportMetric label="失败/异常" value={String(report.counts.failed + report.counts.error)} />
              <ReportMetric label="通过率" value={formatPercent(report.pass_rate)} />
            </div>
            <div className="mt-4 grid gap-3 border-t pt-4 text-sm md:grid-cols-3">
              <div>
                <p className="text-muted-foreground text-xs">项目</p>
                <p className="mt-1 font-medium">{report.project_name}</p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs">运行环境</p>
                <p className="mt-1 font-medium">{report.environment.name}</p>
                <p className="truncate text-muted-foreground text-xs" title={report.environment.api_base_url}>
                  {report.environment.api_base_url}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs">完成时间</p>
                <p className="mt-1 font-medium">{formatDateTime(report.finished_at || report.created_at)}</p>
              </div>
            </div>
          </ShellSection>

          <ShellSection>
            <div className="mb-4">
              <h2 className="font-medium text-sm">场景结果</h2>
              <p className="text-muted-foreground text-xs">每一行对应本批次中的一条接口场景运行记录。</p>
            </div>
            <div className="overflow-hidden rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>场景名称</TableHead>
                    <TableHead>步骤数</TableHead>
                    <TableHead>结果</TableHead>
                    <TableHead>错误摘要</TableHead>
                    <TableHead>完成时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.runs.map((run) => (
                    <TableRow key={run.id}>
                      <TableCell className="font-medium">{run.scenario_name}</TableCell>
                      <TableCell>{run.step_count}</TableCell>
                      <TableCell>
                        <StatusBadge tone={runTone(run.status)}>{runStatusLabel(run.status)}</StatusBadge>
                      </TableCell>
                      <TableCell className="max-w-md truncate text-muted-foreground" title={run.error_message}>
                        {run.error_message || "-"}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">
                        {formatDateTime(run.finished_at || run.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </ShellSection>
        </>
      )}
    </PageShell>
  );
}

function ReportMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/20 p-4">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-2 font-semibold text-2xl tracking-tight">{value}</p>
    </div>
  );
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
