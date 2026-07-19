"use client";

import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  Activity,
  AlertTriangle,
  Bug,
  ChartNoAxesCombined,
  Download,
  FileDown,
  ListTree,
  LoaderCircle,
  Play,
  RefreshCw,
  RotateCcw,
  ScrollText,
  Square,
  TableProperties,
} from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ApiRequestError,
  getPerformanceRun,
  getPerformanceRunStats,
  listPerformanceRunReports,
  type PerformanceRun,
  type PerformanceRunReports,
  type PerformanceRunStartOptions,
  type PerformanceRunStats,
  performanceRunReportUrl,
  resetPerformanceRunStats,
  startPerformanceRun,
  stopPerformanceRun,
  streamPerformanceRun,
} from "@/lib/api-client";

const TERMINAL_STATUSES = new Set(["completed", "stopped", "failed", "cancelled"]);
const ACTIVE_STATUSES = new Set(["starting", "running", "stopping"]);

type ConsoleTab = "statistics" | "charts" | "failures" | "exceptions" | "tasks" | "logs" | "downloads";
type StartDraft = { host: string; users: string; spawnRate: string; runTime: string };

const TABS: Array<{ id: ConsoleTab; label: string; icon: typeof Activity }> = [
  { id: "statistics", label: "Statistics", icon: TableProperties },
  { id: "charts", label: "Charts", icon: ChartNoAxesCombined },
  { id: "failures", label: "Failures", icon: AlertTriangle },
  { id: "exceptions", label: "Exceptions", icon: Bug },
  { id: "tasks", label: "Tasks", icon: ListTree },
  { id: "logs", label: "Logs", icon: ScrollText },
  { id: "downloads", label: "Downloads", icon: FileDown },
];

