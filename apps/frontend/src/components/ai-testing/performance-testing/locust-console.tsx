"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Image from "next/image";
import { useRouter } from "next/navigation";

import {
  Activity,
  Bot,
  ChartNoAxesCombined,
  Clock3,
  Download,
  FileClock,
  FileText,
  Gauge,
  LayoutDashboard,
  RotateCcw,
  ShieldAlert,
  ShieldX,
  Square,
  Users,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ApiRequestError,
  createPerformanceRun,
  deletePerformanceRun,
  downloadPerformanceRunReport,
  getPerformanceRun,
  getPerformanceRunCharts,
  getPerformanceRunStats,
  listPerformanceRunHistory,
  listPerformanceRunReports,
  type PerformanceRun,
  type PerformanceRunHistory,
  type PerformanceRunReports,
  type PerformanceRunStartPayload,
  type PerformanceRunStats,
  resetPerformanceRunStats,
  startPerformanceRun,
  stopPerformanceRun,
  streamPerformanceRun,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

import { type LocustChartSample, LocustChartsPanel } from "./locust-charts-panel";
import { LocustGenericTable, LocustStatisticsTable } from "./locust-statistics-table";
import { PerformanceAiAnalysisDrawer } from "./performance-ai-analysis-drawer";

const TERMINAL_STATUSES = new Set<PerformanceRun["status"]>(["completed", "stopped", "failed", "cancelled"]);
const DELETABLE_STATUSES = new Set<PerformanceRun["status"]>([
  "created",
  "completed",
  "stopped",
  "failed",
  "cancelled",
]);

export function LocustConsole({ projectId, testId, runId }: { projectId: string; testId: string; runId: string }) {
  const router = useRouter();
  const [run, setRun] = useState<PerformanceRun | null>(null);
  const [snapshot, setSnapshot] = useState<PerformanceRunStats | null>(null);
  const [reports, setReports] = useState<PerformanceRunReports | null>(null);
  const [samples, setSamples] = useState<LocustChartSample[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<PerformanceRunHistory | null>(null);
  const [deletingRunId, setDeletingRunId] = useState("");
  const runRef = useRef<PerformanceRun | null>(null);

  const refresh = useCallback(async () => {
    const [nextRun, nextSnapshot, nextCharts, nextReports] = await Promise.all([
      getPerformanceRun(projectId, runId),
      getPerformanceRunStats(projectId, runId),
      getPerformanceRunCharts(projectId, runId),
      listPerformanceRunReports(projectId, runId),
    ]);
    runRef.current = nextRun;
    setRun(nextRun);
    setSnapshot(nextSnapshot);
    setReports(nextReports);
    setSamples(chartSamples(nextCharts.samples));
  }, [projectId, runId]);

  useEffect(() => {
    let disposed = false;
    let fallbackTimer: number | undefined;
    const controller = new AbortController();
    const refreshSilently = () => refresh().catch(() => undefined);
    const updateRun = (nextRun: PerformanceRun) => {
      runRef.current = nextRun;
      setRun(nextRun);
    };
    const handleStreamEvent = (event: string, payload: Record<string, unknown>) => {
      if (event === "run") {
        updateRun(payload as PerformanceRun);
        return;
      }
      if (event === "done") {
        void refreshSilently();
        return;
      }
      if (event !== "stats" || !isRecord(payload.latest)) return;
      const latest = payload.latest;
      const nextRun = isRecord(payload.run) ? (payload.run as PerformanceRun) : null;
      if (nextRun) updateRun(nextRun);
      setSnapshot((current) => {
        if (!current) return current;
        return {
          ...current,
          run: nextRun ?? current.run,
          stats: [...current.stats, latest].slice(-180),
          request_stats: Array.isArray(payload.request_stats) ? payload.request_stats : current.request_stats,
          failures: Array.isArray(payload.failures)
            ? (payload.failures as PerformanceRunStats["failures"])
            : current.failures,
          exceptions: Array.isArray(payload.exceptions)
            ? (payload.exceptions as PerformanceRunStats["exceptions"])
            : current.exceptions,
        };
      });
      setSamples((current) => [...current, ...chartSamples([latest])].slice(-180));
    };
    const startPollingFallback = () => {
      if (fallbackTimer !== undefined) return;
      fallbackTimer = window.setInterval(() => {
        if (!disposed && (!runRef.current || !TERMINAL_STATUSES.has(runRef.current.status))) {
          void refreshSilently();
        }
      }, 1000);
    };
    void refresh()
      .catch((error) => !disposed && toast.error(apiErrorMessage(error)))
      .finally(() => {
        if (disposed) return;
        setLoading(false);
        streamPerformanceRun(projectId, runId, controller.signal, handleStreamEvent).catch((error) => {
          if (!disposed && (error as Error)?.name !== "AbortError") startPollingFallback();
        });
      });
    return () => {
      disposed = true;
      controller.abort();
      if (fallbackTimer !== undefined) window.clearInterval(fallbackTimer);
    };
  }, [projectId, refresh, runId]);

  const startDefaults = useMemo<PerformanceRunStartPayload>(() => {
    const config = run?.load_config ?? {};
    return {
      users: Number(config.users ?? 1),
      spawn_rate: Number(config.spawn_rate ?? 1),
      run_time: Number(config.measurement_duration_seconds ?? 60),
    };
  }, [run?.load_config]);

  async function start() {
    setWorking(true);
    try {
      await startPerformanceRun(projectId, testId, runId, startDefaults);
      await refresh();
      toast.success("压测已开始");
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setWorking(false);
    }
  }

  async function stop() {
    setWorking(true);
    try {
      await stopPerformanceRun(projectId, runId);
      await refresh();
      toast.success("压测已停止");
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setWorking(false);
    }
  }

  async function downloadReport(filename: string) {
    try {
      const blob = await downloadPerformanceRunReport(projectId, runId, filename);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(apiErrorMessage(error));
    }
  }

  async function reset() {
    setWorking(true);
    try {
      await resetPerformanceRunStats(projectId, runId);
      setSamples([]);
      await refresh();
      toast.success("统计数据已重置");
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setWorking(false);
    }
  }

  async function rerun() {
    if (!run) return;
    setWorking(true);
    try {
      const nextRun = await createPerformanceRun(projectId, testId, run.script_id);
      await startPerformanceRun(projectId, testId, nextRun.id, startDefaults);
      toast.success("已开始重新压测");
      router.push(`/projects/${projectId}/performance-tests/${testId}/runs/${nextRun.id}`);
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setWorking(false);
    }
  }

  async function openHistory() {
    setHistoryOpen(true);
    try {
      setHistory(await listPerformanceRunHistory(projectId, testId));
    } catch (error) {
      toast.error(apiErrorMessage(error));
    }
  }

  async function deleteHistoryRun(historyRun: PerformanceRun) {
    setDeletingRunId(historyRun.id);
    try {
      await deletePerformanceRun(projectId, historyRun.id);
      const remainingRuns = (history?.runs ?? []).filter((item) => item.id !== historyRun.id);
      setHistory((current) => (current ? { ...current, runs: remainingRuns } : current));
      toast.success("历史记录已删除");
      if (historyRun.id === runId) {
        const nextRun = remainingRuns[0];
        router.replace(
          nextRun
            ? `/projects/${projectId}/performance-tests/${testId}/runs/${nextRun.id}`
            : `/projects/${projectId}/performance-tests`,
        );
      }
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setDeletingRunId("");
    }
  }

  if (loading && !run) {
    return <div className="py-20 text-center text-muted-foreground text-sm">正在加载 Locust 控制台...</div>;
  }

  const aggregate = snapshot?.stats.at(-1) ?? {};
  const canStart = run?.status === "created";
  const canStop = run?.status === "starting" || run?.status === "running";
  const canReset = Boolean(run && !["created", "stopping"].includes(run.status));
  const canRerun = Boolean(run && TERMINAL_STATUSES.has(run.status));
  const canAnalyze = Boolean(run && TERMINAL_STATUSES.has(run.status));

  return (
    <div className="space-y-6">
      <header className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 flex-wrap items-center gap-x-5 gap-y-2 text-slate-500 text-sm dark:text-slate-400">
            <Image alt="Locust" className="h-8 w-12 shrink-0" height={32} src="/brand/locust-mark.svg" width={48} />
            <Badge className={statusBadgeClass(run?.status)} variant="outline">
              {statusText(run?.status)}
            </Badge>
            <span>开始时间：{run?.started_at ? formatRunTime(run.started_at) : "尚未开始"}</span>
            <span>持续时间：{formatRunDuration(run?.started_at, run?.finished_at)}</span>
          </div>
          <div className="flex w-full flex-wrap items-center justify-start gap-2 sm:w-auto sm:justify-end">
            <Button className="h-9 px-3" onClick={() => void openHistory()} size="sm" variant="outline">
              <FileClock className="mr-2 size-3.5" /> 历史记录
            </Button>
            {canStart ? (
              <Button
                className="h-9 flex-1 bg-blue-600 px-4 text-white shadow-sm hover:bg-blue-700 sm:flex-none dark:bg-blue-500 dark:hover:bg-blue-400"
                disabled={working}
                onClick={start}
                size="sm"
              >
                <Activity className="mr-2 size-3.5" /> 开始压测
              </Button>
            ) : null}
            {canStop ? (
              <Button
                className="h-9 flex-1 px-3 sm:flex-none"
                disabled={working}
                onClick={stop}
                size="sm"
                variant="destructive"
              >
                <Square className="mr-2 size-3.5" /> 停止
              </Button>
            ) : null}
            {canRerun ? (
              <Button
                className="h-9 flex-1 px-3 sm:flex-none"
                disabled={working || !canAnalyze}
                onClick={() => setAnalysisOpen(true)}
                size="sm"
                variant="outline"
              >
                <Bot className="mr-2 size-3.5" /> AI 分析
              </Button>
            ) : null}
            {canRerun ? (
              <Button
                className="h-9 flex-1 bg-blue-600 px-4 text-white shadow-sm hover:bg-blue-700 sm:flex-none dark:bg-blue-500 dark:hover:bg-blue-400"
                disabled={working}
                onClick={rerun}
                size="sm"
              >
                <Activity className="mr-2 size-3.5" /> 重新压测
              </Button>
            ) : null}
            <Button
              className="h-9 flex-1 border-slate-200 bg-slate-100/70 px-3 text-slate-700 hover:bg-slate-100 sm:flex-none dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-200 dark:hover:bg-slate-800"
              disabled={!canReset || working}
              onClick={reset}
              size="sm"
              variant="outline"
            >
              <RotateCcw className="mr-2 size-3.5" /> 重置统计
            </Button>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <Metric icon={Users} label="用户数" secondary="并发用户" tone="green" value={aggregate.user_count} />
          <Metric
            icon={Activity}
            label="每秒请求数"
            secondary="RPS"
            tone="blue"
            value={aggregate.requests_per_second}
          />
          <Metric
            icon={Gauge}
            label="失败率"
            secondary={`失败请求数 ${formatNumber(aggregate.failure_count ?? 0)}`}
            suffix="%"
            tone="purple"
            value={percentage(aggregate.failure_rate)}
          />
          <Metric icon={FileText} label="请求数" secondary="总请求数" tone="orange" value={aggregate.request_count} />
          <Metric icon={ShieldX} label="失败数" secondary="失败请求数" tone="red" value={aggregate.failure_count} />
          <Metric
            icon={Clock3}
            label="平均响应时间"
            secondary={`P95: ${formatNumber(aggregate.p95_response_time_ms ?? 0)} ms`}
            tone="amber"
            suffix=" ms"
            value={aggregate.average_response_time_ms}
          />
        </div>
      </header>
      <PerformanceAiAnalysisDrawer
        onOpenChange={setAnalysisOpen}
        onRepairApplied={(nextRunId) => {
          router.push(`/projects/${projectId}/performance-tests/${testId}/runs/${nextRunId}`);
        }}
        open={analysisOpen}
        projectId={projectId}
        runId={runId}
        testId={testId}
      />
      <Sheet onOpenChange={setHistoryOpen} open={historyOpen}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl" side="right">
          <SheetHeader>
            <SheetTitle>压测历史</SheetTitle>
            <SheetDescription>保留最近 10 次，超过后自动清理最早记录。</SheetDescription>
          </SheetHeader>
          <div className="space-y-2 px-4 pb-6">
            {(history?.runs ?? []).map((historyRun) => (
              <div className="flex items-center rounded-lg border hover:bg-muted/50" key={historyRun.id}>
                <button
                  className="flex min-w-0 flex-1 items-center justify-between gap-4 px-4 py-3 text-left"
                  onClick={() =>
                    router.push(`/projects/${projectId}/performance-tests/${testId}/runs/${historyRun.id}`)
                  }
                  type="button"
                >
                  <span className="min-w-0">
                    <span className="block font-medium text-sm">
                      {formatRunTime(historyRun.finished_at ?? historyRun.created_at)}
                    </span>
                    <span className="block truncate font-mono text-muted-foreground text-xs">{historyRun.id}</span>
                  </span>
                  <Badge className={statusBadgeClass(historyRun.status)} variant="outline">
                    {statusText(historyRun.status)}
                  </Badge>
                </button>
                {DELETABLE_STATUSES.has(historyRun.status) ? (
                  <Button
                    aria-label={`删除历史记录 ${historyRun.id}`}
                    className="mr-2 size-8 shrink-0 text-muted-foreground hover:text-destructive"
                    disabled={deletingRunId === historyRun.id}
                    onClick={() => void deleteHistoryRun(historyRun)}
                    size="icon"
                    title="删除本次记录"
                    variant="ghost"
                  >
                    <X className="size-4" />
                  </Button>
                ) : null}
              </div>
            ))}
            {history && history.runs.length === 0 ? (
              <div className="py-16 text-center text-muted-foreground text-sm">暂无历史压测记录</div>
            ) : null}
          </div>
        </SheetContent>
      </Sheet>

      {run?.error_message ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700 text-sm dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
          <span className="font-medium">运行失败：</span>
          {run.error_message}
        </div>
      ) : null}

      <Tabs className="gap-4" defaultValue="summary">
        <TabsList
          className="h-16 w-full justify-start gap-8 overflow-x-auto rounded-lg border border-slate-200 bg-white px-5 py-0 shadow-[0_10px_24px_-24px_rgba(15,23,42,0.5)] dark:border-slate-800 dark:bg-slate-900"
          variant="line"
        >
          <TabsTrigger
            className="h-16 rounded-none px-1 text-slate-500 text-sm data-[state=active]:text-emerald-600 dark:text-slate-400 dark:data-[state=active]:text-emerald-400"
            value="summary"
          >
            <LayoutDashboard aria-hidden="true" />
            统计汇总
          </TabsTrigger>
          <TabsTrigger
            className="h-16 rounded-none px-1 text-slate-500 text-sm data-[state=active]:text-emerald-600 dark:text-slate-400 dark:data-[state=active]:text-emerald-400"
            value="charts"
          >
            <ChartNoAxesCombined aria-hidden="true" />
            趋势图表
          </TabsTrigger>
          <TabsTrigger
            className="h-16 rounded-none px-1 text-slate-500 text-sm data-[state=active]:text-emerald-600 dark:text-slate-400 dark:data-[state=active]:text-emerald-400"
            value="requests"
          >
            <FileText aria-hidden="true" />
            请求统计
          </TabsTrigger>
          {snapshot?.sse_metrics.metrics.length ? (
            <TabsTrigger
              className="h-16 rounded-none px-1 text-slate-500 text-sm data-[state=active]:text-emerald-600 dark:text-slate-400 dark:data-[state=active]:text-emerald-400"
              value="sse"
            >
              <Clock3 aria-hidden="true" />
              流式指标
            </TabsTrigger>
          ) : null}
          <TabsTrigger
            className="h-16 rounded-none px-1 text-slate-500 text-sm data-[state=active]:text-emerald-600 dark:text-slate-400 dark:data-[state=active]:text-emerald-400"
            value="analysis"
          >
            <ShieldAlert aria-hidden="true" />
            异常分析
          </TabsTrigger>
          <TabsTrigger
            className="h-16 rounded-none px-1 text-slate-500 text-sm data-[state=active]:text-emerald-600 dark:text-slate-400 dark:data-[state=active]:text-emerald-400"
            value="downloads"
          >
            <Download aria-hidden="true" />
            下载文件
          </TabsTrigger>
        </TabsList>
        <TabsContent value="summary">
          <LocustStatisticsTable rows={statisticsRows(snapshot).slice(0, 5)} />
        </TabsContent>
        <TabsContent value="charts">
          <LocustChartsPanel samples={samples} />
        </TabsContent>
        <TabsContent value="sse">
          <LocustGenericTable
            columns={[
              ["metric_id", "指标"],
              ["attempt_count", "请求数"],
              ["matched_count", "命中数"],
              ["missing_count", "缺失数"],
              ["failure_count", "失败数"],
              ["average_ms", "平均值"],
              ["p50_ms", "P50"],
              ["p95_ms", "P95"],
              ["p99_ms", "P99"],
            ]}
            empty="暂无 SSE 流式指标"
            rows={sseMetricRows(snapshot)}
          />
        </TabsContent>
        <TabsContent value="requests">
          <LocustStatisticsTable rows={statisticsRows(snapshot)} />
        </TabsContent>
        <TabsContent className="space-y-5" value="analysis">
          <section className="space-y-3">
            <h3 className="font-semibold text-sm">失败请求</h3>
            <LocustGenericTable
              columns={[
                ["method", "方法"],
                ["request_name", "名称"],
                ["reason", "错误信息"],
                ["count", "次数"],
              ]}
              empty="暂无失败请求"
              rows={snapshot?.failures ?? []}
            />
          </section>
          <section className="space-y-3">
            <h3 className="font-semibold text-sm">异常记录</h3>
            <LocustGenericTable
              columns={[
                ["count", "次数"],
                ["exception_type", "异常类型"],
                ["message", "异常信息"],
                ["request_name", "请求名称"],
              ]}
              empty="暂无异常记录"
              rows={snapshot?.exceptions ?? []}
            />
          </section>
        </TabsContent>
        <TabsContent value="downloads">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {(reports?.reports ?? []).map((report) => (
              <button
                className="rounded-md border px-4 py-3 text-sm transition-colors hover:bg-muted/40 dark:border-slate-800 dark:hover:bg-slate-900"
                key={report.name}
                onClick={() => void downloadReport(report.name)}
                type="button"
              >
                <span className="block text-left font-medium">{reportLabel(report.name)}</span>
                <span className="mt-1 block text-left text-muted-foreground text-xs">{formatBytes(report.size)}</span>
              </button>
            ))}
            {!reports?.reports.length ? (
              <div className="col-span-full rounded-md border px-4 py-12 text-center text-muted-foreground text-sm">
                运行结束后将显示可下载的报告文件
              </div>
            ) : null}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  secondary,
  tone,
  value,
  suffix = "",
}: {
  icon: typeof Activity;
  label: string;
  secondary: string;
  tone: "green" | "blue" | "red" | "purple" | "amber" | "orange";
  value: unknown;
  suffix?: string;
}) {
  return (
    <div className="flex min-h-36 min-w-0 items-center gap-4 rounded-lg border border-slate-200 bg-white px-5 py-6 shadow-[0_10px_24px_-24px_rgba(15,23,42,0.55)] xl:gap-2 xl:px-3 2xl:gap-4 2xl:px-5 dark:border-slate-800 dark:bg-slate-900">
      <span
        className={`flex size-12 shrink-0 items-center justify-center rounded-full xl:size-10 2xl:size-12 ${metricToneClass(tone)}`}
      >
        <Icon aria-hidden="true" className="size-6 xl:size-5 2xl:size-6" strokeWidth={1.9} />
      </span>
      <div className="min-w-0">
        <p className="truncate font-medium text-slate-600 text-sm dark:text-slate-300">{label}</p>
        <p className="mt-2 whitespace-nowrap font-mono font-semibold text-2xl text-slate-950 tabular-nums xl:text-lg 2xl:text-2xl dark:text-slate-100">
          {value === undefined || value === null ? "-" : `${formatNumber(value)}${suffix}`}
        </p>
        <p className="mt-2 truncate text-slate-400 text-xs dark:text-slate-500">{secondary}</p>
      </div>
    </div>
  );
}

function metricToneClass(tone: "green" | "blue" | "red" | "purple" | "amber" | "orange") {
  return {
    green: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",
    blue: "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400",
    red: "bg-red-50 text-red-500 dark:bg-red-500/10 dark:text-red-400",
    purple: "bg-violet-50 text-violet-500 dark:bg-violet-500/10 dark:text-violet-400",
    amber: "bg-amber-50 text-amber-500 dark:bg-amber-500/10 dark:text-amber-400",
    orange: "bg-orange-50 text-orange-500 dark:bg-orange-500/10 dark:text-orange-400",
  }[tone];
}

function chartSamples(rows: Array<Record<string, unknown>>): LocustChartSample[] {
  return rows.slice(-180).map((row) => ({
    sampledAt: formatSampleTime(row.sampled_at),
    users: Number(row.user_count ?? 0),
    rps: Number(row.requests_per_second ?? 0),
    failuresPerSecond: Number(row.failures_per_second ?? 0),
    p50ResponseTime: Number(row.p50_response_time_ms ?? 0),
    p95ResponseTime: Number(row.p95_response_time_ms ?? 0),
  }));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatSampleTime(value: unknown) {
  const text = String(value ?? "");
  const numericTimestamp = Number(text);
  const date =
    Number.isFinite(numericTimestamp) && numericTimestamp > 0
      ? new Date(numericTimestamp * 1000)
      : new Date(text.endsWith("Z") ? text : `${text}Z`);
  return Number.isNaN(date.getTime()) ? text : date.toLocaleTimeString([], { hour12: false });
}

function statisticsRows(snapshot: PerformanceRunStats | null) {
  if (!snapshot) return [];
  return snapshot.request_stats.map((row) => (row.name === "Aggregated" ? { ...row, name: "汇总" } : row));
}

function sseMetricRows(snapshot: PerformanceRunStats | null) {
  return (snapshot?.sse_metrics.metrics ?? []).map((metric) => ({ ...metric }));
}

function percentage(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number * 100 : undefined;
}

function formatRunTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatRunDuration(startedAt?: string | null, finishedAt?: string | null) {
  if (!startedAt) return "-";
  const start = new Date(startedAt).getTime();
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end)) return "-";
  const seconds = Math.max(0, Math.floor((end - start) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours > 0 ? `${String(hours).padStart(2, "0")}:` : ""}${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function formatNumber(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(Number.isInteger(number) ? 0 : 2) : String(value);
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function statusText(status?: PerformanceRun["status"]) {
  return (
    {
      created: "就绪",
      starting: "启动中",
      ready: "就绪",
      running: "运行中",
      stopping: "停止中",
      completed: "已完成",
      stopped: "已停止",
      failed: "失败",
      cancelled: "已取消",
    }[status ?? "created"] ?? "未知状态"
  );
}

function statusBadgeClass(status?: PerformanceRun["status"]) {
  if (status === "running")
    return "border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300";
  if (status === "starting" || status === "stopping")
    return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300";
  if (status === "failed" || status === "cancelled")
    return "border-red-200 bg-red-50 text-red-600 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300";
  if (status === "completed" || status === "stopped")
    return "border-blue-200 bg-blue-50 text-blue-600 dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-300";
  return "border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300";
}

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  return error instanceof Error ? error.message : "Locust 控制台请求失败";
}

function reportLabel(name: string) {
  return (
    {
      "result.html": "HTML 测试报告",
      "result_stats.csv": "统计数据 CSV",
      "result_stats_history.csv": "统计历史 CSV",
      "result_failures.csv": "失败请求 CSV",
      "result_exceptions.csv": "异常记录 CSV",
      "result_tasks.csv": "任务数据 CSV",
      "stdout.log": "标准输出日志",
      "stderr.log": "错误输出日志",
    }[name] ?? name
  );
}
