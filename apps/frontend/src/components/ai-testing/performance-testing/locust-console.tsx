"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { RotateCcw, Square } from "lucide-react";
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

import { LocustChartsPanel, type LocustChartSample } from "./locust-charts-panel";
import { LocustStartPanel } from "./locust-start-panel";
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

  const defaults = useMemo<PerformanceRunStartPayload>(() => {
    const config = run?.load_config ?? {};
    return {
      users: Number(config.users ?? 1),
      spawn_rate: Number(config.spawn_rate ?? 1),
      run_time: Number(config.measurement_duration_seconds ?? 60),
    };
  }, [run?.load_config]);

  async function start(payload: PerformanceRunStartPayload) {
    setWorking(true);
    try {
      await startPerformanceRun(projectId, testId, runId, payload);
      await refresh();
      toast.success("Load test started");
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
      toast.success("Load test stopped");
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
      toast.success("Statistics reset");
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setWorking(false);
    }
  }

  if (loading && !run) {
    return <div className="py-20 text-center text-muted-foreground text-sm">Loading Locust console…</div>;
  }

  const aggregate = snapshot?.stats.at(-1) ?? {};
  const canStop = run?.status === "starting" || run?.status === "running";

  return (
    <div className="space-y-5">
      <header className="overflow-hidden rounded-lg border bg-slate-950 text-slate-100 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <span className="font-semibold text-lg tracking-tight">LOCUST</span>
              <Badge className="border-slate-700 bg-slate-900 text-slate-200" variant="outline">
                {statusText(run?.status)}
              </Badge>
            </div>
            <p className="mt-1 truncate font-mono text-slate-400 text-xs">run / {runId}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button disabled={!canStop || working} onClick={stop} size="sm" variant="destructive">
              <Square className="mr-2 size-3.5" /> Stop
            </Button>
            <Button
              className="border-slate-700 bg-slate-900 text-slate-100 hover:bg-slate-800"
              disabled={run?.status !== "running" || working}
              onClick={reset}
              size="sm"
              variant="outline"
            >
              <RotateCcw className="mr-2 size-3.5" /> Reset Stats
            </Button>
          </div>
        </div>
        <div className="grid grid-cols-2 border-slate-800 border-t sm:grid-cols-4 lg:grid-cols-6">
          <Metric label="Users" value={aggregate.user_count} />
          <Metric label="RPS" value={aggregate.requests_per_second} />
          <Metric label="Failure rate" suffix="%" value={percentage(aggregate.failure_rate)} />
          <Metric label="Requests" value={aggregate.request_count} />
          <Metric label="Failures" value={aggregate.failure_count} />
          <Metric label="Avg response" suffix=" ms" value={aggregate.average_response_time_ms} />
        </div>
      </header>

      {run?.status === "created" ? <LocustStartPanel defaults={defaults} disabled={working} onStart={start} /> : null}

      {run?.error_message ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-destructive text-sm">
          {run.error_message}
        </div>
      ) : null}

      <Tabs defaultValue="statistics">
        <TabsList className="w-full justify-start overflow-x-auto" variant="line">
          <TabsTrigger value="statistics">Statistics</TabsTrigger>
          <TabsTrigger value="charts">Charts</TabsTrigger>
          <TabsTrigger value="failures">Failures</TabsTrigger>
          <TabsTrigger value="exceptions">Exceptions</TabsTrigger>
          <TabsTrigger value="downloads">Download Data</TabsTrigger>
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
              ["method", "Type"],
              ["name", "Name"],
              ["error", "Error"],
              ["occurrences", "Occurrences"],
            ]}
            empty="No failures have been recorded."
            rows={snapshot?.failures ?? []}
          />
        </TabsContent>
        <TabsContent className="pt-4" value="exceptions">
          <LocustGenericTable
            columns={[
              ["count", "Count"],
              ["msg", "Message"],
              ["traceback", "Traceback"],
              ["nodes", "Nodes"],
            ]}
            empty="No exceptions have been recorded."
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
                <span className="block font-medium">{report.name}</span>
                <span className="mt-1 block text-muted-foreground text-xs">{formatBytes(report.size)}</span>
              </a>
            ))}
            {!reports?.reports.length ? (
              <div className="col-span-full rounded-md border px-4 py-12 text-center text-muted-foreground text-sm">
                Download files appear after Locust writes run artifacts.
              </div>
            ) : null}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Metric({ label, value, suffix = "" }: { label: string; value: unknown; suffix?: string }) {
  return (
    <div className="border-slate-800 border-r px-4 py-3 last:border-r-0">
      <p className="text-[10px] text-slate-500 uppercase tracking-[0.14em]">{label}</p>
      <p className="mt-1 font-mono font-semibold text-base tabular-nums">
        {value === undefined || value === null ? "-" : `${formatNumber(value)}${suffix}`}
      </p>
    </div>
  );
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
      name: "Aggregated",
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
      created: "READY",
      starting: "SPAWNING",
      ready: "READY",
      running: "RUNNING",
      stopping: "STOPPING",
      completed: "COMPLETED",
      stopped: "STOPPED",
      failed: "FAILED",
      cancelled: "CANCELLED",
    }[status ?? "created"] ?? "UNKNOWN"
  );
}

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  return error instanceof Error ? error.message : "Locust console request failed";
}
