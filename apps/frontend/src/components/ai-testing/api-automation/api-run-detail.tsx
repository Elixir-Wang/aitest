"use client";

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { Bot, ChevronLeft, Copy, FileJson, Loader2, Play, RefreshCw } from "lucide-react";
import { toast } from "@/lib/toast";

import { ApiRepairDrawer } from "@/components/ai-testing/api-automation/api-repair-drawer";
import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type ApiAutomationRun,
  createApiAutomationRun,
  formatDateTime,
  getApiAutomationRun,
  getApiAutomationRunLogs,
  getApiAutomationRunReport,
} from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

const ACTIVE_STATUSES = new Set(["queued", "running"]);

export function ApiRunDetail({ projectId, runId }: { projectId: string; runId: string }) {
  const [run, setRun] = useState<ApiAutomationRun | null>(null);
  const [logs, setLogs] = useState({ stdout: "", stderr: "" });
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);
  const [repairOpen, setRepairOpen] = useState(false);
  const [rerunLoading, setRerunLoading] = useState(false);

  const loadDetail = useCallback(
    async (showLoading = true) => {
      if (showLoading) setLoading(true);
      try {
        const nextRun = await getApiAutomationRun(projectId, runId);
        setRun(nextRun);
        try {
          setLogs(await getApiAutomationRunLogs(projectId, runId));
        } catch {
          setLogs({ stdout: "", stderr: "" });
        }
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "运行详情加载失败");
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [projectId, runId],
  );

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const runStatus = run?.status;
  useEffect(() => {
    if (!ACTIVE_STATUSES.has(runStatus ?? "")) return;
    const timer = window.setInterval(() => void loadDetail(false), 3000);
    return () => window.clearInterval(timer);
  }, [loadDetail, runStatus]);

  async function loadReport() {
    setReportLoading(true);
    try {
      setReport(await getApiAutomationRunReport(projectId, runId));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "JSON 报告加载失败");
    } finally {
      setReportLoading(false);
    }
  }

  async function openReport() {
    setReportOpen(true);
    if (!report) await loadReport();
  }

  async function copyReport() {
    if (!report) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      toast.success("JSON 报告已复制");
    } catch {
      toast.error("JSON 报告复制失败");
    }
  }

  async function rerun() {
    if (!run || ACTIVE_STATUSES.has(run.status) || !run.api_environment_id || run.target_type === "scenario") return;
    setRerunLoading(true);
    try {
      const created = await createApiAutomationRun(projectId, {
        script_ids: run.script_ids,
        api_environment_id: run.api_environment_id,
      });
      toast.success("执行任务已重新创建");
      window.location.assign(`/projects/${projectId}/automation/api/runs/${created.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "重新执行失败");
    } finally {
      setRerunLoading(false);
    }
  }

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs(
        "apiAutomation",
        { label: "接口自动化", href: `/projects/${projectId}/automation/api?tab=runs` },
        { label: "运行详情" },
      )}
      description="查看一次接口自动化运行的执行环境、结果、日志和 JSON 报告。"
      projectScope="project"
      title="接口自动化运行详情"
    >
      <ShellSection className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b pb-5">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-semibold text-2xl tracking-tight">运行详情</h1>
              {run ? (
                <Badge className={runStatusTone(run.status)} variant="outline">
                  {runStatusLabel(run.status)}
                </Badge>
              ) : null}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <Button asChild variant="outline">
              <Link href={`/projects/${projectId}/automation/api?tab=runs`}>
                <ChevronLeft className="size-4" />
                返回
              </Link>
            </Button>
            <Button aria-label="刷新运行详情" disabled={loading} onClick={() => void loadDetail()} variant="outline">
              {loading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
              刷新
            </Button>
            <Button
              disabled={
                run
                  ? rerunLoading ||
                    ACTIVE_STATUSES.has(run.status) ||
                    !run.api_environment_id ||
                    run.target_type === "scenario"
                  : true
              }
              onClick={() => void rerun()}
              variant="outline"
            >
              <Play className={cn("size-4", rerunLoading && "animate-pulse")} />
              重新执行
            </Button>
            {run?.json_report_path ? (
              <Button onClick={() => void openReport()} variant="outline">
                <FileJson className="size-4" />
                查看 JSON 报告
              </Button>
            ) : null}
            {run?.status === "failed" && run.target_type === "scripts" ? (
              <Button onClick={() => setRepairOpen(true)}>
                <Bot className="size-4" />
                AI 分析与修复
              </Button>
            ) : null}
          </div>
        </div>

        {loading && !run ? (
          <div className="flex min-h-52 items-center justify-center text-muted-foreground text-sm">
            <Loader2 className="mr-2 size-4 animate-spin" />
            加载中
          </div>
        ) : null}
        {run ? (
          <>
            <div className="grid gap-x-6 gap-y-5 border-b pb-5 sm:grid-cols-2 lg:grid-cols-4">
              <RunDetailValue label="开始时间" value={formatDateTime(run.created_at)} />
              <RunDetailValue label="执行环境" value={run.execution_snapshot.environment?.name ?? "已删除环境"} />
              <RunDetailValue label="执行结果" value={runResultLabel(run)} />
              <RunDetailValue label="耗时" value={runDurationLabel(run)} />
              <RunDetailValue
                label="脚本 / 用例"
                value={`${run.execution_snapshot.script_count ?? run.script_ids.length} / ${run.execution_snapshot.case_count ?? 0}`}
              />
              <RunDetailValue label="Base URL" mono value={run.execution_snapshot.environment?.api_base_url ?? "-"} />
              <RunDetailValue label="命令" mono value={run.command_summary || "-"} />
            </div>

            {run.target_type === "scenario" ? (
              <div className="grid gap-3 rounded-md border p-4 sm:grid-cols-3">
                <RunDetailValue label="场景" value={run.execution_snapshot.scenario?.name ?? "已删除场景"} />
                <RunDetailValue label="发布版本" value={`v${run.execution_snapshot.scenario?.revision ?? "-"}`} />
                <RunDetailValue label="步骤数" value={`${run.execution_snapshot.scenario?.step_count ?? 0} 个`} />
              </div>
            ) : (
              <div>
                <div className="mb-2 font-semibold text-sm">执行脚本</div>
                <div className="overflow-hidden rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>接口信息</TableHead>
                        <TableHead>脚本</TableHead>
                        <TableHead className="text-right">用例数</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(run.execution_snapshot.scripts ?? []).map((script) => (
                        <TableRow key={script.id}>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              {script.method ? <MethodBadge method={script.method} /> : null}
                              <span className="max-w-80 truncate">{script.endpoint_summary || script.path || "-"}</span>
                            </div>
                          </TableCell>
                          <TableCell className="font-mono text-xs">{script.name}</TableCell>
                          <TableCell className="text-right tabular-nums">{script.case_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )}

            {run.error_message ? (
              <div>
                <div className="mb-2 font-semibold text-red-700 text-sm dark:text-red-300">失败原因</div>
                <pre className="overflow-auto whitespace-pre-wrap rounded-md border border-red-200 bg-red-50 p-3 text-xs dark:border-red-900 dark:bg-red-950/30">
                  {run.error_message}
                </pre>
              </div>
            ) : null}

            <div>
              <div className="mb-2 font-semibold text-sm">运行日志</div>
              <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-md bg-zinc-950 p-4 font-mono text-xs text-zinc-100 leading-5">
                {logs.stdout ||
                  logs.stderr ||
                  (ACTIVE_STATUSES.has(run.status) ? "任务执行中，日志将在完成后显示。" : "暂无运行日志。")}
              </pre>
            </div>
          </>
        ) : null}
      </ShellSection>

      {run?.status === "failed" && run.target_type === "scripts" ? (
        <ApiRepairDrawer
          onOpenChange={setRepairOpen}
          onRunChanged={() => void loadDetail(false)}
          open={repairOpen}
          projectId={projectId}
          run={run}
        />
      ) : null}

      <Dialog onOpenChange={setReportOpen} open={reportOpen}>
        <DialogContent className="grid h-[min(52rem,calc(100vh-2rem))] w-[calc(100vw-2rem)] max-w-none grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0 sm:max-w-6xl">
          <DialogHeader className="border-b px-5 py-4 pr-14">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <DialogTitle>JSON 报告</DialogTitle>
                <DialogDescription className="mt-1 truncate font-mono text-xs">运行 ID：{runId}</DialogDescription>
              </div>
              <Button disabled={!report} onClick={() => void copyReport()} size="sm" variant="outline">
                <Copy className="size-4" />
                复制 JSON
              </Button>
            </div>
          </DialogHeader>
          <div className="min-h-0 min-w-0 overflow-hidden bg-zinc-950">
            {reportLoading ? (
              <div className="flex h-full items-center justify-center text-sm text-zinc-400">
                <Loader2 className="mr-2 size-4 animate-spin" />
                JSON 报告加载中
              </div>
            ) : report ? (
              <pre className="h-full max-w-full overflow-auto whitespace-pre p-5 font-mono text-xs text-zinc-100 leading-5">
                {JSON.stringify(report, null, 2)}
              </pre>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-zinc-400">暂无 JSON 报告内容</div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}

function RunDetailValue({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className={cn("mt-1 truncate font-medium text-sm", mono && "font-mono text-xs")} title={value}>
        {value}
      </div>
    </div>
  );
}

function MethodBadge({ method }: { method: string }) {
  return (
    <Badge
      className="border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200"
      variant="outline"
    >
      {method.toUpperCase()}
    </Badge>
  );
}

function runStatusLabel(status: string) {
  return (
    (
      {
        queued: "排队中",
        running: "执行中",
        passed: "通过",
        failed: "失败",
        observed: "通过",
        cancelled: "已取消",
        interrupted: "已中断",
      } as Record<string, string>
    )[status] ?? status
  );
}

function runStatusTone(status: string) {
  return (
    (
      {
        queued:
          "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200",
        running: "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-200",
        passed:
          "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200",
        observed:
          "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200",
        failed: "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200",
        cancelled: "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300",
        interrupted:
          "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200",
      } as Record<string, string>
    )[status] ?? ""
  );
}

function runSummaryNumber(run: ApiAutomationRun, key: string) {
  const value = run.summary[key];
  return typeof value === "number" ? value : Number(value) || 0;
}

function runResultLabel(run: ApiAutomationRun) {
  if (ACTIVE_STATUSES.has(run.status)) return "-";
  const total = runSummaryNumber(run, "total");
  return total > 0
    ? `${runSummaryNumber(run, "passed")} 通过 / ${runSummaryNumber(run, "failed")} 失败 / ${runSummaryNumber(run, "skipped")} 跳过 / ${total} 总计`
    : "-";
}

function runDurationLabel(run: ApiAutomationRun) {
  const duration = runSummaryNumber(run, "duration");
  if (duration > 0) return `${duration.toFixed(duration >= 10 ? 1 : 2)} 秒`;
  if (!run.finished_at) return ACTIVE_STATUSES.has(run.status) ? "进行中" : "-";
  const normalize = (value: string) => (value.includes("T") ? value : `${value.replace(" ", "T")}Z`);
  const durationMs = Date.parse(normalize(run.finished_at)) - Date.parse(normalize(run.created_at));
  return Number.isFinite(durationMs) && durationMs >= 0 ? `${(durationMs / 1000).toFixed(1)} 秒` : "-";
}
