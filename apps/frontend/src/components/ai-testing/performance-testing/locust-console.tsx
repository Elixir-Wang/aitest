"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Activity, Clock3, FileText, Gauge, RotateCcw, ShieldX, Square, Users } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ApiRequestError,
  getPerformanceRun,
  getPerformanceRunStats,
  listPerformanceRunReports,
  type PerformanceRun,
  type PerformanceRunReports,
  type PerformanceRunStartPayload,
  type PerformanceRunStats,
  performanceRunReportUrl,
  resetPerformanceRunStats,
  startPerformanceRun,
  stopPerformanceRun,
  streamPerformanceRun,
} from "@/lib/api-client";

import { type LocustChartSample, LocustChartsPanel } from "./locust-charts-panel";
import { LocustGenericTable, LocustStatisticsTable } from "./locust-statistics-table";

const TERMINAL_STATUSES = new Set<PerformanceRun["status"]>(["completed", "stopped", "failed", "cancelled"]);

export function LocustConsole({ projectId, testId, runId }: { projectId: string; testId: string; runId: string }) {
  const [run, setRun] = useState<PerformanceRun | null>(null);
  const [snapshot, setSnapshot] = useState<PerformanceRunStats | null>(null);
  const [reports, setReports] = useState<PerformanceRunReports | null>(null);
  const [samples, setSamples] = useState<LocustChartSample[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const runRef = useRef<PerformanceRun | null>(null);

  const refresh = useCallback(async () => {
    const [nextRun, nextSnapshot, nextReports] = await Promise.all([
      getPerformanceRun(projectId, runId),
      getPerformanceRunStats(projectId, runId),
      listPerformanceRunReports(projectId, runId),
    ]);
    runRef.current = nextRun;
    setRun(nextRun);
    setSnapshot(nextSnapshot);
    setReports(nextReports);
    const sample = chartSample(nextSnapshot);
    if (sample) {
      setSamples((current) => {
        if (current.at(-1)?.sampledAt === sample.sampledAt) return current;
        return [...current.slice(-179), sample];
      });
    }
  }, [projectId, runId]);

  useEffect(() => {
    let disposed = false;
    let fallbackTimer: number | undefined;
    const controller = new AbortController();
    const startPollingFallback = () => {
      if (fallbackTimer !== undefined) return;
      fallbackTimer = window.setInterval(() => {
        if (!disposed && (!runRef.current || !TERMINAL_STATUSES.has(runRef.current.status))) {
          refresh().catch((error) => !disposed && toast.error(apiErrorMessage(error)));
        }
      }, 1000);
    };
    refresh()
      .catch((error) => !disposed && toast.error(apiErrorMessage(error)))
      .finally(() => !disposed && setLoading(false));
    streamPerformanceRun(projectId, runId, controller.signal, () => {
      if (!disposed) refresh().catch((error) => toast.error(apiErrorMessage(error)));
    }).catch((error) => {
      if (!disposed && (error as Error)?.name !== "AbortError") startPollingFallback();
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

  if (loading && !run) {
    return <div className="py-20 text-center text-muted-foreground text-sm">正在加载 Locust 控制台...</div>;
  }

  const aggregate = snapshot?.stats.at(-1) ?? {};
  const canStart = run?.status === "created";
  const canStop = run?.status === "starting" || run?.status === "running";

  return (
    <div className="space-y-3">
      <header className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_12px_32px_-28px_rgba(15,23,42,0.55)]">
        <div className="flex flex-wrap items-center justify-between gap-4 border-slate-100 border-b px-0 py-4">
          <div className="flex min-w-0 items-center gap-4">
            <div className="relative flex size-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white shadow-[0_8px_18px_-10px_rgba(37,99,235,0.9)]">
              <Activity aria-hidden="true" className="size-6" strokeWidth={2.2} />
              <span className="absolute -right-1 -bottom-1 size-3 rounded-full border-2 border-background bg-emerald-400" />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-[1.1rem] text-slate-950 tracking-tight">LOCUST</span>
                <Badge className={statusBadgeClass(run?.status)} variant="outline">
                  {statusText(run?.status)}
                </Badge>
              </div>
              <p className="mt-0.5 truncate font-mono text-[11px] text-slate-500">运行 / {runId}</p>
            </div>
          </div>
          <div className="flex w-full items-center justify-end gap-2 sm:w-auto">
            {canStart ? (
              <Button
                className="h-9 flex-1 bg-blue-600 px-4 text-white shadow-sm hover:bg-blue-700 sm:flex-none"
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
            <Button
              className="h-9 flex-1 border-slate-200 bg-slate-100/70 px-3 text-slate-700 hover:bg-slate-100 sm:flex-none"
              disabled={run?.status !== "running" || working}
              onClick={reset}
              size="sm"
              variant="outline"
            >
              <RotateCcw className="mr-2 size-3.5" /> 重置统计
            </Button>
          </div>
        </div>
        <div className="grid grid-cols-2 divide-x divide-slate-100 sm:grid-cols-3 lg:grid-cols-6">
          <Metric icon={Users} label="用户数" tone="slate" value={aggregate.user_count} />
          <Metric icon={Activity} label="每秒请求数" tone="blue" value={aggregate.requests_per_second} />
          <Metric icon={Gauge} label="失败率" tone="red" suffix="%" value={percentage(aggregate.failure_rate)} />
          <Metric icon={FileText} label="请求数" tone="blue" value={aggregate.request_count} />
          <Metric icon={ShieldX} label="失败数" tone="purple" value={aggregate.failure_count} />
          <Metric
            icon={Clock3}
            label="平均响应时间"
            tone="amber"
            suffix=" ms"
            value={aggregate.average_response_time_ms}
          />
        </div>
      </header>

      {run?.error_message ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700 text-sm">
          <span className="font-medium">运行失败：</span>
          {run.error_message}
        </div>
      ) : null}

      <Tabs defaultValue="statistics">
        <TabsList
          className="h-12 w-full justify-start gap-5 overflow-x-auto rounded-none border-slate-200 border-b bg-transparent p-0"
          variant="line"
        >
          <TabsTrigger
            className="h-12 rounded-none px-1 text-slate-500 text-sm data-[state=active]:text-slate-950"
            value="statistics"
          >
            统计
          </TabsTrigger>
          <TabsTrigger
            className="h-12 rounded-none px-1 text-slate-500 text-sm data-[state=active]:text-slate-950"
            value="charts"
          >
            趋势图
          </TabsTrigger>
          <TabsTrigger
            className="h-12 rounded-none px-1 text-slate-500 text-sm data-[state=active]:text-slate-950"
            value="failures"
          >
            失败请求
          </TabsTrigger>
          <TabsTrigger
            className="h-12 rounded-none px-1 text-slate-500 text-sm data-[state=active]:text-slate-950"
            value="exceptions"
          >
            异常
          </TabsTrigger>
          <TabsTrigger
            className="h-12 rounded-none px-1 text-slate-500 text-sm data-[state=active]:text-slate-950"
            value="downloads"
          >
            下载文件
          </TabsTrigger>
        </TabsList>
        <TabsContent className="pt-4" value="statistics">
          <LocustStatisticsTable rows={statisticsRows(snapshot)} />
        </TabsContent>
        <TabsContent className="pt-4" value="charts">
          <LocustChartsPanel samples={samples} />
        </TabsContent>
        <TabsContent className="pt-4" value="failures">
          <LocustGenericTable
            columns={[
              ["method", "方法"],
              ["name", "名称"],
              ["error", "错误信息"],
              ["occurrences", "次数"],
            ]}
            empty="暂无失败请求"
            rows={snapshot?.failures ?? []}
          />
        </TabsContent>
        <TabsContent className="pt-4" value="exceptions">
          <LocustGenericTable
            columns={[
              ["count", "次数"],
              ["msg", "异常信息"],
              ["traceback", "堆栈信息"],
              ["nodes", "节点"],
            ]}
            empty="暂无异常记录"
            rows={snapshot?.exceptions ?? []}
          />
        </TabsContent>
        <TabsContent className="pt-4" value="downloads">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {(reports?.reports ?? []).map((report) => (
              <a
                className="rounded-md border px-4 py-3 text-sm transition-colors hover:bg-muted/40"
                href={performanceRunReportUrl(projectId, runId, report.name)}
                key={report.name}
              >
                <span className="block font-medium">{reportLabel(report.name)}</span>
                <span className="mt-1 block text-muted-foreground text-xs">{formatBytes(report.size)}</span>
              </a>
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
  tone,
  value,
  suffix = "",
}: {
  icon: typeof Activity;
  label: string;
  tone: "slate" | "blue" | "red" | "purple" | "amber";
  value: unknown;
  suffix?: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3 border-slate-100 border-b px-4 py-4 last:border-r-0 sm:px-5 lg:border-r lg:border-b-0 lg:py-4">
      <span
        className={`flex size-8 shrink-0 items-center justify-center rounded-lg bg-slate-50 ${metricToneClass(tone)}`}
      >
        <Icon aria-hidden="true" className="size-5" strokeWidth={1.8} />
      </span>
      <div className="min-w-0">
        <p className="truncate text-[11px] text-slate-500">{label}</p>
        <p className="mt-0.5 font-mono font-semibold text-[1.05rem] text-slate-900 tabular-nums">
          {value === undefined || value === null ? "-" : `${formatNumber(value)}${suffix}`}
        </p>
      </div>
    </div>
  );
}

function metricToneClass(tone: "slate" | "blue" | "red" | "purple" | "amber") {
  return {
    slate: "text-slate-500",
    blue: "text-blue-600",
    red: "text-red-500",
    purple: "text-violet-500",
    amber: "text-amber-500",
  }[tone];
}

function chartSample(snapshot: PerformanceRunStats): LocustChartSample | null {
  const total = snapshot.stats.at(-1);
  if (!total) return null;
  return {
    sampledAt: new Date().toLocaleTimeString([], { hour12: false }),
    users: Number(total.user_count ?? 0),
    rps: Number(total.requests_per_second ?? 0),
    failuresPerSecond: Number(total.failure_rate ?? 0) * 100,
    responseTime: Number(total.average_response_time_ms ?? 0),
  };
}

function statisticsRows(snapshot: PerformanceRunStats | null) {
  if (!snapshot) return [];
  const rows = [...snapshot.request_stats];
  const latest = snapshot.stats.at(-1);
  if (latest) {
    rows.push({
      method: "",
      name: "汇总",
      request_count: latest.request_count,
      failure_count: latest.failure_count,
      median_response_time_ms: latest.p50_response_time_ms,
      p95_response_time_ms: latest.p95_response_time_ms,
      p99_response_time_ms: latest.p99_response_time_ms,
      average_response_time_ms: latest.average_response_time_ms,
      min_response_time_ms: "-",
      max_response_time_ms: "-",
      content_size: "-",
      requests_per_second: latest.requests_per_second,
    });
  }
  return rows;
}

function percentage(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number * 100 : undefined;
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
  if (status === "running") return "border-emerald-200 bg-emerald-50 text-emerald-600";
  if (status === "starting" || status === "stopping") return "border-amber-200 bg-amber-50 text-amber-700";
  if (status === "failed" || status === "cancelled") return "border-red-200 bg-red-50 text-red-600";
  if (status === "completed" || status === "stopped") return "border-blue-200 bg-blue-50 text-blue-600";
  return "border-emerald-200 bg-emerald-50 text-emerald-600";
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