export function PerformanceRunDetail({ projectId, runId }: { projectId: string; runId: string }) {
  const [run, setRun] = useState<PerformanceRun | null>(null);
  const [snapshot, setSnapshot] = useState<PerformanceRunStats | null>(null);
  const [reports, setReports] = useState<PerformanceRunReports | null>(null);
  const [activeTab, setActiveTab] = useState<ConsoleTab>("statistics");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<"start" | "stop" | "reset" | "">("");
  const [draft, setDraft] = useState<StartDraft>({ host: "", users: "1", spawnRate: "1", runTime: "60" });
  const initializedDraft = useRef(false);
  const runRef = useRef<PerformanceRun | null>(null);

  const refresh = useCallback(async () => {
    const [runResult, statsResult, reportsResult] = await Promise.all([
      getPerformanceRun(projectId, runId),
      getPerformanceRunStats(projectId, runId),
      listPerformanceRunReports(projectId, runId),
    ]);
    runRef.current = runResult;
    setRun(runResult);
    setSnapshot(statsResult);
    setReports(reportsResult);
    if (!initializedDraft.current) {
      initializedDraft.current = true;
      setDraft({
        host: runResult.target_host ?? "",
        users: String(runResult.load_config.users ?? 1),
        spawnRate: String(runResult.load_config.spawn_rate ?? 1),
        runTime: String(runResult.load_config.measurement_duration_seconds ?? 60),
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
    setLoading(true);
    refresh()
      .catch((error) => !disposed && toast.error(apiErrorMessage(error)))
      .finally(() => !disposed && setLoading(false));
    streamPerformanceRun(projectId, runId, controller.signal, (event, payload) => {
      if (disposed) return;
      if (event === "run") {
        const nextRun = payload as unknown as PerformanceRun;
        runRef.current = nextRun;
        setRun(nextRun);
      } else if (event === "stats") {
        refresh().catch((error) => toast.error(apiErrorMessage(error)));
      } else if (event === "log") {
        setSnapshot((current) => (current ? { ...current, events: [...current.events, payload] } : current));
      }
    }).catch((error) => {
      if (!disposed && (error as Error)?.name !== "AbortError") startPollingFallback();
    });
    return () => {
      disposed = true;
      controller.abort();
      if (fallbackTimer !== undefined) window.clearInterval(fallbackTimer);
    };
  }, [projectId, refresh, runId]);

  const samples = snapshot?.stats ?? [];
  const latest = samples.at(-1);
  const requestRows = useMemo(() => buildStatisticsRows(snapshot), [snapshot]);
  const canStop = Boolean(run && ["starting", "running"].includes(run.status));

  async function startRun() {
    if (!run) return;
    const options: PerformanceRunStartOptions = {
      users: Number(draft.users),
      spawn_rate: Number(draft.spawnRate),
      run_time: Number(draft.runTime),
      host: draft.host.trim() || undefined,
    };
    if (!Number.isInteger(options.users) || options.users < 1 || options.spawn_rate <= 0 || options.run_time < 1) {
      toast.error("用户数必须为正整数，增长速率和运行时间必须大于 0");
      return;
    }
    setWorking("start");
    try {
      await startPerformanceRun(projectId, run.performance_test_id, runId, options);
      await refresh();
      toast.success("Swarming started");
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setWorking("");
    }
  }

  async function stopRun() {
    setWorking("stop");
    try {
      await stopPerformanceRun(projectId, runId);
      await refresh();
      toast.success("Test stopped");
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setWorking("");
    }
  }

  async function resetStats() {
    setWorking("reset");
    try {
      await resetPerformanceRunStats(projectId, runId);
      await refresh();
      toast.success("Statistics reset");
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setWorking("");
    }
  }

  if (loading && !run) {
    return (
      <div className="flex min-h-64 items-center justify-center gap-2 text-muted-foreground text-sm">
        <LoaderCircle className="size-4 animate-spin" />
        正在加载 Locust 控制台
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-0 overflow-hidden border bg-background">
      <header className="border-b bg-muted/20 px-4 py-3 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Activity className="size-5 text-primary" />
              <h1 className="font-semibold text-base">Locust</h1>
              <StatusBadge status={run?.status ?? ""} />
            </div>
            <p className="mt-1 truncate font-mono text-muted-foreground text-xs" title={runId}>
              {run?.target_host || "Target host not configured"} · {runId}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {canStop ? (
              <Button disabled={working !== ""} onClick={stopRun} size="sm" variant="destructive">
                {working === "stop" ? <LoaderCircle className="animate-spin" /> : <Square />}
                Stop
              </Button>
            ) : null}
            <Button disabled={working !== ""} onClick={() => refresh()} size="icon-sm" title="刷新" variant="outline">
              <RefreshCw />
            </Button>
            <Button
              disabled={!run || run.status === "created" || run.status === "stopping" || working !== ""}
              onClick={resetStats}
              size="sm"
              variant="outline"
            >
              {working === "reset" ? <LoaderCircle className="animate-spin" /> : <RotateCcw />}
              Reset stats
            </Button>
          </div>
        </div>
      </header>

      {run?.status === "created" ? (
        <StartTestPanel draft={draft} onChange={setDraft} onStart={startRun} starting={working === "start"} />
      ) : run ? (
        <TelemetryStrip latest={latest} run={run} />
      ) : null}

      {run?.error_message ? (
        <div className="flex items-start gap-2 border-b bg-destructive/5 px-4 py-3 text-destructive text-sm sm:px-5">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span>{run.error_message}</span>
        </div>
      ) : null}

      <nav aria-label="Locust console views" className="overflow-x-auto border-b bg-background px-2">
        <div className="flex min-w-max">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const count = tabCount(tab.id, snapshot);
            return (
              <button
                className={`flex h-11 items-center gap-2 border-b-2 px-3 text-xs transition-colors ${
                  activeTab === tab.id
                    ? "border-primary font-medium text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                type="button"
              >
                <Icon className="size-3.5" />
                {tab.label}
                {count !== null ? <span className="font-mono text-[10px]">{count}</span> : null}
              </button>
            );
          })}
        </div>
      </nav>

      <main className="min-h-[360px] p-4 sm:p-5">
        {activeTab === "statistics" ? <StatisticsView rows={requestRows} /> : null}
        {activeTab === "charts" ? <ChartsView samples={samples} /> : null}
        {activeTab === "failures" ? <FailuresView rows={snapshot?.failures ?? []} /> : null}
        {activeTab === "exceptions" ? <ExceptionsView rows={snapshot?.exceptions ?? []} /> : null}
        {activeTab === "tasks" ? <TasksView run={run} rows={requestRows} /> : null}
        {activeTab === "logs" ? <LogsView rows={snapshot?.events ?? []} /> : null}
        {activeTab === "downloads" ? <DownloadsView projectId={projectId} reports={reports} runId={runId} /> : null}
      </main>
    </div>
  );
}

function StartTestPanel({
  draft,
  onChange,
  onStart,
  starting,
}: {
  draft: StartDraft;
  onChange: (draft: StartDraft) => void;
  onStart: () => void;
  starting: boolean;
}) {
  return (
    <section className="border-b px-4 py-5 sm:px-5">
      <div className="mb-4">
        <h2 className="font-semibold text-sm">Start a new load test</h2>
        <p className="mt-1 text-muted-foreground text-xs">配置与 Locust Web UI 的 swarm 参数一致。</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2 md:items-end 2xl:grid-cols-[minmax(220px,1fr)_140px_140px_140px_auto]">
        <ConsoleField label="Host">
          <Input
            onChange={(event) => onChange({ ...draft, host: event.target.value })}
            placeholder="https://example.com"
            value={draft.host}
          />
        </ConsoleField>
        <ConsoleField label="Number of users">
          <Input
            min="1"
            onChange={(event) => onChange({ ...draft, users: event.target.value })}
            type="number"
            value={draft.users}
          />
        </ConsoleField>
        <ConsoleField label="Ramp up (users/s)">
          <Input
            min="0.1"
            onChange={(event) => onChange({ ...draft, spawnRate: event.target.value })}
            step="0.1"
            type="number"
            value={draft.spawnRate}
          />
        </ConsoleField>
        <ConsoleField label="Run time (seconds)">
          <Input
            min="1"
            onChange={(event) => onChange({ ...draft, runTime: event.target.value })}
            type="number"
            value={draft.runTime}
          />
        </ConsoleField>
        <Button disabled={starting} onClick={onStart}>
          {starting ? <LoaderCircle className="animate-spin" /> : <Play />}
          Start swarming
        </Button>
      </div>
    </section>
  );
}

function ConsoleField({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="grid gap-1.5">
      <span className="font-medium text-xs">{label}</span>
      {children}
    </div>
  );
}

function TelemetryStrip({ latest, run }: { latest?: Record<string, unknown>; run: PerformanceRun }) {
  const items = [
    ["STATUS", statusText(run.status)],
    ["USERS", formatInteger(latest?.user_count)],
    ["RPS", formatNumber(latest?.requests_per_second, 2)],
    ["FAILURES", formatPercent(latest?.failure_rate)],
    ["MEDIAN", formatMilliseconds(latest?.p50_response_time_ms)],
    ["95%ILE", formatMilliseconds(latest?.p95_response_time_ms)],
    ["REQUESTS", formatInteger(latest?.request_count)],
  ];
  return (
    <section className="grid border-b bg-muted/10 sm:grid-cols-4 xl:grid-cols-7">
      {items.map(([label, value]) => (
        <div className="border-b px-4 py-3 sm:border-r sm:last:border-r-0 xl:border-b-0" key={label}>
          <p className="font-medium text-[10px] text-muted-foreground">{label}</p>
          <p className="mt-1 font-mono font-semibold text-sm tabular-nums">{value}</p>
        </div>
      ))}
    </section>
  );
}

function StatisticsView({ rows }: { rows: Array<Record<string, unknown>> }) {
  return (
    <ConsoleSection description="Aggregated request statistics" title="Statistics">
      <DataTable
        columns={[
          "method",
          "name",
          "request_count",
          "failure_count",
          "median_response_time_ms",
          "p95_response_time_ms",
          "p99_response_time_ms",
          "average_response_time_ms",
          "min_response_time_ms",
          "max_response_time_ms",
          "content_size",
          "requests_per_second",
        ]}
        rows={rows}
      />
    </ConsoleSection>
  );
}

function ChartsView({ samples }: { samples: Array<Record<string, unknown>> }) {
  const data = samples.slice(-120).map((sample, index) => ({
    index,
    time: String(sample.sampled_at ?? index),
    rps: Number(sample.requests_per_second ?? 0),
    failures: Number(sample.failure_rate ?? 0) * 100,
    average: Number(sample.average_response_time_ms ?? 0),
    p95: Number(sample.p95_response_time_ms ?? 0),
    users: Number(sample.user_count ?? 0),
  }));
  if (!data.length)
    return (
      <EmptyState title="No chart data" detail="Start the test to collect request rate and response-time history." />
    );
  return (
    <div className="space-y-8">
      <ConsoleChart
        data={data}
        lines={[
          { key: "rps", label: "Total requests per second", color: "#2563eb" },
          { key: "failures", label: "Failures (%)", color: "#dc2626" },
        ]}
      />
      <ConsoleChart
        data={data}
        lines={[
          { key: "average", label: "Average response time (ms)", color: "#059669" },
          { key: "p95", label: "95% response time (ms)", color: "#d97706" },
        ]}
      />
      <ConsoleChart data={data} lines={[{ key: "users", label: "Number of users", color: "#7c3aed" }]} />
    </div>
  );
}

function ConsoleChart({
  data,
  lines,
}: {
  data: Array<Record<string, number | string>>;
  lines: Array<{ key: string; label: string; color: string }>;
}) {
  return (
    <section>
      <div className="mb-3 flex flex-wrap gap-4">
        {lines.map((line) => (
          <span className="flex items-center gap-2 text-xs" key={line.key}>
            <span className="size-2.5" style={{ backgroundColor: line.color }} />
            {line.label}
          </span>
        ))}
      </div>
      <div className="h-56 w-full border bg-muted/5 p-2">
        <ResponsiveContainer height="100%" width="100%">
          <LineChart data={data} margin={{ left: 0, right: 16, top: 12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="index" tick={{ fontSize: 10 }} tickLine={false} />
            <YAxis tick={{ fontSize: 10 }} tickLine={false} width={42} />
            <Tooltip labelFormatter={(value) => data[Number(value)]?.time ?? value} />
            {lines.map((line) => (
              <Line
                dataKey={line.key}
                dot={false}
                isAnimationActive={false}
                key={line.key}
                stroke={line.color}
                strokeWidth={1.5}
                type="monotone"
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function FailuresView({ rows }: { rows: Array<Record<string, unknown>> }) {
  return (
    <ConsoleSection description="Request failures grouped by method, name and error" title="Failures">
      <DataTable columns={["method", "request_name", "reason", "count", "last_occurred_at"]} rows={rows} />
    </ConsoleSection>
  );
}

function ExceptionsView({ rows }: { rows: Array<Record<string, unknown>> }) {
  return (
    <ConsoleSection description="Python exceptions raised by Locust users" title="Exceptions">
      <DataTable columns={["count", "exception_type", "message", "request_name", "last_occurred_at"]} rows={rows} />
    </ConsoleSection>
  );
}

function TasksView({ run, rows }: { run: PerformanceRun | null; rows: Array<Record<string, unknown>> }) {
  const users = Number(run?.load_config.users ?? 0);
  const taskRows = rows
    .filter((row) => row.name !== "Aggregated")
    .map((row) => ({ user_class: "PerformanceUser", task: row.name, ratio: "100%", users }));
  return (
    <ConsoleSection description="User class and task execution ratio" title="Tasks">
      <DataTable columns={["user_class", "task", "ratio", "users"]} rows={taskRows} />
    </ConsoleSection>
  );
}

function LogsView({ rows }: { rows: Array<Record<string, unknown>> }) {
  return (
    <ConsoleSection description="Run lifecycle and worker events" title="Logs">
      <DataTable columns={["created_at", "level", "event_type", "message"]} newestFirst rows={rows} />
    </ConsoleSection>
  );
}

function DownloadsView({
  projectId,
  reports,
  runId,
}: {
  projectId: string;
  reports: PerformanceRunReports | null;
  runId: string;
}) {
  const rows = reports?.reports ?? [];
  return (
    <ConsoleSection description="Locust HTML report and raw CSV output" title="Download Data">
      {rows.length ? (
        <div className="divide-y border">
          {rows.map((report) => (
            <a
              className="flex items-center justify-between gap-4 px-4 py-3 text-sm hover:bg-muted/30"
              href={performanceRunReportUrl(projectId, runId, report.name)}
              key={report.name}
            >
              <span className="flex min-w-0 items-center gap-2">
                <Download className="size-4 shrink-0 text-muted-foreground" />
                <span className="truncate font-mono text-xs">{report.name}</span>
              </span>
              <span className="shrink-0 text-muted-foreground text-xs">{formatBytes(report.size)}</span>
            </a>
          ))}
        </div>
      ) : (
        <EmptyState title="No reports available" detail="Locust writes report files after the run starts." />
      )}
    </ConsoleSection>
  );
}

function ConsoleSection({ children, description, title }: { children: ReactNode; description: string; title: string }) {
  return (
    <section>
      <div className="mb-4">
        <h2 className="font-semibold text-sm">{title}</h2>
        <p className="mt-1 text-muted-foreground text-xs">{description}</p>
      </div>
      {children}
    </section>
  );
}

function DataTable({
  rows,
  columns,
  newestFirst = false,
}: {
  rows: Array<Record<string, unknown>>;
  columns: string[];
  newestFirst?: boolean;
}) {
  const displayedRows = useMemo(() => (newestFirst ? [...rows].reverse() : rows).slice(0, 500), [newestFirst, rows]);
  return (
    <div className="overflow-x-auto border">
      <table className="w-full min-w-max border-collapse text-left text-xs">
        <thead className="bg-muted/40 text-muted-foreground">
          <tr>
            {columns.map((column) => (
              <th className="border-b px-3 py-2.5 font-medium" key={column}>
                {columnLabel(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {displayedRows.length ? (
            displayedRows.map((row, index) => (
              <tr
                className={row.name === "Aggregated" ? "bg-muted/25 font-semibold" : "hover:bg-muted/15"}
                key={String(row.id ?? row.name ?? row.created_at ?? index)}
              >
                {columns.map((column) => (
                  <td className="max-w-[32rem] px-3 py-2.5 tabular-nums" key={column}>
                    {formatCell(column, row[column])}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td className="px-3 py-12 text-center text-muted-foreground" colSpan={columns.length}>
                No data
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ detail, title }: { detail: string; title: string }) {
  return (
    <div className="border border-dashed px-4 py-14 text-center">
      <p className="font-medium text-sm">{title}</p>
      <p className="mt-1 text-muted-foreground text-xs">{detail}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const active = ACTIVE_STATUSES.has(status);
  return (
    <Badge className="gap-1.5 font-normal" variant={status === "failed" ? "destructive" : "outline"}>
      <span className={`size-1.5 rounded-full ${active ? "animate-pulse bg-emerald-500" : "bg-muted-foreground/60"}`} />
      {statusText(status)}
    </Badge>
  );
}

function buildStatisticsRows(snapshot: PerformanceRunStats | null) {
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

function tabCount(tab: ConsoleTab, snapshot: PerformanceRunStats | null) {
  if (tab === "failures") return snapshot?.failures.length ?? 0;
  if (tab === "exceptions") return snapshot?.exceptions.length ?? 0;
  return null;
}

function columnLabel(column: string) {
  return (
    {
      method: "Type",
      name: "Name",
      request_name: "Name",
      request_count: "# Requests",
      failure_count: "# Fails",
      median_response_time_ms: "Median (ms)",
      p95_response_time_ms: "95%ile (ms)",
      p99_response_time_ms: "99%ile (ms)",
      average_response_time_ms: "Average (ms)",
      min_response_time_ms: "Min (ms)",
      max_response_time_ms: "Max (ms)",
      content_size: "Average size (bytes)",
      requests_per_second: "Current RPS",
      reason: "Error",
      count: "Occurrences",
      last_occurred_at: "Last occurrence",
      exception_type: "Type",
      message: "Message",
      user_class: "User class",
      task: "Task",
      ratio: "Ratio",
      users: "Users",
      created_at: "Time",
      level: "Level",
      event_type: "Event",
    }[column] ?? column
  );
}

function formatCell(column: string, value: unknown) {
  if (value === undefined || value === null || value === "") return "-";
  if (column === "failure_rate") return formatPercent(value);
  if (typeof value === "number" && !Number.isInteger(value)) return value.toFixed(2);
  return String(value);
}

function formatInteger(value: unknown) {
  return value === undefined || value === null ? "-" : Math.round(Number(value)).toLocaleString();
}

function formatNumber(value: unknown, digits = 0) {
  return value === undefined || value === null ? "-" : Number(value).toFixed(digits);
}

function formatMilliseconds(value: unknown) {
  return value === undefined || value === null ? "-" : `${Math.round(Number(value))} ms`;
}

function formatPercent(value: unknown) {
  return value === undefined || value === null ? "-" : `${(Number(value) * 100).toFixed(2)}%`;
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function statusText(status: string) {
  return (
    {
      created: "Ready",
      starting: "Spawning",
      running: "Running",
      stopping: "Stopping",
      completed: "Finished",
      stopped: "Stopped",
      failed: "Failed",
      cancelled: "Cancelled",
    }[status] ?? "Unknown"
  );
}

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  return "Locust 控制台加载失败";
}
